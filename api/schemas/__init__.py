
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
    post: str = Field(..., description="Generated social media post content")
    platform: str = Field(..., description="Target platform for the post")
    
class ErrorResponse(BaseModel):
    """Standard error response schema."""
    error: str = Field(..., description="Error type or code")
    message: str = Field(..., description="Detailed error message")
    detail: Optional[str] = Field(None, description="Additional error details")