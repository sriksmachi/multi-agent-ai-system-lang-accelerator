"""
Standard MCP (Model Context Protocol) JSON-RPC 2.0 schemas.
Following the official MCP specification.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal, Union
from datetime import datetime


# JSON-RPC 2.0 Base Classes
class JsonRpcRequest(BaseModel):
    """JSON-RPC 2.0 request."""
    jsonrpc: Literal["2.0"] = "2.0"
    id: Optional[Union[str, int]] = None
    method: str
    params: Optional[Dict[str, Any]] = None


class JsonRpcResponse(BaseModel):
    """JSON-RPC 2.0 successful response."""
    jsonrpc: Literal["2.0"] = "2.0"
    id: Optional[Union[str, int]] = None
    result: Any


class JsonRpcError(BaseModel):
    """JSON-RPC 2.0 error object."""
    code: int
    message: str
    data: Optional[Any] = None


class JsonRpcErrorResponse(BaseModel):
    """JSON-RPC 2.0 error response."""
    jsonrpc: Literal["2.0"] = "2.0"
    id: Optional[Union[str, int]] = None
    error: JsonRpcError


# MCP Protocol Constants
class ErrorCodes:
    """Standard JSON-RPC and MCP error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


# MCP Initialize
class InitializeParams(BaseModel):
    """Parameters for initialize method."""
    protocolVersion: str
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    clientInfo: Dict[str, str] = Field(default_factory=dict)


class ServerCapabilities(BaseModel):
    """Server capabilities."""
    tools: Optional[Dict[str, Any]] = Field(default_factory=lambda: {"listChanged": True})
    prompts: Optional[Dict[str, Any]] = None
    resources: Optional[Dict[str, Any]] = None
    logging: Optional[Dict[str, Any]] = None


class ServerInfo(BaseModel):
    """Server information."""
    name: str
    version: str


class InitializeResult(BaseModel):
    """Result of initialize method."""
    protocolVersion: str
    capabilities: ServerCapabilities
    serverInfo: ServerInfo


# MCP Tools
class ToolParameter(BaseModel):
    """Tool parameter definition."""
    name: str
    type: str
    description: str
    required: bool = False


class Tool(BaseModel):
    """MCP Tool definition."""
    name: str
    description: str
    inputSchema: Dict[str, Any]


class ListToolsResult(BaseModel):
    """Result of tools/list method."""
    tools: List[Tool]


class CallToolParams(BaseModel):
    """Parameters for tools/call method."""
    name: str
    arguments: Optional[Dict[str, Any]] = None


class ToolContent(BaseModel):
    """Tool response content."""
    type: Literal["text", "image", "resource"] = "text"
    text: Optional[str] = None
    data: Optional[str] = None
    mimeType: Optional[str] = None


class CallToolResult(BaseModel):
    """Result of tools/call method."""
    content: List[ToolContent]
    isError: bool = False


# Notifications
class ProgressNotification(BaseModel):
    """Progress notification."""
    method: Literal["notifications/progress"] = "notifications/progress"
    params: Dict[str, Any]


class LogNotification(BaseModel):
    """Log notification."""
    method: Literal["notifications/message"] = "notifications/message"
    params: Dict[str, Any]
