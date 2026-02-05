"""
FastAPI application for the agentic post generator using FastMCP.
"""

import asyncio
import os
import logging
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables FIRST
load_dotenv()

from azure.monitor.opentelemetry import configure_azure_monitor
# Configure Azure Monitor BEFORE any other initialization (critical for tracing)
configure_azure_monitor(
    connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
)

# Instrument OpenAI BEFORE importing modules that use OpenAI clients
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
OpenAIInstrumentor().instrument()

from starlette.middleware.cors import CORSMiddleware

# Azure imports
from azure.monitor.opentelemetry import configure_azure_monitor
from azure.core.settings import settings

# OpenTelemetry imports
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
from opentelemetry import trace

# MCP imports
from mcp.server.fastmcp import Context, FastMCP
from mcp import ServerSession

import uvicorn

# Local imports
from api.schemas import (
    HealthResponse,
    ErrorResponse,
)
from workflows import configure_post_generator


# Configure logging to console FIRST - force configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ],
    force=True  # Force reconfiguration
)

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = True

# Ensure console handler is added
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

# Suppress noisy Azure loggers
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.monitor.opentelemetry.exporter.export._base").setLevel(logging.WARNING)
logging.getLogger("azure.cosmos._cosmos_http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("mcp.server.transport_security").setLevel(logging.ERROR)

# Initialize tracer
tracer = trace.get_tracer(__name__)
settings.tracing_implementation = "opentelemetry"

mcp = FastMCP("SocialMediaPostGenerator")

# Get the Starlette app and configure CORS immediately
starlette_app = mcp.streamable_http_app()

# Then wrap it with CORS middleware
starlette_app = CORSMiddleware(
    starlette_app,
    allow_origins=["*"],
    allow_credentials=False,  # Set to False when allow_origins is ["*"]
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

@mcp.tool()
async def generate_linkedin_post(
    topic: str,
    ctx: Context[ServerSession, None],
    user_id: Optional[str] = None,
) -> str:  # Keep return type str
    """
    Generate a professional LinkedIn post with real-time streaming updates.
    """
    if not user_id:
        user_id = f"mcp-user-{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    thread_id = f"thread_{user_id}_{datetime.now().strftime('%Y%m%d')}"
    logger.info(f"[{user_id}] FastMCP: Streaming LinkedIn post for topic: {topic}")

    with tracer.start_as_current_span("fastmcp_generate_linkedin_post_streaming") as span:
        try:
            await ctx.info(f"Starting generation for: {topic}")
            await ctx.report_progress(0.1, message="Initializing workflow...")

            compiled_workflow, initial_state, config = configure_post_generator(
                user_id=user_id,
                topic=topic,
                thread_id=thread_id
            )

            await ctx.report_progress(0.2, message="Workflow ready")

            accumulated = ""

            async for chunk in compiled_workflow.astream(initial_state.model_dump(), config=config, stream_mode="updates"):
                if isinstance(chunk, dict):
                    for node_name, node_output in chunk.items():
                        if isinstance(node_output, dict):
                            # Stream draft as it appears
                            if draft := node_output.get("draft"):
                                new_part = draft[len(accumulated):]
                                if new_part:
                                    await ctx.info(new_part)  # ← This streams visible text
                                    accumulated += new_part
                                await ctx.report_progress(0.5, message="Drafting post...")

                            # Stream final post
                            elif final := node_output.get("final_post"):
                                new_part = final[len(accumulated):]
                                if new_part:
                                    await ctx.info(new_part)  # ← Visible streaming
                                    accumulated += new_part
                                await ctx.report_progress(0.9, message="Finalizing...")

                            # Optional: show agent messages
                            for msg in node_output.get("messages", []):
                                role = msg.get("role", "agent")
                                content = msg.get("content", "")
                                if content:
                                    await ctx.info(f"[{role}] {content}")

            await ctx.report_progress(1.0, message="Complete!")
            await ctx.info("Post generation finished")

            span.set_attribute("success", True)
            return accumulated  # Final full post

        except Exception as e:
            await ctx.error(f"Error: {str(e)}")
            logger.error(f"Streaming error: {e}", exc_info=True)
            raise
        
@mcp.tool()
async def greet(ctx: Context[ServerSession, None], name: str = "World") -> str:
    """Greet someone by name."""
    await ctx.info(f"Starting to greet {name}")
    await ctx.report_progress(0.5, message="processing..")
    await ctx.debug("Halfway through processing")
    await asyncio.sleep(1)
    await ctx.report_progress(1.0, message="processing complete!")
    await ctx.info(f"Successfully greeted {name}")
    return f"Hello, {name}!"

if __name__ == "__main__":
    # Run the server
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(starlette_app, host=host, port=port)
