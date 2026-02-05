"""
Writer Agent Request/Response Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class WriteRequest(BaseModel):
    """Request schema for content writing"""
    user_id: str = Field(..., description="User identifier")
    topic: str = Field(..., description="Content topic")
    plan: Optional[str] = Field(default="", description="Content plan from planner")
    research_documents: List[str] = Field(default_factory=list, description="Documents from researcher")
    tone: Optional[str] = Field(default="professional", description="Desired tone")
    platform: str = Field(default="linkedin", description="Target platform")
    thread_id: str = Field(..., description="Thread/conversation ID")
    # Refinement fields
    previous_draft: Optional[str] = Field(default=None, description="Previous draft for refinement")
    feedback: Optional[str] = Field(default=None, description="Reviewer feedback for refinement")
    refinement_count: int = Field(default=0, description="Current refinement iteration")
    metadata: Optional[dict] = Field(default=None, description="Additional metadata")


class WriteResponse(BaseModel):
    """Response schema for content writing"""
    draft: str = Field(..., description="Generated draft content")
    agent: str = Field(default="writer", description="Agent identifier")
    thread_id: str = Field(..., description="Thread/conversation ID")
    status: str = Field(default="success", description="Response status")
