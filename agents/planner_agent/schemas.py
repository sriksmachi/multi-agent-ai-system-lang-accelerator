"""
Planner Agent Request/Response Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional


class PlanRequest(BaseModel):
    """Request schema for plan generation"""
    user_id: str = Field(..., description="User identifier")
    topic: str = Field(..., description="Topic for the LinkedIn post")
    platform: str = Field(default="linkedin", description="Target platform")
    tone: str = Field(default="professional", description="Desired tone")
    thread_id: str = Field(..., description="Thread/conversation ID")
    metadata: Optional[dict] = Field(default=None, description="Additional metadata")


class PlanResponse(BaseModel):
    """Response schema for plan generation"""
    plan: str = Field(..., description="Generated content plan")
    agent: str = Field(default="planner", description="Agent identifier")
    thread_id: str = Field(..., description="Thread/conversation ID")
    status: str = Field(default="success", description="Response status")
