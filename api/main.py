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
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, AsyncGenerator

from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

# Configure Azure Monitor BEFORE any other imports (critical for tracing)
from azure.monitor.opentelemetry import configure_azure_monitor
configure_azure_monitor(
    connection_string="InstrumentationKey=56d1abd5-93d6-4d79-9ba5-b32a09720b5f;IngestionEndpoint=https://eastus2-3.in.applicationinsights.azure.com/;LiveEndpoint=https://eastus2.livediagnostics.monitor.azure.com/;ApplicationId=79def9ed-d37c-4102-83cb-72c57d512f09"
)

# Instrument OpenAI BEFORE importing modules that use OpenAI clients
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
OpenAIInstrumentor().instrument()

# Now import FastAPI and other dependencies
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry import trace
from azure.core.settings import settings
import uvicorn

from api.schemas import (
    ChatRequest,
    GeneratePostResponse,
    HealthResponse,
    ErrorResponse,
)

# Import workflows AFTER OpenAI instrumentation is configured
from workflows import run_post_generator

# Initialize logger
logger = logging.getLogger(__name__)

# Suppress noisy Azure loggers
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.monitor.opentelemetry.exporter.export._base").setLevel(logging.WARNING)

# Initialize tracer
tracer = trace.get_tracer(__name__)
settings.tracing_implementation = "opentelemetry"

# Create FastAPI app
app = FastAPI(
    title="Multi Agent Linked in post generator",
    description="Multi-agent system for generating platform specific posts using LLMs, KBs, and tools.",
    version="0.1.0",
)

# Instrument FastAPI (must be done after app creation)
FastAPIInstrumentor.instrument_app(app)

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
    logger.error(f"Unexpected error: {exc}", exc_info=True)
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
    """
    return HealthResponse(
        status="healthy",
        message="API is running",
        version="0.1.0"
    )

@app.post(
    "/chat",
    response_model=GeneratePostResponse,
    summary="Chat Endpoint",
    description="Generate social media post based on user input.",
)
async def generate_post(request: ChatRequest):
    """
    Generate a social media post.
    
    Args:
        request: ChatRequest with user_id and query
        
    Returns:
        GeneratePostResponse with post and platform
        
    Raises:
        HTTPException: If generation fails
    """
    with tracer.start_as_current_span(
        "generate_post_api",
        attributes={
            "user_id": request.user_id,
            "api.endpoint": "/chat",
            "api.method": "POST",
            "query": request.query,
            "query_length": len(request.query),
        }
    ) as span:
        try:
            # Add thread tracking for conversation context
            thread_id = f"thread_{request.user_id}_{datetime.now().strftime('%Y%m%d')}"
            span.set_attribute("gen_ai.thread.id", thread_id)
            
            span.add_event("gen_ai.request.received", {
                "user_id": request.user_id,
                "query_length": len(request.query),
                "gen_ai.thread.id": thread_id
            })
            
            logger.info(f"[{request.user_id}] API: Received post generation request for query: {request.query}")

            # Run the workflow
            result = run_post_generator(
                user_id=request.user_id,
                topic=request.query,
                thread_id=thread_id
            )
            
            span.set_attribute("success", True)
            span.set_attribute("trace_id", result.get("trace_id", ""))
            span.set_attribute("post_length", len(result.get("post", "")))
            span.set_attribute("platform", result.get("platform", "unknown"))
            
            span.add_event("gen_ai.response.completed", {
                "post_length": len(result.get("post", "")),
                "trace_id": result.get("trace_id", ""),
                "gen_ai.event.content": json.dumps({"post": result.get("post", "")})
            })
            
            
            logger.info(f"[{request.user_id}] API: Post generation completed successfully")
            
            return GeneratePostResponse(**result)
            
        except ValueError as e:
            # Handle retriever errors (e.g., FAISS index not found)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            span.record_exception(e)
            logger.error(f"[{request.user_id}] API: Retriever error: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_424_FAILED_DEPENDENCY,
                detail=f"Retriever error: {str(e)}. Ensure FAISS index is built.",
            )
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            span.record_exception(e)
            logger.error(f"[{request.user_id}] API: Error generating post: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Post generation failed: {str(e)}",
            )

if __name__ == "__main__":

    # Run with: python -m api.main
    # Or: uvicorn api.main:app --reload
    
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "true").lower() == "true"
    
    logger.info(f"Starting server at http://{host}:{port}")
    logger.info(f"API docs at http://{host}:{port}/docs")
    
    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
