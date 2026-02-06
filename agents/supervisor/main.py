"""
Supervisor Agent FastAPI Service

Orchestrates multi-agent workflow using A2A protocol for agent discovery and communication.
This agent coordinates Planner → Researcher → Writer → Reviewer pipeline.
"""

import os
import sys
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from typing import Dict, Any, Optional

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agents.supervisor.schemas import (
    GeneratePostRequest, 
    GeneratePostResponse,
    WorkflowStatus,
    AgentStatus,
    DiscoveredAgent,
    AgentRegistryResponse
)
from core.a2a_protocol import AgentHealthResponse
from core.a2a_client import A2AClient, get_agent_url, AgentCard
from core.logging_config import get_logger
from core.telemetry import setup_telemetry

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

# Initialize telemetry
setup_telemetry(service_name="supervisor-agent")

# Global instances
a2a_client: A2AClient = None
discovered_agents: Dict[str, AgentCard] = {}


async def discover_all_agents():
    """Discover all agents via A2A protocol on startup"""
    global discovered_agents
    
    agent_names = ["planner", "researcher", "writer", "reviewer"]
    
    for agent_name in agent_names:
        try:
            agent_url = get_agent_url(agent_name)
            if agent_url:
                card = await a2a_client.discover_agent(agent_url)
                discovered_agents[agent_name] = card
                logger.info(f"✅ Discovered {card.name} at {agent_url}")
        except Exception as e:
            logger.warning(f"⚠️ Could not discover {agent_name}: {e}")


