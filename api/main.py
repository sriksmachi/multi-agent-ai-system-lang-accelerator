"""
FastAPI application for the agentic post generator.

Endpoints:
- GET /health: Health check
- POST /sessions: Create/resume session
- POST /posts:generate: Generate post
"""

import os
import uuid
import json
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse

from api.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    GeneratePostRequest,
    GeneratePostResponse,
    HealthResponse,
    ErrorResponse,
    StreamEvent,
)
from workflows import run_post_generator, stream_post_generator
from lib.retriever import FaissRetriever
from lib.memory import LongTermMemory
from lib.observability import get_tracer

# Load environment variables
load_dotenv()


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    print("Starting Agentic Post Generator API...")
    print(f"Environment: {os.getenv('DEBUG', 'false')}")
    print(f"Checkpointer: {os.getenv('CHECKPOINTER', 'memory')}")
    
    # Initialize global components (optional pre-loading)
    try:
        # Pre-load retriever
        faiss_path = os.getenv("FAISS_INDEX_PATH", "./data/faiss_index")
        if os.path.exists(os.path.join(faiss_path, "index.faiss")):
            print(f"FAISS index available at: {faiss_path}")
        else:
            print(f"FAISS index not found at: {faiss_path}")
            print(f"Run 'python scripts/build_faiss_index.py' to create it")
    except Exception as e:
        print(f"Error checking FAISS index: {e}")
    
    yield
    
    # Shutdown
    print("Shutting down API...")
    # Flush any pending traces
    tracer = get_tracer()
    tracer.flush()


# Create FastAPI app
app = FastAPI(
    title="Agentic Post Generator",
    description="Multi-agent system for generating platform-specific social media posts with RAG and evaluation",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware (configure for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure specific origins for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handler for HTTPException
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with standard error format."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.__class__.__name__,
            message=exc.detail,
        ).model_dump(),
    )


# Exception handler for general exceptions
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle unexpected exceptions."""
    print(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="InternalServerError",
            message="An unexpected error occurred. Please try again later.",
            detail=str(exc) if os.getenv("DEBUG", "false").lower() == "true" else None,
        ).model_dump(),
    )


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint redirect to docs."""
    return {"message": "Agentic Post Generator API", "docs": "/docs", "health": "/health"}


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check API health and component status",
)
async def health_check():
    """
    Health check endpoint.
    
    Returns status of all major components:
    - Retriever (FAISS)
    - Long-term memory (Cosmos/in-memory)
    - Checkpointer (Cosmos/in-memory)
    - Tracer (Langfuse)
    """
    components: Dict[str, str] = {}
    
    # Check retriever
    try:
        faiss_path = os.getenv("FAISS_INDEX_PATH", "./data/faiss_index")
        if os.path.exists(os.path.join(faiss_path, "index.faiss")):
            components["retriever"] = "ok"
        else:
            components["retriever"] = "not_initialized"
    except Exception:
        components["retriever"] = "error"
    
    # Check LTM
    try:
        ltm = LongTermMemory()
        components["ltm"] = "ok" if ltm else "error"
    except Exception:
        components["ltm"] = "error"
    
    # Check checkpointer
    checkpointer_type = os.getenv("CHECKPOINTER", "memory")
    components["checkpointer"] = f"ok ({checkpointer_type})"
    
    # Check tracer
    try:
        tracer = get_tracer()
        components["tracer"] = "ok" if tracer.enabled else "disabled"
    except Exception:
        components["tracer"] = "error"
    
    # Overall status
    has_errors = any(v == "error" for v in components.values())
    status_value = "degraded" if has_errors else "healthy"
    message = "Some components unavailable" if has_errors else "All systems operational"
    
    return HealthResponse(
        status=status_value,
        message=message,
        version="0.1.0",
        components=components,
    )


@app.post(
    "/sessions",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Session",
    description="Create a new session or resume an existing one",
)
async def create_session(request: CreateSessionRequest):
    """
    Create a new session for the user.
    
    Sessions enable:
    - Multi-turn conversations
    - State persistence via checkpointing
    - User preference loading from LTM
    
    Args:
        request: CreateSessionRequest with user_id and optional platform
        
    Returns:
        CreateSessionResponse with session_id and metadata
    """
    try:
        # Generate unique session ID
        session_id = f"session-{request.user_id}-{uuid.uuid4().hex[:8]}"
        
        # Initialize LTM and load/create user preferences
        ltm = LongTermMemory()
        user_prefs = ltm.get_user_preferences(request.user_id)
        
        if not user_prefs:
            # Create default preferences for new user
            ltm.upsert_user_preferences(
                request.user_id,
                {
                    "user_id": request.user_id,
                    "preferred_tone": "professional",
                    "platform_defaults": {
                        request.platform: {}
                    },
                }
            )
            print(f"   Created default preferences for user: {request.user_id}")
        
        return CreateSessionResponse(
            session_id=session_id,
            user_id=request.user_id,
            platform=request.platform,
            message="Session created successfully",
        )
        
    except Exception as e:
        print(f"Error creating session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}",
        )


