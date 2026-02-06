"""
FastAPI application for the agentic post generator using FastMCP.
"""

import asyncio
import os
import logging
from datetime import datetime
from typing import Optional
import json
import uuid

import httpx
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
from workflows import configure_post_generator, AgentOrchestrator


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
async def generate_linkedin_post_stream(
    topic: str,
    ctx: Context[ServerSession, None],
    user_id: Optional[str] = None,
) -> str:
    """
    Generate a professional LinkedIn post with real-time streaming updates.
    Uses LangGraph workflow with A2A agent discovery.
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

            # Track intermediate results
            result_data = {
                "plan": "",
                "context": "",
                "draft": "",
                "final_post": "",
                "scores": {},
                "feedback": ""
            }

            async for chunk in compiled_workflow.astream(initial_state.model_dump(), config=config, stream_mode="updates"):
                if isinstance(chunk, dict):
                    for node_name, node_output in chunk.items():
                        if isinstance(node_output, dict):
                            # Stream plan from planner
                            if plan := node_output.get("plan"):
                                result_data["plan"] = plan
                                await ctx.info(f"[PLAN]{plan}[/PLAN]")
                                await ctx.report_progress(0.3, message="Plan created")

                            # Stream context from researcher
                            if context := node_output.get("context"):
                                result_data["context"] = context[:500] + "..." if len(context) > 500 else context
                                await ctx.info(f"[CONTEXT]{result_data['context']}[/CONTEXT]")
                                await ctx.report_progress(0.4, message="Research complete")

                            # Stream draft from writer
                            if draft := node_output.get("draft"):
                                result_data["draft"] = draft
                                await ctx.info(f"[DRAFT]{draft}[/DRAFT]")
                                await ctx.report_progress(0.6, message="Draft written")

                            # Stream scores from reviewer
                            if scores := node_output.get("scores"):
                                result_data["scores"] = scores
                                await ctx.info(f"[SCORES]{json.dumps(scores)}[/SCORES]")
                                
                            if feedback := node_output.get("feedback"):
                                result_data["feedback"] = feedback
                                await ctx.info(f"[FEEDBACK]{feedback}[/FEEDBACK]")
                                await ctx.report_progress(0.8, message="Review complete")

                            # Stream final post
                            if final := node_output.get("final_post"):
                                result_data["final_post"] = final
                                await ctx.info(f"[FINAL]{final}[/FINAL]")
                                await ctx.report_progress(0.95, message="Finalizing...")

            await ctx.report_progress(1.0, message="Complete!")
            
            # Return final result as JSON
            final_output = result_data.get("final_post") or result_data.get("draft") or ""
            await ctx.info(f"[RESULT]{json.dumps(result_data)}[/RESULT]")

            span.set_attribute("success", True)
            return final_output

        except Exception as e:
            await ctx.error(f"Error: {str(e)}")
            logger.error(f"Streaming error: {e}", exc_info=True)
            raise
        
@mcp.tool()
async def generate_linkedin_post_sync(
    topic: str,
    user_id: Optional[str] = None,
    platform: Optional[str] = "LinkedIn",
    tone: Optional[str] = "professional",
) -> str:
    """
    Generate a LinkedIn post using the Supervisor Agent (A2A orchestrator).
    This is a synchronous call that returns the complete result without streaming.
    """
    if not user_id:
        user_id = f"mcp-user-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    thread_id = f"sup-{uuid.uuid4().hex[:8]}"
    supervisor_url = os.getenv("SUPERVISOR_AGENT_URL", "http://supervisor:8005")
    
    logger.info(f"[{user_id}] Calling Supervisor Agent for topic: {topic}")
    
    with tracer.start_as_current_span("fastmcp_generate_linkedin_post_sync") as span:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{supervisor_url}/generate",
                    json={
                        "topic": topic,
                        "platform": platform,
                        "tone": tone,
                        "user_id": user_id,
                        "thread_id": thread_id
                    }
                )
                response.raise_for_status()
                result = response.json()
            
            final_content = result.get("final_content", "")
            draft = result.get("draft", "")
            
            span.set_attribute("success", True)
            span.set_attribute("supervisor_url", supervisor_url)
            
            return final_content or draft or ""
            
        except httpx.HTTPStatusError as e:
            error_msg = f"Supervisor Agent error: {e.response.status_code} - {e.response.text}"
            logger.error(error_msg)
            span.set_attribute("error", True)
            raise Exception(error_msg)
        except Exception as e:
            logger.error(f"Sync generation error: {e}", exc_info=True)
            span.set_attribute("error", True)
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


@mcp.tool()
async def discover_agents(ctx: Context[ServerSession, None]) -> str:
    """
    Discover all available agents via A2A protocol.
    Returns information about each agent's capabilities and skills.
    """
    await ctx.info("🔍 Discovering agents via A2A protocol...")
    
    orchestrator = AgentOrchestrator(use_a2a_discovery=True)
    try:
        await orchestrator.discover_all_agents()
        
        agents_info = {}
        for agent_name, card in orchestrator.get_discovered_agents().items():
            agents_info[agent_name] = {
                "name": card.name,
                "description": card.description,
                "version": card.version,
                "skills": [s.get("name") for s in card.skills],
                "endpoints": card.endpoints
            }
            await ctx.info(f"✅ {card.name}: {[s.get('name') for s in card.skills]}")
        
        await ctx.info(f"🎉 Discovered {len(agents_info)} agents")
        return json.dumps(agents_info, indent=2)
    finally:
        await orchestrator.close()


@mcp.tool()
async def get_agent_card(
    ctx: Context[ServerSession, None],
    agent_name: str
) -> str:
    """
    Get the A2A Agent Card for a specific agent.
    
    Args:
        agent_name: Name of the agent (planner, researcher, writer, reviewer)
    """
    await ctx.info(f"🔍 Fetching Agent Card for: {agent_name}")
    
    orchestrator = AgentOrchestrator(use_a2a_discovery=True)
    try:
        agent_urls = {
            "planner": orchestrator.planner_url,
            "researcher": orchestrator.researcher_url,
            "writer": orchestrator.writer_url,
            "reviewer": orchestrator.reviewer_url,
        }
        
        if agent_name not in agent_urls:
            return json.dumps({"error": f"Unknown agent: {agent_name}. Available: {list(agent_urls.keys())}"})
        
        card = await orchestrator.discover_agent(agent_name, agent_urls[agent_name])
        if card:
            await ctx.info(f"✅ Discovered {card.name}")
            return json.dumps({
                "name": card.name,
                "description": card.description,
                "version": card.version,
                "protocol": card.protocol,
                "capabilities": card.capabilities,
                "skills": card.skills,
                "endpoints": card.endpoints
            }, indent=2)
        else:
            return json.dumps({"error": f"Failed to discover {agent_name}"})
    finally:
        await orchestrator.close()


if __name__ == "__main__":
    # Run the server
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(starlette_app, host=host, port=port)
