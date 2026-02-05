"""
Reviewer Agent FastAPI Service

Independent microservice for content review using Azure OpenAI.
"""

import os
import sys
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agents.reviewer_agent.agent import ReviewerAgent
from agents.reviewer_agent.schemas import ReviewRequest, ReviewResponse
from core.a2a_protocol import AgentHealthResponse
from core.logging_config import get_logger
from core.telemetry import setup_telemetry

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

# Initialize telemetry
setup_telemetry(service_name="reviewer-agent")

# Global agent instance
reviewer_agent: ReviewerAgent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app"""
    global reviewer_agent
    logger.info("🚀 Starting Reviewer Agent Service")
    reviewer_agent = ReviewerAgent()
    logger.info("✅ Reviewer Agent initialized")
    yield
    logger.info("🛑 Shutting down Reviewer Agent Service")


# Initialize FastAPI app
app = FastAPI(
    title="Reviewer Agent Service",
    description="Content review agent for multi-agent LinkedIn post generation",
    version="1.0.0",
    lifespan=lifespan
)

# Instrument with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)


@app.get("/health", response_model=AgentHealthResponse)
async def health_check():
    """Health check endpoint"""
    return AgentHealthResponse(
        agent="reviewer",
        status="healthy",
        version="1.0.0"
    )


@app.post("/review", response_model=ReviewResponse)
async def review_content(request: ReviewRequest):
    """
    Review and finalize content draft.
    
    Args:
        request: ReviewRequest containing draft and context
        
    Returns:
        ReviewResponse with reviewed final post
    """
    with tracer.start_as_current_span("reviewer.review_content") as span:
        try:
            span.set_attribute("thread_id", request.thread_id)
            span.set_attribute("topic", request.topic)
            span.set_attribute("user_id", request.user_id)
            
            logger.info(f"📝 Reviewing content for topic: {request.topic} (thread: {request.thread_id})")
            
            # Prepare state for agent
            state = {
                "topic": request.topic,
                "plan": request.plan,
                "draft": request.draft,
                "platform": request.platform,
                "user_id": request.user_id,
                "thread_id": request.thread_id
            }
            
            # Call reviewer agent
            result = reviewer_agent.review_post(state)
            
            if "final_post" not in result or not result["final_post"]:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to generate final post"
                )
            
            logger.info(f"✅ Content reviewed successfully (thread: {request.thread_id})")
            
            return ReviewResponse(
                final_post=result["final_post"],
                scores=result.get("scores"),
                feedback=result.get("feedback"),
                needs_refinement=result.get("needs_refinement", False),
                thread_id=request.thread_id,
                status="success"
            )
            
        except Exception as e:
            logger.error(f"❌ Error reviewing content: {str(e)}")
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            raise HTTPException(
                status_code=200, # we return 200 to avoid retry loops in the workflow, making review optional. 
                detail=f"Error reviewing content: {str(e)}"
            )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"❌ Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "agent": "reviewer",
            "status": "error",
            "error": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("AGENT_PORT", "8004"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENVIRONMENT", "production") == "development",
        log_level="info"
    )
