"""
Reviewer Agent Request/Response Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional


class ReviewRequest(BaseModel):
    """Request schema for content review"""
    user_id: str = Field(..., description="User identifier")
    topic: str = Field(..., description="Content topic")
    draft: str = Field(..., description="Draft content from writer")
    plan: str = Field(..., description="Original content plan")
    platform: str = Field(default="linkedin", description="Target platform")
    thread_id: str = Field(..., description="Thread/conversation ID")
    metadata: Optional[dict] = Field(default=None, description="Additional metadata")


class ReviewResponse(BaseModel):
    """Response schema for content review"""
    final_post: str = Field(..., description="Reviewed and finalized content")
    review_notes: Optional[str] = Field(default=None, description="Review notes or feedback")
    agent: str = Field(default="reviewer", description="Agent identifier")
    thread_id: str = Field(..., description="Thread/conversation ID")
    status: str = Field(default="success", description="Response status")
