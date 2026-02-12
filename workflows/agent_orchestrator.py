"""
HTTP-Based Agent Orchestrator with A2A Protocol Support

Orchestrates agent services via HTTP calls following A2A protocol.
Supports dynamic agent discovery via /.well-known/agent.json endpoints.
"""

import os
import httpx
from typing import Dict, Any, Optional
from datetime import datetime
from opentelemetry import trace
from opentelemetry.propagate import inject
from core.logging_config import get_logger
from core.a2a_client import A2AClient, get_agent_url, AgentCard

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)


class AgentOrchestrator:
    """
    Orchestrator for calling agent services via HTTP using A2A protocol.
    
    Features:
    - A2A agent discovery via /.well-known/agent.json
    - Dynamic endpoint resolution from Agent Cards
    - Distributed tracing with OpenTelemetry
    - Automatic retry with fresh discovery on failures
    """
    
    def __init__(self, use_a2a_discovery: bool = True):
        """
        Initialize HTTP client and agent service URLs.
        
        Args:
            use_a2a_discovery: If True, discover agents via A2A protocol.
                               If False, use direct HTTP calls (legacy mode).
        """
        self.use_a2a_discovery = use_a2a_discovery
        
        # Get agent service URLs from environment (A2A URLs take precedence)
        self.planner_url = get_agent_url("planner") or os.getenv("PLANNER_SERVICE_URL", "http://localhost:8001")
        self.researcher_url = get_agent_url("researcher") or os.getenv("RESEARCHER_SERVICE_URL", "http://localhost:8002")
        self.writer_url = get_agent_url("writer") or os.getenv("WRITER_SERVICE_URL", "http://localhost:8003")
        self.reviewer_url = get_agent_url("reviewer") or os.getenv("REVIEWER_SERVICE_URL", "http://localhost:8004")
        
        # Create async HTTP client with timeout and redirect handling
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(240.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            follow_redirects=True  # Handle HTTP -> HTTPS redirects in Azure Container Apps
        )
        
        # A2A client for agent discovery
        self.a2a_client: Optional[A2AClient] = None
        self._discovered_agents: Dict[str, AgentCard] = {}
        
        logger.info(f"🔗 Agent Orchestrator initialized (A2A discovery: {use_a2a_discovery})")
        logger.info(f"  Planner: {self.planner_url}")
        logger.info(f"  Researcher: {self.researcher_url}")
        logger.info(f"  Writer: {self.writer_url}")
        logger.info(f"  Reviewer: {self.reviewer_url}")
    
    async def _ensure_a2a_client(self):
        """Initialize A2A client if needed"""
        if self.a2a_client is None:
            self.a2a_client = A2AClient(timeout=60.0)
    
    async def discover_agent(self, agent_name: str, agent_url: str) -> Optional[AgentCard]:
        """
        Discover an agent via A2A protocol.
        
        Args:
            agent_name: Name of the agent (planner, researcher, etc.)
            agent_url: Base URL of the agent
            
        Returns:
            AgentCard if discovery succeeds, None otherwise
        """
        if not self.use_a2a_discovery:
            return None
            
        await self._ensure_a2a_client()
        
        try:
            card = await self.a2a_client.discover_agent(agent_url)
            self._discovered_agents[agent_name] = card
            logger.info(f"✅ A2A Discovery: {card.name} - Skills: {[s.get('name') for s in card.skills]}")
            return card
        except Exception as e:
            logger.warning(f"⚠️ A2A Discovery failed for {agent_name}: {e}")
            return None
    
    async def discover_all_agents(self):
        """Discover all agents via A2A protocol"""
        agents = [
            ("planner", self.planner_url),
            ("researcher", self.researcher_url),
            ("writer", self.writer_url),
            ("reviewer", self.reviewer_url),
        ]
        
        for agent_name, agent_url in agents:
            await self.discover_agent(agent_name, agent_url)
        
        logger.info(f"🔍 A2A Discovery complete: {len(self._discovered_agents)} agents discovered")
    
    def get_agent_endpoint(self, agent_name: str, skill_name: str, default_endpoint: str) -> str:
        """
        Get the endpoint for a skill from the Agent Card.
        
        Args:
            agent_name: Name of the agent
            skill_name: Name of the skill
            default_endpoint: Fallback endpoint if not discovered
            
        Returns:
            Endpoint path (e.g., "/plan")
        """
        card = self._discovered_agents.get(agent_name)
        if card and card.endpoints:
            return card.endpoints.get(skill_name, default_endpoint)
        return default_endpoint
    
    def _get_trace_headers(self, state: Dict[str, Any]) -> Dict[str, str]:
        """
        Get headers with trace context propagation for distributed tracing.
        
        Args:
            state: Current workflow state
            
        Returns:
            Dictionary of headers including trace context
        """
        headers = {
            "X-Thread-ID": state.get("thread_id", ""),
            "X-User-ID": state.get("user_id", "")
        }
        # Inject W3C trace context (traceparent, tracestate)
        inject(headers)
        return headers
    
    async def call_planner(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call Planner Agent via HTTP with A2A protocol support.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with plan
        """
        with tracer.start_as_current_span("orchestrator.call_planner") as span:
            span.set_attribute("thread_id", state.get("thread_id", ""))
            span.set_attribute("topic", state.get("topic", ""))
            span.set_attribute("a2a.enabled", self.use_a2a_discovery)
            
            try:
                # Discover agent if A2A is enabled and not yet discovered
                if self.use_a2a_discovery and "planner" not in self._discovered_agents:
                    await self.discover_agent("planner", self.planner_url)
                
                logger.info(f"📋 Calling Planner Agent for topic: {state.get('topic')}")
                
                # Get endpoint from Agent Card or use default
                endpoint = self.get_agent_endpoint("planner", "plan", "/plan")
                
                request_payload = {
                    "user_id": state.get("user_id", ""),
                    "topic": state.get("topic", ""),
                    "platform": state.get("platform", "linkedin"),
                    "tone": state.get("tone", "professional"),
                    "thread_id": state.get("thread_id", "")
                }
                
                response = await self.client.post(
                    f"{self.planner_url}{endpoint}",
                    json=request_payload,
                    headers=self._get_trace_headers(state)
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
        Call Researcher Agent via HTTP with A2A protocol support.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with research documents
        """
        with tracer.start_as_current_span("orchestrator.call_researcher") as span:
            span.set_attribute("thread_id", state.get("thread_id", ""))
            span.set_attribute("topic", state.get("topic", ""))
            span.set_attribute("a2a.enabled", self.use_a2a_discovery)
            
            try:
                # Discover agent if A2A is enabled and not yet discovered
                if self.use_a2a_discovery and "researcher" not in self._discovered_agents:
                    await self.discover_agent("researcher", self.researcher_url)
                
                logger.info(f"🔍 Calling Researcher Agent for topic: {state.get('topic')}")
                
                # Get endpoint from Agent Card or use default
                endpoint = self.get_agent_endpoint("researcher", "research", "/research")
                
                request_payload = {
                    "user_id": state.get("user_id", ""),
                    "topic": state.get("topic", ""),
                    "plan": state.get("plan", ""),
                    "thread_id": state.get("thread_id", ""),
                    "max_results": 5
                }
                
                response = await self.client.post(
                    f"{self.researcher_url}{endpoint}",
                    json=request_payload,
                    headers=self._get_trace_headers(state)
                )
                response.raise_for_status()
                result = response.json()
                
                documents = result.get("documents", [])
                retrieved_docs = result.get("retrieved_docs", [])
                logger.info(f"✅ Researcher Agent completed: {len(documents)} documents retrieved")
                
                # Create context string from formatted documents
                context = "\n\n---\n\n".join(documents) if documents else "No relevant documents found for the topic."
                
                return {
                    "context": context,
                    "retrieved_docs": retrieved_docs,
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
        Call Writer Agent via HTTP with A2A protocol support.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with draft content
        """
        with tracer.start_as_current_span("orchestrator.call_writer") as span:
            span.set_attribute("thread_id", state.get("thread_id", ""))
            span.set_attribute("topic", state.get("topic", ""))
            span.set_attribute("a2a.enabled", self.use_a2a_discovery)
            
            try:
                # Discover agent if A2A is enabled and not yet discovered
                if self.use_a2a_discovery and "writer" not in self._discovered_agents:
                    await self.discover_agent("writer", self.writer_url)
                
                refinement_count = state.get("refinement_count", 0)
                is_refinement = refinement_count > 0
                
                logger.info(f"✍️ Calling Writer Agent for topic: {state.get('topic')} (refinement: {is_refinement})")
                
                # Get endpoint from Agent Card or use default
                endpoint = self.get_agent_endpoint("writer", "write", "/write")
                
                request_payload = {
                    "user_id": state.get("user_id", ""),
                    "topic": state.get("topic", ""),
                    "plan": state.get("plan", ""),
                    "research_documents": [state.get("context", "")] if state.get("context") else [],
                    "tone": state.get("tone", "professional"),
                    "platform": state.get("platform", "linkedin"),
                    "thread_id": state.get("thread_id", ""),
                    # Include refinement context if this is a refinement iteration
                    "previous_draft": state.get("draft", "") if is_refinement else None,
                    "feedback": state.get("feedback", "") if is_refinement else None,
                    "refinement_count": refinement_count
                }
                
                response = await self.client.post(
                    f"{self.writer_url}{endpoint}",
                    json=request_payload,
                    headers=self._get_trace_headers(state)
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
        Call Reviewer Agent via HTTP with A2A protocol support.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with final post
        """
        with tracer.start_as_current_span("orchestrator.call_reviewer") as span:
            span.set_attribute("thread_id", state.get("thread_id", ""))
            span.set_attribute("topic", state.get("topic", ""))
            span.set_attribute("a2a.enabled", self.use_a2a_discovery)
            
            try:
                # Discover agent if A2A is enabled and not yet discovered
                if self.use_a2a_discovery and "reviewer" not in self._discovered_agents:
                    await self.discover_agent("reviewer", self.reviewer_url)
                
                logger.info(f"📝 Calling Reviewer Agent for topic: {state.get('topic')}")
                
                # Get endpoint from Agent Card or use default
                endpoint = self.get_agent_endpoint("reviewer", "review", "/review")
                
                request_payload = {
                    "user_id": state.get("user_id", ""),
                    "topic": state.get("topic", ""),
                    "draft": state.get("draft", ""),
                    "plan": state.get("plan", ""),
                    "platform": state.get("platform", "linkedin"),
                    "thread_id": state.get("thread_id", "")
                }
                
                response = await self.client.post(
                    f"{self.reviewer_url}{endpoint}",
                    json=request_payload,
                    headers=self._get_trace_headers(state)
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
        """Close HTTP client and A2A client"""
        await self.client.aclose()
        if self.a2a_client:
            await self.a2a_client.close()
        logger.info("🔌 Agent Orchestrator HTTP client closed")
    
    def get_discovered_agents(self) -> Dict[str, AgentCard]:
        """Get all discovered agents"""
        return self._discovered_agents.copy()
    
    async def get_agent_info(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific agent.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Agent info dict or None if not discovered
        """
        card = self._discovered_agents.get(agent_name)
        if card:
            return {
                "name": card.name,
                "description": card.description,
                "version": card.version,
                "skills": [s.get("name") for s in card.skills],
                "endpoints": card.endpoints,
                "capabilities": card.capabilities
            }
        return None
