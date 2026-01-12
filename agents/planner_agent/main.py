"""
Planner Agent FastAPI Service

Independent microservice for content planning using Azure OpenAI.
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

from agents.planner_agent.agent import PlannerAgent
from agents.planner_agent.schemas import PlanRequest, PlanResponse
from core.a2a_protocol import AgentHealthResponse
from core.logging_config import get_logger
from core.telemetry import setup_telemetry

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

# Initialize telemetry
setup_telemetry(service_name="planner-agent")

# Global agent instance
planner_agent: PlannerAgent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app"""
    global planner_agent
    logger.info("🚀 Starting Planner Agent Service")
    planner_agent = PlannerAgent()
    logger.info("✅ Planner Agent initialized")
    yield
    logger.info("🛑 Shutting down Planner Agent Service")


# Initialize FastAPI app
app = FastAPI(
    title="Planner Agent Service",
    description="Content planning agent for multi-agent LinkedIn post generation",
    version="1.0.0",
    lifespan=lifespan
)

# Instrument with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)


@app.get("/health", response_model=AgentHealthResponse)
async def health_check():
    """Health check endpoint"""
    return AgentHealthResponse(
        agent="planner",
        status="healthy",
        version="1.0.0"
    )


@app.post("/plan", response_model=PlanResponse)
async def create_plan(request: PlanRequest):
    """
    Generate a content plan for a LinkedIn post.
    
    Args:
        request: PlanRequest containing topic, tone, platform, etc.
        
    Returns:
        PlanResponse with generated plan
    """
    with tracer.start_as_current_span("planner.create_plan") as span:
        try:
            span.set_attribute("thread_id", request.thread_id)
            span.set_attribute("topic", request.topic)
            span.set_attribute("user_id", request.user_id)
            
            logger.info(f"📋 Creating plan for topic: {request.topic} (thread: {request.thread_id})")
            
            # Prepare state for agent
            state = {
                "topic": request.topic,
                "platform": request.platform,
                "tone": request.tone,
                "user_id": request.user_id,
                "thread_id": request.thread_id
            }
            
            # Call planner agent
            result = planner_agent.plan_node(state)
            
            if "plan" not in result or not result["plan"]:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to generate plan"
                )
            
            logger.info(f"✅ Plan created successfully (thread: {request.thread_id})")
            
            return PlanResponse(
                plan=result["plan"],
                thread_id=request.thread_id,
                status="success"
            )
            
        except Exception as e:
            logger.error(f"❌ Error creating plan: {str(e)}")
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            raise HTTPException(
                status_code=500,
                detail=f"Error generating plan: {str(e)}"
            )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"❌ Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "agent": "planner",
            "status": "error",
            "error": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("AGENT_PORT", "8001"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENVIRONMENT", "production") == "development",
        log_level="info"
    )