async def refresh_agent_discovery(agent_name: str) -> Optional[AgentCard]:
    """Refresh discovery for a specific agent"""
    global discovered_agents
    try:
        agent_url = get_agent_url(agent_name)
        if agent_url:
            card = await a2a_client.discover_agent(agent_url)
            discovered_agents[agent_name] = card
            return card
    except Exception as e:
        logger.error(f"❌ Failed to refresh discovery for {agent_name}: {e}")
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app"""
    global a2a_client, discovered_agents
    logger.info("🚀 Starting Supervisor Agent Service")
    
    # Initialize A2A client
    a2a_client = A2AClient(timeout=60.0)
    
    # Discover all agents on startup
    await discover_all_agents()
    
    logger.info("✅ Supervisor Agent initialized with A2A discovery")
    yield
    logger.info("🛑 Shutting down Supervisor Agent Service")
    await a2a_client.close()


# Initialize FastAPI app
app = FastAPI(
    title="Supervisor Agent Service",
    description="Orchestrator for multi-agent LinkedIn post generation using A2A protocol",
    version="1.0.0",
    lifespan=lifespan
)

# Instrument with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)


@app.get("/health", response_model=AgentHealthResponse)
async def health_check():
    """Health check endpoint"""
    return AgentHealthResponse(
        agent="supervisor",
        status="healthy",
        version="1.0.0"
    )


@app.get("/.well-known/agent.json")
async def agent_discovery():
    """A2A Agent Discovery endpoint - returns Agent Card"""
    return {
        "name": "Supervisor Agent",
        "description": "Orchestrator for multi-agent LinkedIn post generation using A2A protocol",
        "version": "1.0.0",
        "protocol": "a2a",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "agentOrchestration": True
        },
        "skills": [
            {
                "name": "generate_post",
                "description": "Orchestrate full workflow to generate a LinkedIn post using planner, researcher, writer, and reviewer agents",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Topic for the LinkedIn post"},
                        "platform": {"type": "string", "description": "Target platform"},
                        "tone": {"type": "string", "description": "Desired tone"},
                        "user_id": {"type": "string", "description": "User identifier"},
                        "thread_id": {"type": "string", "description": "Thread identifier"}
                    },
                    "required": ["topic", "thread_id"]
                }
            }
        ],
        "endpoints": {
            "generate_post": "/generate",
            "agents": "/agents",
            "health": "/health"
        },
        "orchestrates": ["planner", "researcher", "writer", "reviewer"]
    }


@app.get("/agents", response_model=AgentRegistryResponse)
async def list_discovered_agents():
    """List all discovered agents and their capabilities via A2A"""
    agents_info = {}
    
    for agent_name, card in discovered_agents.items():
        agent_url = get_agent_url(agent_name)
        agents_info[agent_name] = DiscoveredAgent(
            name=card.name,
            description=card.description,
            version=card.version,
            skills=[s.get("name", "") for s in card.skills],
            healthy=await a2a_client.check_health(agent_url),
            url=agent_url
        )
    
    return AgentRegistryResponse(
        discovered_agents=agents_info,
        total_count=len(discovered_agents)
    )


@app.post("/agents/{agent_name}/refresh")
async def refresh_agent(agent_name: str):
    """Refresh A2A discovery for a specific agent"""
    card = await refresh_agent_discovery(agent_name)
    if card:
        return {
            "status": "success",
            "agent": card.name,
            "skills": [s.get("name") for s in card.skills]
        }
    raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found or unavailable")


@app.post("/agents/refresh-all")
async def refresh_all_agents():
    """Refresh A2A discovery for all agents"""
    await discover_all_agents()
    return {
        "status": "success",
        "discovered_count": len(discovered_agents),
        "agents": list(discovered_agents.keys())
    }


async def call_agent_skill(
    agent_name: str,
    skill_name: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Call an agent skill using A2A protocol with automatic discovery.
    
    Args:
        agent_name: Name of the agent (planner, researcher, writer, reviewer)
        skill_name: Name of the skill to invoke
        payload: Input data for the skill
        
    Returns:
        Response from the agent
    """
    agent_url = get_agent_url(agent_name)
    
    if not agent_url:
        raise HTTPException(
            status_code=503,
            detail=f"Agent {agent_name} URL not configured"
        )
    
    # Check if agent is discovered, if not try to discover
    if agent_name not in discovered_agents:
        card = await refresh_agent_discovery(agent_name)
        if not card:
            raise HTTPException(
                status_code=503,
                detail=f"Agent {agent_name} not available for A2A discovery"
            )
    
    try:
        result = await a2a_client.call_skill(
            agent_base_url=agent_url,
            skill_name=skill_name,
            payload=payload,
            discover_first=False  # Already discovered
        )
        return result
        
    except Exception as e:
        logger.error(f"❌ Failed to call {agent_name}.{skill_name}: {e}")
        
        # Try to re-discover and retry once
        logger.info(f"🔄 Retrying with fresh A2A discovery for {agent_name}")
        await refresh_agent_discovery(agent_name)
        
        try:
            result = await a2a_client.call_skill(
                agent_base_url=agent_url,
                skill_name=skill_name,
                payload=payload,
                discover_first=True
            )
            return result
        except Exception as retry_error:
            raise HTTPException(
                status_code=503,
                detail=f"Agent {agent_name} unavailable: {str(retry_error)}"
            )


