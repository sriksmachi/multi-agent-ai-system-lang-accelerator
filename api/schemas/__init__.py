
from pydantic import BaseModel, Field
from typing import Optional

class HealthResponse(BaseModel):
    """Response schema for health check endpoint."""
    status: str = Field(..., description="Health status of the API")
    message: Optional[str] = Field(None, description="Additional health information")
    version: str = Field(..., description="API version")

class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""
    user_id: str = Field(..., description="User identifier")
    query: str = Field(..., description="User query or topic for post generation")
    
class GeneratePostResponse(BaseModel):
    """Response schema for generated social media post."""
    post_markdown: str = Field(..., description="Generated social media post content in markdown")
    platform: str = Field(..., description="Target platform for the post")
    scores: dict = Field(default_factory=dict, description="Quality evaluation scores")
    refinement_count: int = Field(default=0, description="Number of refinement iterations")
    trace_id: str = Field(..., description="OpenTelemetry trace ID for debugging")
    conversation_id: str = Field(..., description="Conversation identifier")
    
class ErrorResponse(BaseModel):
    """Standard error response schema."""
    error: str = Field(..., description="Error type or code")
    message: str = Field(..., description="Detailed error message")
    detail: Optional[str] = Field(None, description="Additional error details")


# Import MCP schemas
from .mcp_schemas import (
    MCPToolParameter,
    MCPTool,
    MCPToolsListResponse,
    MCPMessage,
    MCPToolCallRequest,
    MCPToolCallResponse,
    MCPStreamChunk,
    MCPErrorResponse,
)

__all__ = [
    "HealthResponse",
    "ChatRequest",
    "GeneratePostResponse",
    "ErrorResponse",
    "MCPToolParameter",
    "MCPTool",
    "MCPToolsListResponse",
    "MCPMessage",
    "MCPToolCallRequest",
    "MCPToolCallResponse",
    "MCPStreamChunk",
    "MCPErrorResponse",
]