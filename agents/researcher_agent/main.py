"""
Researcher Agent FastAPI Service

Independent microservice for document research using Azure AI Search.
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

from agents.researcher_agent.agent import ResearcherAgent
from agents.researcher_agent.schemas import ResearchRequest, ResearchResponse
from core.a2a_protocol import AgentHealthResponse
from core.logging_config import get_logger
from core.telemetry import setup_telemetry

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

# Initialize telemetry
setup_telemetry(service_name="researcher-agent")

# Global agent instance
researcher_agent: ResearcherAgent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app"""
    global researcher_agent
    logger.info("🚀 Starting Researcher Agent Service")
    researcher_agent = ResearcherAgent()
    logger.info("✅ Researcher Agent initialized")
    yield
    logger.info("🛑 Shutting down Researcher Agent Service")


# Initialize FastAPI app
app = FastAPI(
    title="Researcher Agent Service",
    description="Document research agent for multi-agent LinkedIn post generation",
    version="1.0.0",
    lifespan=lifespan
)

# Instrument with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)


@app.get("/health", response_model=AgentHealthResponse)
async def health_check():
    """Health check endpoint"""
    return AgentHealthResponse(
        agent="researcher",
        status="healthy",
        version="1.0.0"
    )


@app.post("/research", response_model=ResearchResponse)
async def conduct_research(request: ResearchRequest):
    """
    Conduct research using Azure AI Search.
    
    Args:
        request: ResearchRequest containing topic and plan
        
    Returns:
        ResearchResponse with retrieved documents
    """
    with tracer.start_as_current_span("researcher.conduct_research") as span:
        try:
            span.set_attribute("thread_id", request.thread_id)
            span.set_attribute("topic", request.topic)
            span.set_attribute("user_id", request.user_id)
            
            logger.info(f"🔍 Conducting research for topic: {request.topic} (thread: {request.thread_id})")
            
            # Prepare state for agent
            state = {
                "topic": request.topic,
                "plan": request.plan,
                "user_id": request.user_id,
                "thread_id": request.thread_id
            }
            
            # Call researcher agent
            result = researcher_agent.research_node(state)
            
            documents = result.get("documents", [])
            
            logger.info(f"✅ Research completed: {len(documents)} documents found (thread: {request.thread_id})")
            
            return ResearchResponse(
                documents=documents,
                document_count=len(documents),
                thread_id=request.thread_id,
                status="success"
            )
            
        except Exception as e:
            logger.error(f"❌ Error conducting research: {str(e)}")
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            raise HTTPException(
                status_code=500,
                detail=f"Error conducting research: {str(e)}"
            )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"❌ Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "agent": "researcher",
            "status": "error",
            "error": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("AGENT_PORT", "8002"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENVIRONMENT", "production") == "development",
        log_level="info"
    )
