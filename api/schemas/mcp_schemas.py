"""
Model Context Protocol (MCP) schemas for FastAPI.

MCP Protocol Specification:
- Tool-based interface for AI agents
- Streaming support for partial responses
- Standard message format for interoperability
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


class MCPToolParameter(BaseModel):
    """MCP tool parameter definition."""
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type (string, number, boolean, object, array)")
    description: str = Field(..., description="Parameter description")
    required: bool = Field(default=False, description="Whether parameter is required")
    enum: Optional[List[str]] = Field(None, description="Allowed values for enum parameters")


class MCPTool(BaseModel):
    """MCP tool definition."""
    name: str = Field(..., description="Tool identifier")
    description: str = Field(..., description="Tool description for AI agent")
    parameters: List[MCPToolParameter] = Field(default_factory=list, description="Tool parameters")
    streaming: bool = Field(default=False, description="Whether tool supports streaming responses")


class MCPToolsListResponse(BaseModel):
    """Response for listing available MCP tools."""
    protocol: str = Field(default="mcp-streamable-1.0", description="MCP protocol version")
    tools: List[MCPTool] = Field(..., description="Available tools")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class MCPMessage(BaseModel):
    """MCP message format."""
    role: Literal["user", "assistant", "system"] = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = Field(None, description="Message timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional message metadata")


class MCPToolCallRequest(BaseModel):
    """MCP tool invocation request."""
    tool: str = Field(..., description="Tool name to invoke")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    user_id: str = Field(..., description="User identifier for context and tracing")
    thread_id: Optional[str] = Field(None, description="Thread ID for conversation continuity")
    stream: bool = Field(default=False, description="Enable streaming response")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional request metadata")


class MCPToolCallResponse(BaseModel):
    """MCP tool invocation response (non-streaming)."""
    protocol: str = Field(default="mcp-streamable-1.0", description="MCP protocol version")
    tool: str = Field(..., description="Tool name that was invoked")
    result: Dict[str, Any] = Field(..., description="Tool execution result")
    user_id: str = Field(..., description="User identifier")
    thread_id: Optional[str] = Field(None, description="Thread ID")
    trace_id: str = Field(..., description="OpenTelemetry trace ID for debugging")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional response metadata")


class MCPStreamChunk(BaseModel):
    """MCP streaming response chunk."""
    protocol: str = Field(default="mcp-streamable-1.0", description="MCP protocol version")
    tool: str = Field(..., description="Tool name")
    chunk_type: Literal["start", "content", "metadata", "end", "error"] = Field(
        ..., description="Type of stream chunk"
    )
    content: Optional[str] = Field(None, description="Partial content for 'content' chunks")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata for 'metadata' chunks")
    error: Optional[str] = Field(None, description="Error message for 'error' chunks")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class MCPErrorResponse(BaseModel):
    """MCP error response."""
    protocol: str = Field(default="mcp-streamable-1.0", description="MCP protocol version")
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
