"""
Researcher Agent Request/Response Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class ResearchRequest(BaseModel):
    """Request schema for research"""
    user_id: str = Field(..., description="User identifier")
    topic: str = Field(..., description="Research topic")
    plan: str = Field(..., description="Content plan from planner")
    thread_id: str = Field(..., description="Thread/conversation ID")
    max_results: int = Field(default=5, description="Maximum number of results")
    metadata: Optional[dict] = Field(default=None, description="Additional metadata")


class ResearchResponse(BaseModel):
    """Response schema for research"""
    documents: List[str] = Field(..., description="Retrieved documents as formatted strings")
    retrieved_docs: List[dict] = Field(default_factory=list, description="Raw retrieved document metadata")
    document_count: int = Field(..., description="Number of documents retrieved")
    agent: str = Field(default="researcher", description="Agent identifier")
    thread_id: str = Field(..., description="Thread/conversation ID")
    status: str = Field(default="success", description="Response status")
