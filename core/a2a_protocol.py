"""
Agent-to-Agent (A2A) Communication Protocol

Defines standardized request/response formats for inter-agent communication.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class A2ARequest(BaseModel):
    """Standard A2A request format for agent communication"""
    agent_id: str = Field(..., description="Identifier of the requesting agent")
    thread_id: str = Field(..., description="Conversation/workflow thread ID")
    user_id: str = Field(..., description="End user identifier")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="ISO timestamp")
    payload: Dict[str, Any] = Field(..., description="Agent-specific request data")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional context or headers")


class A2AResponse(BaseModel):
    """Standard A2A response format for agent communication"""
    agent_id: str = Field(..., description="Identifier of the responding agent")
    thread_id: str = Field(..., description="Conversation/workflow thread ID")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="ISO timestamp")
    status: str = Field(..., description="Response status: success, error, partial")
    result: Dict[str, Any] = Field(..., description="Agent-specific response data")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional response context")
    error: Optional[str] = Field(default=None, description="Error message if status is error")


class AgentHealthResponse(BaseModel):
    """Standard health check response for agents"""
    agent: str = Field(..., description="Agent name")
    status: str = Field(default="healthy", description="Health status")
    version: str = Field(default="1.0.0", description="Agent version")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
