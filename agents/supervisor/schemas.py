"""
Supervisor Agent Pydantic Schemas

Request/Response models for the Supervisor Agent workflow orchestration.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class GeneratePostRequest(BaseModel):
    """Request schema for generate post workflow"""
    topic: str = Field(..., description="Topic for the LinkedIn post")
    platform: Optional[str] = Field(default="LinkedIn", description="Target platform")
    tone: Optional[str] = Field(default="professional", description="Desired tone")
    user_id: Optional[str] = Field(default="anonymous", description="User identifier")
    thread_id: str = Field(..., description="Thread identifier for tracking")


class AgentStatus(BaseModel):
    """Status of an individual agent in the workflow"""
    status: str = Field(..., description="Agent status: pending, running, completed, failed")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Agent result summary")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class WorkflowStatus(BaseModel):
    """Overall workflow status tracking"""
    thread_id: str = Field(..., description="Thread identifier")
    current_step: Optional[str] = Field(default=None, description="Current workflow step")
    agents: Dict[str, AgentStatus] = Field(default_factory=dict, description="Status per agent")


class GeneratePostResponse(BaseModel):
    """Response schema for generate post workflow"""
    thread_id: str = Field(..., description="Thread identifier")
    status: str = Field(..., description="Overall workflow status: success, error, partial")
    plan: Optional[str] = Field(default=None, description="Generated content plan")
    documents: Optional[List[dict]] = Field(default=None, description="Retrieved research documents")
    draft: Optional[str] = Field(default=None, description="Generated draft content")
    final_content: Optional[str] = Field(default=None, description="Final reviewed content")
    feedback: Optional[str] = Field(default=None, description="Reviewer feedback")
    workflow_status: Optional[WorkflowStatus] = Field(default=None, description="Detailed workflow status")


class DiscoveredAgent(BaseModel):
    """Information about a discovered agent"""
    name: str = Field(..., description="Agent name from Agent Card")
    description: str = Field(..., description="Agent description")
    version: str = Field(..., description="Agent version")
    skills: List[str] = Field(default_factory=list, description="Available skill names")
    healthy: bool = Field(..., description="Current health status")
    url: str = Field(..., description="Agent base URL")


class AgentRegistryResponse(BaseModel):
    """Response for listing discovered agents"""
    discovered_agents: Dict[str, DiscoveredAgent] = Field(default_factory=dict)
    total_count: int = Field(..., description="Total number of discovered agents")