@app.post("/generate", response_model=GeneratePostResponse)
async def generate_post(request: GeneratePostRequest):
    """
    Orchestrate the full workflow to generate a LinkedIn post using A2A protocol.
    
    Workflow:
    1. Planner Agent - Create content plan
    2. Researcher Agent - Find relevant documents
    3. Writer Agent - Generate draft
    4. Reviewer Agent - Review and finalize
    """
    with tracer.start_as_current_span("supervisor.generate_post") as span:
        try:
            span.set_attribute("thread_id", request.thread_id)
            span.set_attribute("topic", request.topic)
            span.set_attribute("user_id", request.user_id)
            
            workflow_status = WorkflowStatus(
                thread_id=request.thread_id,
                current_step="starting",
                agents={}
            )
            
            logger.info(f"🎯 Starting A2A workflow for topic: {request.topic} (thread: {request.thread_id})")
            
            # ========== Step 1: Call Planner Agent via A2A ==========
            logger.info("📋 Step 1: Calling Planner Agent via A2A")
            workflow_status.current_step = "planning"
            workflow_status.agents["planner"] = AgentStatus(status="running")
            
            plan_result = await call_agent_skill(
                agent_name="planner",
                skill_name="plan",
                payload={
                    "topic": request.topic,
                    "platform": request.platform,
                    "tone": request.tone,
                    "user_id": request.user_id,
                    "thread_id": request.thread_id
                }
            )
            
            plan = plan_result.get("plan", "")
            workflow_status.agents["planner"] = AgentStatus(
                status="completed", 
                result={"plan_length": len(plan)}
            )
            logger.info(f"✅ Planner completed: {len(plan)} chars")
            
            # ========== Step 2: Call Researcher Agent via A2A ==========
            logger.info("🔍 Step 2: Calling Researcher Agent via A2A")
            workflow_status.current_step = "researching"
            workflow_status.agents["researcher"] = AgentStatus(status="running")
            
            research_result = await call_agent_skill(
                agent_name="researcher",
                skill_name="research",
                payload={
                    "topic": request.topic,
                    "plan": plan,
                    "user_id": request.user_id,
                    "thread_id": request.thread_id
                }
            )
            
            documents = research_result.get("documents", [])
            workflow_status.agents["researcher"] = AgentStatus(
                status="completed", 
                result={"document_count": len(documents)}
            )
            logger.info(f"✅ Researcher completed: {len(documents)} documents found")
            
            # ========== Step 3: Call Writer Agent via A2A ==========
            logger.info("✍️ Step 3: Calling Writer Agent via A2A")
            workflow_status.current_step = "writing"
            workflow_status.agents["writer"] = AgentStatus(status="running")
            
            write_result = await call_agent_skill(
                agent_name="writer",
                skill_name="write",
                payload={
                    "topic": request.topic,
                    "plan": plan,
                    "research_documents": documents,
                    "tone": request.tone,
                    "platform": request.platform,
                    "user_id": request.user_id,
                    "thread_id": request.thread_id
                }
            )
            
            draft = write_result.get("draft", "")
            workflow_status.agents["writer"] = AgentStatus(
                status="completed", 
                result={"draft_length": len(draft)}
            )
            logger.info(f"✅ Writer completed: {len(draft)} chars")
            
            # ========== Step 4: Call Reviewer Agent via A2A ==========
            logger.info("📝 Step 4: Calling Reviewer Agent via A2A")
            workflow_status.current_step = "reviewing"
            workflow_status.agents["reviewer"] = AgentStatus(status="running")
            
            review_result = await call_agent_skill(
                agent_name="reviewer",
                skill_name="review",
                payload={
                    "topic": request.topic,
                    "draft": draft,
                    "plan": plan,
                    "platform": request.platform,
                    "user_id": request.user_id,
                    "thread_id": request.thread_id
                }
            )
            
            final_post = review_result.get("final_post", "")
            feedback = review_result.get("feedback", "")
            workflow_status.agents["reviewer"] = AgentStatus(
                status="completed", 
                result={"final_length": len(final_post)}
            )
            logger.info(f"✅ Reviewer completed: {len(final_post)} chars")
            
            # ========== Workflow Complete ==========
            workflow_status.current_step = "completed"
            logger.info(f"🎉 A2A Workflow completed successfully (thread: {request.thread_id})")
            
            return GeneratePostResponse(
                thread_id=request.thread_id,
                status="success",
                plan=plan,
                documents=documents,
                draft=draft,
                final_content=final_post,
                feedback=feedback,
                workflow_status=workflow_status
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Workflow error: {str(e)}")
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            raise HTTPException(
                status_code=500,
                detail=f"Workflow error: {str(e)}"
            )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"❌ Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "agent": "supervisor",
            "status": "error",
            "error": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("AGENT_PORT", "8005"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENVIRONMENT", "production") == "development",
        log_level="info"
    )
