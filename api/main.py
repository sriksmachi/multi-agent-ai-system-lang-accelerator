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
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor

import uvicorn

from api.schemas import (
    ChatRequest,
    GeneratePostResponse,
    HealthResponse,
    ErrorResponse,
)

from workflows import run_post_generator

# Load environment variables
load_dotenv()

# Initialize logger
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Multi Agent Linked in post generator",
    description="Multi-agent system for generating platform specific posts using LLMs, KBs, and tools.",
    version="0.1.0",
)

# Add CORS middleware (configure for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure specific origins for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

project_client = AIProjectClient(credential=DefaultAzureCredential(), project_url=os.getenv("AZURE_FOUNDRY_PROJECT_URL"))
connection_string = project_client.telemetry.get_application_insights_connection_string()
configure_azure_monitor(connection_string=connection_string)
OpenAIInstrumentor().instrument()

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
    
    Workflow:
    1. Planner: Create outline + retrieve context
    2. Writer: Generate draft
    3. Fact-Checker: Evaluate with DeepEval
    4. Router: Decide refine or finish
    5. (Conditional) Loop back to Writer for refinement
    
    Args:
        request: ChatRequest with user_id and query
        
    Returns:
        GeneratePostResponse with post and platform
        
    Raises:
        HTTPException: If generation fails
    """
    try:
        # Run the workflow
        result = run_post_generator(
            user_id=request.user_id,
            topic=request.query           
        )
        
        return GeneratePostResponse(**result)
        
    except ValueError as e:
        # Handle retriever errors (e.g., FAISS index not found)
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=f"Retriever error: {str(e)}. Ensure FAISS index is built.",
        )
    except Exception as e:
        logger.error(f"Error generating post: {e}", exc_info=True)
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
