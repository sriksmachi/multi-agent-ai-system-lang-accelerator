"""
Writer Agent FastAPI Service

Independent microservice for content writing using Azure OpenAI.
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

from agents.writer_agent.agent import WriterAgent
from agents.writer_agent.schemas import WriteRequest, WriteResponse
from core.a2a_protocol import AgentHealthResponse
from core.logging_config import get_logger
from core.telemetry import setup_telemetry

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

# Initialize telemetry
setup_telemetry(service_name="writer-agent")

# Global agent instance
writer_agent: WriterAgent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app"""
    global writer_agent
    logger.info("🚀 Starting Writer Agent Service")
    writer_agent = WriterAgent()
    logger.info("✅ Writer Agent initialized")
    yield
    logger.info("🛑 Shutting down Writer Agent Service")


# Initialize FastAPI app
app = FastAPI(
    title="Writer Agent Service",
    description="Content writing agent for multi-agent LinkedIn post generation",
    version="1.0.0",
    lifespan=lifespan
)

# Instrument with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)


@app.get("/health", response_model=AgentHealthResponse)
async def health_check():
    """Health check endpoint"""
    return AgentHealthResponse(
        agent="writer",
        status="healthy",
        version="1.0.0"
    )


@app.post("/write", response_model=WriteResponse)
async def write_content(request: WriteRequest):
    """
    Generate content draft for a LinkedIn post.
    
    Args:
        request: WriteRequest containing topic, plan, and research documents
        
    Returns:
        WriteResponse with generated draft
    """
    with tracer.start_as_current_span("writer.write_content") as span:
        try:
            span.set_attribute("thread_id", request.thread_id)
            span.set_attribute("topic", request.topic)
            span.set_attribute("user_id", request.user_id)
            
            logger.info(f"✍️ Writing content for topic: {request.topic} (thread: {request.thread_id})")
            
            # Prepare state for agent
            state = {
                "topic": request.topic,
                "plan": request.plan,
                "documents": request.research_documents,
                "tone": request.tone,
                "platform": request.platform,
                "user_id": request.user_id,
                "thread_id": request.thread_id
            }
            
            # Call writer agent
            result = writer_agent.write_node(state)
            
            if "draft" not in result or not result["draft"]:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to generate draft"
                )
            
            logger.info(f"✅ Content drafted successfully (thread: {request.thread_id})")
            
            return WriteResponse(
                draft=result["draft"],
                thread_id=request.thread_id,
                status="success"
            )
            
        except Exception as e:
            logger.error(f"❌ Error writing content: {str(e)}")
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            raise HTTPException(
                status_code=500,
                detail=f"Error generating draft: {str(e)}"
            )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"❌ Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "agent": "writer",
            "status": "error",
            "error": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("AGENT_PORT", "8003"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENVIRONMENT", "production") == "development",
        log_level="info"
    )