@app.post(
    "/posts:generate",
    response_model=GeneratePostResponse,
    summary="Generate Post",
    description="Generate a platform-specific social media post using the multi-agent workflow",
)
async def generate_post(request: GeneratePostRequest):
    """
    Generate a social media post.
    
    Workflow:
    1. Planner: Create outline + retrieve context
    2. Writer: Generate draft
    3. Fact-Checker: Evaluate with DeepEval
    4. Router: Decide refine or finish
    5. (Conditional) Loop back to Writer for refinement
    
    Args:
        request: GeneratePostRequest with session_id, topic, platform, tone
        
    Returns:
        GeneratePostResponse with post_markdown, scores, trace_url
        
    Raises:
        HTTPException: If generation fails
    """
    try:
        print(f"\n{'='*60}")
        print(f"POST GENERATION REQUEST")
        print(f"Session: {request.session_id}")
        print(f"Topic: {request.topic}")
        print(f"Platform: {request.platform or 'default'}")
        print(f"{'='*60}\n")
        
        # Extract user_id from session_id (format: session-{user_id}-{random})
        try:
            user_id = request.session_id.split("-")[1]
        except IndexError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session_id format. Use POST /sessions to create a valid session.",
            )
        
        # Run the workflow
        result = run_post_generator(
            user_id=user_id,
            session_id=request.session_id,
            topic=request.topic,
            platform=request.platform or "linkedin",
            tone=request.tone,
        )
        
        return GeneratePostResponse(**result)
        
    except ValueError as e:
        # Handle retriever errors (e.g., FAISS index not found)
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=f"Retriever error: {str(e)}. Ensure FAISS index is built.",
        )
    except Exception as e:
        print(f"Error generating post: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Post generation failed: {str(e)}",
        )


@app.post(
    "/posts:generate:stream",
    summary="Generate Post (Streaming)",
    description="Generate a post with real-time progress updates via Server-Sent Events (SSE)",
)
async def generate_post_stream(request: GeneratePostRequest):
    """
    Generate a social media post with streaming progress updates.
    
    Returns Server-Sent Events (SSE) for each step:
    - node_start: Agent starts execution
    - progress: Intermediate progress updates
    - node_end: Agent completes execution
    - complete: Final result with post and scores
    - error: Error occurred
    
    Args:
        request: GeneratePostRequest with session_id, topic, platform, tone
        
    Returns:
        EventSourceResponse with streaming events
        
    Example client usage:
        ```javascript
        const eventSource = new EventSource('/posts:generate:stream');
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log(data.message);
        };
        ```
    """
    # Extract user_id from session_id
    try:
        user_id = request.session_id.split("-")[1]
    except IndexError:
        async def error_generator():
            yield {
                "event": "error",
                "data": json.dumps({
                    "error": "InvalidSessionError",
                    "message": "Invalid session_id format. Use POST /sessions to create a valid session.",
                })
            }
        return EventSourceResponse(error_generator())
    
    async def event_generator() -> AsyncGenerator[dict, None]:
        """
        Generate SSE events as the workflow executes.
        """
        try:
            # Stream the workflow execution
            async for event in stream_post_generator(
                user_id=user_id,
                session_id=request.session_id,
                topic=request.topic,
                platform=request.platform or "linkedin",
                tone=request.tone,
            ):
                # Add timestamp to each event
                event["timestamp"] = datetime.utcnow().isoformat() + "Z"
                
                # Yield SSE-formatted event
                yield {
                    "event": event.get("event", "progress"),
                    "data": json.dumps(event)
                }
        
        except Exception as e:
            print(f"Error in streaming generation: {e}")
            yield {
                "event": "error",
                "data": json.dumps({
                    "event": "error",
                    "message": f"Post generation failed: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                })
            }
    
    return EventSourceResponse(event_generator())


if __name__ == "__main__":
    import uvicorn
    
    # Run with: python -m api.main
    # Or: uvicorn api.main:app --reload
    
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "true").lower() == "true"
    
    print(f"Starting server at http://{host}:{port}")
    print(f"API docs at http://{host}:{port}/docs")
    
    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
