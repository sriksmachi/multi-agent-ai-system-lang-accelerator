"""
FastAPI application for the agentic post generator using FastMCP.
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
    connection_string=os.getenv("APPINSIGHTS_CONNECTION_STRING", "")
)

# Instrument OpenAI BEFORE importing modules that use OpenAI clients
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
OpenAIInstrumentor().instrument()

# Now import FastAPI and other dependencies
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry import trace
from azure.core.settings import settings
import uvicorn

from api.schemas import (
    HealthResponse,
    ErrorResponse,
)

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
    title="Multi-Agent LinkedIn Post Generator with FastMCP",
    description="Multi-agent system for generating LinkedIn posts using FastMCP protocol. Access tools via MCP endpoints.",
    version="0.2.0",
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

# Include MCP routes (uses workflows directly)
from api.routes.mcp_routes import router as mcp_router
app.include_router(mcp_router)

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
    return {
        "message": "Multi-Agent LinkedIn Post Generator API with FastMCP",
        "docs": "/docs",
        "health": "/health",
        "mcp_tools": "/mcp/tools",
        "mcp_call": "/mcp/tools/call"
    }

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
        message="FastMCP API is running",
        version="0.2.0"
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
