"""
A2A Protocol Client for Agent-to-Agent Communication

Provides discovery and communication capabilities for agents using the A2A protocol.
Agents can discover each other via /.well-known/agent.json and call skills dynamically.
"""

import os
import httpx
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field
from core.logging_config import get_logger

logger = get_logger(__name__)


class AgentCard(BaseModel):
    """A2A Agent Card schema - describes agent capabilities"""
    name: str = Field(..., description="Human-readable agent name")
    description: str = Field(..., description="What the agent does")
    version: str = Field(..., description="Agent version")
    protocol: str = Field(default="a2a", description="Protocol identifier")
    capabilities: Dict[str, bool] = Field(default_factory=dict, description="Agent capabilities")
    skills: List[Dict[str, Any]] = Field(default_factory=list, description="Available skills")
    endpoints: Dict[str, str] = Field(default_factory=dict, description="Endpoint mappings")


class A2AClient:
    """
    Client for A2A protocol communication between agents.
    
    Supports:
    - Agent discovery via /.well-known/agent.json
    - Dynamic skill invocation based on Agent Cards
    - Health checking
    - Connection pooling and retry logic
    """
    
    def __init__(self, timeout: float = 30.0):
        """
        Initialize A2A client.
        
        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout
        self._agent_cards: Dict[str, AgentCard] = {}
        self._client = httpx.AsyncClient(timeout=timeout)
    
    async def discover_agent(self, agent_base_url: str) -> AgentCard:
        """
        Discover an agent by fetching its Agent Card.
        
        The A2A protocol requires agents to expose their capabilities
        at /.well-known/agent.json endpoint.
        
        Args:
            agent_base_url: Base URL of the agent (e.g., http://reviewer-agent:8004)
            
        Returns:
            AgentCard with agent capabilities and endpoints
            
        Raises:
            httpx.HTTPError: If discovery fails
        """
        discovery_url = f"{agent_base_url}/.well-known/agent.json"
        
        try:
            response = await self._client.get(discovery_url)
            response.raise_for_status()
            card_data = response.json()
            agent_card = AgentCard(**card_data)
            
            # Cache the agent card
            self._agent_cards[agent_base_url] = agent_card
            
            logger.info(f"✅ Discovered agent: {agent_card.name} at {agent_base_url}")
            logger.debug(f"   Skills: {[s.get('name') for s in agent_card.skills]}")
            return agent_card
            
        except httpx.HTTPError as e:
            logger.error(f"❌ Failed to discover agent at {agent_base_url}: {e}")
            raise
    
    async def call_skill(
        self,
        agent_base_url: str,
        skill_name: str,
        payload: Dict[str, Any],
        discover_first: bool = True
    ) -> Dict[str, Any]:
        """
        Call a skill on a remote agent using A2A protocol.
        
        Args:
            agent_base_url: Base URL of the target agent
            skill_name: Name of the skill to invoke
            payload: Input data for the skill
            discover_first: Whether to discover the agent first (recommended)
            
        Returns:
            Response from the agent skill
            
        Raises:
            ValueError: If skill not found in agent card
            httpx.HTTPError: If skill call fails
        """
        # Discover agent if not cached
        if discover_first and agent_base_url not in self._agent_cards:
            await self.discover_agent(agent_base_url)
        
        agent_card = self._agent_cards.get(agent_base_url)
        
        if agent_card:
            # Get endpoint from agent card
            endpoint = agent_card.endpoints.get(skill_name)
            if not endpoint:
                raise ValueError(f"Skill '{skill_name}' not found in agent card for {agent_card.name}")
        else:
            # Fallback to skill name as endpoint
            endpoint = f"/{skill_name}"
        
        skill_url = f"{agent_base_url}{endpoint}"
        
        try:
            agent_name = agent_card.name if agent_card else agent_base_url
            logger.info(f"🔗 Calling skill '{skill_name}' on {agent_name}")
            
            response = await self._client.post(skill_url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"✅ Skill '{skill_name}' completed successfully")
            return result
            
        except httpx.HTTPError as e:
            logger.error(f"❌ Failed to call skill '{skill_name}' on {agent_base_url}: {e}")
            raise
    
    async def check_health(self, agent_base_url: str) -> bool:
        """
        Check if an agent is healthy.
        
        Args:
            agent_base_url: Base URL of the agent
            
        Returns:
            True if agent is healthy, False otherwise
        """
        try:
            response = await self._client.get(f"{agent_base_url}/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False
    
    def get_cached_card(self, agent_base_url: str) -> Optional[AgentCard]:
        """Get cached agent card if available."""
        return self._agent_cards.get(agent_base_url)
    
    def clear_cache(self, agent_base_url: Optional[str] = None):
        """Clear agent card cache."""
        if agent_base_url:
            self._agent_cards.pop(agent_base_url, None)
        else:
            self._agent_cards.clear()
    
    async def close(self):
        """Close the HTTP client and release resources."""
        await self._client.aclose()


# =============================================================================
# Agent Registry - Maps agent names to URLs
# =============================================================================

AGENT_REGISTRY = {
    "planner": "http://planner-agent:8001",
    "researcher": "http://researcher-agent:8002",
    "writer": "http://writer-agent:8003",
    "reviewer": "http://reviewer-agent:8004",
}


def get_agent_url(agent_name: str) -> str:
    """
    Get agent URL from environment variable or registry.
    
    Environment variables take precedence over the default registry.
    Format: {AGENT_NAME}_AGENT_URL (e.g., PLANNER_AGENT_URL)
    
    Args:
        agent_name: Name of the agent (planner, researcher, writer, reviewer)
        
    Returns:
        Agent URL string, or empty string if not found
    """
    env_key = f"{agent_name.upper()}_AGENT_URL"
    return os.environ.get(env_key, AGENT_REGISTRY.get(agent_name, ""))


def get_all_agent_urls() -> Dict[str, str]:
    """
    Get all agent URLs from environment or registry.
    
    Returns:
        Dictionary mapping agent names to URLs
    """
    return {
        agent_name: get_agent_url(agent_name)
        for agent_name in AGENT_REGISTRY.keys()
    }
