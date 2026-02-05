"""
HTTP-Based Agent Orchestrator

Orchestrates agent services via HTTP calls following A2A protocol.
Replaces direct function calls with HTTP requests to independent agent services.
"""

import os
import httpx
from typing import Dict, Any
from datetime import datetime
from opentelemetry import trace
from core.logging_config import get_logger

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)


class AgentOrchestrator:
    """
    Orchestrator for calling agent services via HTTP using A2A protocol.
    """
    
    def __init__(self):
        """Initialize HTTP client and agent service URLs"""
        # Get agent service URLs from environment
        self.planner_url = os.getenv("PLANNER_SERVICE_URL", "http://localhost:8001")
        self.researcher_url = os.getenv("RESEARCHER_SERVICE_URL", "http://localhost:8002")
        self.writer_url = os.getenv("WRITER_SERVICE_URL", "http://localhost:8003")
        self.reviewer_url = os.getenv("REVIEWER_SERVICE_URL", "http://localhost:8004")
        
        # Create async HTTP client with timeout
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(240.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        
        logger.info(f"🔗 Agent Orchestrator initialized")
        logger.info(f"  Planner: {self.planner_url}")
        logger.info(f"  Researcher: {self.researcher_url}")
        logger.info(f"  Writer: {self.writer_url}")
        logger.info(f"  Reviewer: {self.reviewer_url}")
    
    async def call_planner(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call Planner Agent via HTTP
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with plan
        """
        with tracer.start_as_current_span("orchestrator.call_planner") as span:
            span.set_attribute("thread_id", state.get("thread_id", ""))
            span.set_attribute("topic", state.get("topic", ""))
            
            try:
                logger.info(f"📋 Calling Planner Agent for topic: {state.get('topic')}")
                
                request_payload = {
                    "user_id": state.get("user_id", ""),
                    "topic": state.get("topic", ""),
                    "platform": state.get("platform", "linkedin"),
                    "tone": state.get("tone", "professional"),
                    "thread_id": state.get("thread_id", "")
                }
                
                response = await self.client.post(
                    f"{self.planner_url}/plan",
                    json=request_payload,
                    headers={
                        "X-Thread-ID": state.get("thread_id", ""),
                        "X-User-ID": state.get("user_id", "")
                    }
                )
                response.raise_for_status()
                result = response.json()
                
                logger.info(f"✅ Planner Agent completed successfully")
                
                return {
                    "plan": result.get("plan", ""),
                    "messages": state.get("messages", []) + [{
                        "role": "planner",
                        "content": result.get("plan", ""),
                        "timestamp": datetime.utcnow().isoformat()
                    }]
                }
                
            except httpx.HTTPStatusError as e:
                logger.error(f"❌ Planner Agent HTTP error: {e.response.status_code} - {e.response.text}")
                span.set_attribute("error", True)
                raise Exception(f"Planner service error: {e.response.status_code}")
            except Exception as e:
                logger.error(f"❌ Error calling Planner Agent: {str(e)}")
                span.set_attribute("error", True)
                raise
    
    async def call_researcher(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call Researcher Agent via HTTP
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with research documents
        """
        with tracer.start_as_current_span("orchestrator.call_researcher") as span:
            span.set_attribute("thread_id", state.get("thread_id", ""))
            span.set_attribute("topic", state.get("topic", ""))
            
            try:
                logger.info(f"🔍 Calling Researcher Agent for topic: {state.get('topic')}")
                
                request_payload = {
                    "user_id": state.get("user_id", ""),
                    "topic": state.get("topic", ""),
                    "plan": state.get("plan", ""),
                    "thread_id": state.get("thread_id", ""),
                    "max_results": 5
                }
                
                response = await self.client.post(
                    f"{self.researcher_url}/research",
                    json=request_payload,
                    headers={
                        "X-Thread-ID": state.get("thread_id", ""),
                        "X-User-ID": state.get("user_id", "")
                    }
                )
                response.raise_for_status()
                result = response.json()
                
                documents = result.get("documents", [])
                logger.info(f"✅ Researcher Agent completed: {len(documents)} documents retrieved")
                
                # Create context string from documents
                context = "\n\n---\n\n".join(documents) if documents else ""
                
                return {
                    "context": context,
                    "retrieved_docs": documents,
                    "messages": state.get("messages", []) + [{
                        "role": "researcher",
                        "content": f"Retrieved {len(documents)} documents",
                        "timestamp": datetime.utcnow().isoformat()
                    }]
                }
                
            except httpx.HTTPStatusError as e:
                logger.error(f"❌ Researcher Agent HTTP error: {e.response.status_code} - {e.response.text}")
                span.set_attribute("error", True)
                raise Exception(f"Researcher service error: {e.response.status_code}")
            except Exception as e:
                logger.error(f"❌ Error calling Researcher Agent: {str(e)}")
                span.set_attribute("error", True)
                raise
    
    async def call_writer(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call Writer Agent via HTTP
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with draft content
        """
        with tracer.start_as_current_span("orchestrator.call_writer") as span:
            span.set_attribute("thread_id", state.get("thread_id", ""))
            span.set_attribute("topic", state.get("topic", ""))
            
            try:
                refinement_count = state.get("refinement_count", 0)
                is_refinement = refinement_count > 0
                
                logger.info(f"✍️ Calling Writer Agent for topic: {state.get('topic')} (refinement: {is_refinement})")
                
                request_payload = {
                    "user_id": state.get("user_id", ""),
                    "topic": state.get("topic", ""),
                    "plan": state.get("plan", ""),
                    "research_documents": state.get("retrieved_docs", []),
                    "tone": state.get("tone", "professional"),
                    "platform": state.get("platform", "linkedin"),
                    "thread_id": state.get("thread_id", ""),
                    # Include refinement context if this is a refinement iteration
                    "previous_draft": state.get("draft", "") if is_refinement else None,
                    "feedback": state.get("feedback", "") if is_refinement else None,
                    "refinement_count": refinement_count
                }
                
                response = await self.client.post(
                    f"{self.writer_url}/write",
                    json=request_payload,
                    headers={
                        "X-Thread-ID": state.get("thread_id", ""),
                        "X-User-ID": state.get("user_id", "")
                    }
                )
                response.raise_for_status()
                result = response.json()
                
                logger.info(f"✅ Writer Agent completed successfully")
                
                return {
                    "draft": result.get("draft", ""),
                    "messages": state.get("messages", []) + [{
                        "role": "writer",
                        "content": result.get("draft", ""),
                        "refinement_count": refinement_count,
                        "timestamp": datetime.utcnow().isoformat()
                    }]
                }
                
            except httpx.HTTPStatusError as e:
                logger.error(f"❌ Writer Agent HTTP error: {e.response.status_code} - {e.response.text}")
                span.set_attribute("error", True)
                raise Exception(f"Writer service error: {e.response.status_code}")
            except Exception as e:
                logger.error(f"❌ Error calling Writer Agent: {str(e)}")
                span.set_attribute("error", True)
                raise
    
    async def call_reviewer(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call Reviewer Agent via HTTP
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with final post
        """
        with tracer.start_as_current_span("orchestrator.call_reviewer") as span:
            span.set_attribute("thread_id", state.get("thread_id", ""))
            span.set_attribute("topic", state.get("topic", ""))
            
            try:
                logger.info(f"📝 Calling Reviewer Agent for topic: {state.get('topic')}")
                
                request_payload = {
                    "user_id": state.get("user_id", ""),
                    "topic": state.get("topic", ""),
                    "draft": state.get("draft", ""),
                    "plan": state.get("plan", ""),
                    "platform": state.get("platform", "linkedin"),
                    "thread_id": state.get("thread_id", "")
                }
                
                response = await self.client.post(
                    f"{self.reviewer_url}/review",
                    json=request_payload,
                    headers={
                        "X-Thread-ID": state.get("thread_id", ""),
                        "X-User-ID": state.get("user_id", "")
                    }
                )
                response.raise_for_status()
                result = response.json()
                
                logger.info(f"✅ Reviewer Agent completed successfully")
                
                return {
                    "final_post": result.get("final_post", ""),
                    "scores": result.get("scores", {}),
                    "feedback": result.get("feedback", ""),
                    "needs_refinement": result.get("needs_refinement", False),
                    "messages": state.get("messages", []) + [{
                        "role": "reviewer",
                        "content": result.get("final_post", ""),
                        "scores": result.get("scores", {}),
                        "feedback": result.get("feedback", ""),
                        "timestamp": datetime.utcnow().isoformat()
                    }]
                }
                
            except httpx.HTTPStatusError as e:
                logger.error(f"❌ Reviewer Agent HTTP error: {e.response.status_code} - {e.response.text}")
                span.set_attribute("error", True)
                raise Exception(f"Reviewer service error: {e.response.status_code}")
            except Exception as e:
                logger.error(f"❌ Error calling Reviewer Agent: {str(e)}")
                span.set_attribute("error", True)
                raise
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
        logger.info("🔌 Agent Orchestrator HTTP client closed")
