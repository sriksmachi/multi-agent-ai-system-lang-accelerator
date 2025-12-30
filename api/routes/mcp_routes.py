"""
Model Context Protocol (MCP) routes for FastAPI.

Implements MCP-compliant endpoints:
- GET /mcp/tools: List available tools
- POST /mcp/invoke: Invoke tool (streaming or non-streaming)
"""

import json
import logging
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from api.schemas.mcp_schemas import (
    MCPToolsListResponse,
    MCPTool,
    MCPToolParameter,
    MCPToolCallRequest,
    MCPToolCallResponse,
    MCPStreamChunk,
    MCPErrorResponse,
)
from workflows import run_post_generator

# Initialize logger and tracer
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# Create router
router = APIRouter(prefix="/mcp", tags=["MCP Protocol"])


# ============================================================================
# MCP TOOLS REGISTRY
# ============================================================================

MCP_TOOLS = [
    MCPTool(
        name="generate_linkedin_post",
        description=(
            "Generate a professional LinkedIn post using a multi-agent system. "
            "The system uses planner, researcher, writer, and reviewer agents to "
            "create high-quality, fact-checked content optimized for LinkedIn."
        ),
        parameters=[
            MCPToolParameter(
                name="topic",
                type="string",
                description="Topic or query for the LinkedIn post",
                required=True,
            ),
            MCPToolParameter(
                name="platform",
                type="string",
                description="Target platform (default: 'linkedin')",
                required=False,
                enum=["linkedin"],
            ),
        ],
        streaming=True,
    ),
]


# ============================================================================
# MCP ENDPOINTS
# ============================================================================

@router.get(
    "/tools",
    response_model=MCPToolsListResponse,
    summary="List MCP Tools",
    description="Get list of available MCP tools with their parameters and capabilities",
    responses={
        200: {
            "description": "List of available MCP tools",
            "content": {
                "application/json": {
                    "example": {
                        "protocol": "mcp-streamable-1.0",
                        "tools": [
                            {
                                "name": "generate_linkedin_post",
                                "description": "Generate a professional LinkedIn post",
                                "parameters": [
                                    {
                                        "name": "topic",
                                        "type": "string",
                                        "description": "Topic for the post",
                                        "required": True,
                                    }
                                ],
                                "streaming": True,
                            }
                        ],
                        "timestamp": "2025-12-23T10:00:00Z",
                    }
                }
            },
        }
    },
)
async def list_mcp_tools():
    """
    List all available MCP tools.
    
    Returns:
        MCPToolsListResponse: List of tools with their specifications
    """
    with tracer.start_as_current_span(
        "mcp.list_tools",
        attributes={
            "mcp.protocol": "mcp-streamable-1.0",
            "mcp.tool_count": len(MCP_TOOLS),
        }
    ) as span:
        logger.info(f"MCP: Listing {len(MCP_TOOLS)} available tools")
        span.add_event("mcp.tools_listed", {"tool_count": len(MCP_TOOLS)})
        
        return MCPToolsListResponse(tools=MCP_TOOLS)


@router.post(
    "/tools/call",
    response_model=None,
    tags=["MCP Protocol"],
    description="Invoke an MCP tool with optional streaming support",
    responses={
        200: {
            "description": "Tool execution result (streaming or non-streaming)",
            "content": {
                "application/json": {
                    "example": {
                        "protocol": "mcp-streamable-1.0",
                        "tool": "generate_linkedin_post",
                        "result": {
                            "post_markdown": "# Amazing Post\n\nContent here...",
                            "platform": "linkedin",
                            "trace_id": "abc123",
                        },
                        "user_id": "user_123",
                        "trace_id": "abc123",
                        "timestamp": "2025-12-23T10:00:00Z",
                    }
                },
                "text/event-stream": {
                    "example": 'data: {"protocol":"mcp-streamable-1.0","tool":"generate_linkedin_post","chunk_type":"content","content":"# Post Title\\n","timestamp":"2025-12-23T10:00:00Z"}\n\n'
                },
            },
        },
        400: {"description": "Invalid request or unknown tool"},
        500: {"description": "Tool execution failed"},
    },
    openapi_extra={
        "x-ms-agentic-protocol": "mcp-streamable-1.0",
    },
)
async def invoke_mcp_tool(request: MCPToolCallRequest):
    """
    Invoke an MCP tool.
    
    Supports both streaming and non-streaming modes:
    - Non-streaming: Returns complete result as JSON
    - Streaming: Returns Server-Sent Events (SSE) with partial results
    
    Args:
        request: MCPToolCallRequest with tool name, parameters, and options
        
    Returns:
        StreamingResponse (if stream=True) or MCPToolCallResponse (if stream=False)
        
    Raises:
        HTTPException: If tool not found or execution fails
    """
    tool_name = request.tool
    user_id = request.user_id
    thread_id = request.thread_id or f"thread_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    with tracer.start_as_current_span(
        "mcp.invoke_tool",
        attributes={
            "mcp.protocol": "mcp-streamable-1.0",
            "mcp.tool": tool_name,
            "mcp.user_id": user_id,
            "mcp.thread_id": thread_id,
            "mcp.streaming": request.stream,
        }
    ) as span:
        # Validate tool exists
        tool = next((t for t in MCP_TOOLS if t.name == tool_name), None)
        if not tool:
            span.set_status(Status(StatusCode.ERROR, f"Unknown tool: {tool_name}"))
            logger.error(f"MCP: Unknown tool requested: {tool_name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown tool: {tool_name}. Use GET /mcp/tools to list available tools.",
            )
        
        logger.info(
            f"MCP: Invoking tool '{tool_name}' for user '{user_id}' (streaming={request.stream})",
            extra={
                "mcp.tool": tool_name,
                "mcp.user_id": user_id,
                "mcp.thread_id": thread_id,
                "mcp.parameters": request.parameters,
            }
        )
        
        span.add_event("mcp.tool_invoked", {
            "tool": tool_name,
            "user_id": user_id,
            "parameters": json.dumps(request.parameters),
        })
        
        # Route to appropriate tool handler
        if tool_name == "generate_linkedin_post":
            if request.stream:
                return StreamingResponse(
                    _generate_post_streaming(request, span),
                    media_type="text/event-stream",
                )
            else:
                return await _generate_post_non_streaming(request, span)
        else:
            # Should never reach here due to validation above
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Tool handler not implemented",
            )


# ============================================================================
# TOOL HANDLERS
# ============================================================================

async def _generate_post_non_streaming(
    request: MCPToolCallRequest,
    parent_span: trace.Span,
) -> MCPToolCallResponse:
    """
    Handle non-streaming post generation.
    
    Args:
        request: MCP tool call request
        parent_span: Parent OpenTelemetry span
        
    Returns:
        MCPToolCallResponse with complete result
        
    Raises:
        HTTPException: If generation fails
    """
    try:
        topic = request.parameters.get("topic")
        if not topic:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required parameter: 'topic'",
            )
        
        platform = request.parameters.get("platform", "linkedin")
        
        # Run workflow (non-streaming)
        result = run_post_generator(
            user_id=request.user_id,
            topic=topic,
            thread_id=request.thread_id,
            stream=False,
        )
        
        # Build MCP response
        response = MCPToolCallResponse(
            tool=request.tool,
            result=result,
            user_id=request.user_id,
            thread_id=request.thread_id,
            trace_id=result.get("trace_id", ""),
        )
        
        parent_span.set_attribute("mcp.success", True)
        parent_span.set_attribute("mcp.trace_id", response.trace_id)
        parent_span.add_event("mcp.tool_completed", {
            "trace_id": response.trace_id,
            "result_size": len(json.dumps(response.result)),
        })
        
        logger.info(f"MCP: Tool '{request.tool}' completed successfully (non-streaming)")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        parent_span.set_status(Status(StatusCode.ERROR, str(e)))
        parent_span.record_exception(e)
        logger.error(f"MCP: Tool execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tool execution failed: {str(e)}",
        )


async def _generate_post_streaming(
    request: MCPToolCallRequest,
    parent_span: trace.Span,
) -> AsyncGenerator[str, None]:
    """
    Handle streaming post generation.
    
    Yields Server-Sent Events (SSE) in MCP format:
    - Start chunk: Indicates stream start
    - Content chunks: Partial post content
    - Metadata chunks: Additional information (scores, trace_id, etc.)
    - End chunk: Indicates completion
    - Error chunk: On failure
    
    Args:
        request: MCP tool call request
        parent_span: Parent OpenTelemetry span
        
    Yields:
        SSE-formatted strings with MCP chunks
    """
    try:
        topic = request.parameters.get("topic")
        if not topic:
            error_chunk = MCPStreamChunk(
                tool=request.tool,
                chunk_type="error",
                error="Missing required parameter: 'topic'",
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"
            return
        
        platform = request.parameters.get("platform", "linkedin")
        
        # Send start chunk
        start_chunk = MCPStreamChunk(
            tool=request.tool,
            chunk_type="start",
            metadata={
                "user_id": request.user_id,
                "thread_id": request.thread_id,
                "topic": topic,
                "platform": platform,
            },
        )
        yield f"data: {start_chunk.model_dump_json()}\n\n"
        
        parent_span.add_event("mcp.stream_started")
        logger.info(f"MCP: Starting streaming generation for tool '{request.tool}'")
        
        # Run workflow (streaming mode)
        accumulated_content = ""
        final_metadata = {}
        
        async for chunk in run_post_generator(
            user_id=request.user_id,
            topic=topic,
            thread_id=request.thread_id,
            stream=True,
        ):
            # Parse SSE chunk from workflow
            if chunk.startswith("data: "):
                try:
                    data = json.loads(chunk[6:])  # Remove "data: " prefix
                    
                    # Extract content or metadata
                    if "content" in data:
                        content = data["content"]
                        accumulated_content += content
                        
                        # Send content chunk
                        content_chunk = MCPStreamChunk(
                            tool=request.tool,
                            chunk_type="content",
                            content=content,
                        )
                        yield f"data: {content_chunk.model_dump_json()}\n\n"
                    
                    if "metadata" in data:
                        final_metadata.update(data["metadata"])
                    
                except json.JSONDecodeError:
                    logger.warning(f"MCP: Failed to parse workflow chunk: {chunk}")
                    continue
        
        # Send metadata chunk with final information
        metadata_chunk = MCPStreamChunk(
            tool=request.tool,
            chunk_type="metadata",
            metadata={
                "content_length": len(accumulated_content),
                **final_metadata,
            },
        )
        yield f"data: {metadata_chunk.model_dump_json()}\n\n"
        
        # Send end chunk
        end_chunk = MCPStreamChunk(
            tool=request.tool,
            chunk_type="end",
            metadata={"status": "completed"},
        )
        yield f"data: {end_chunk.model_dump_json()}\n\n"
        
        parent_span.set_attribute("mcp.success", True)
        parent_span.add_event("mcp.stream_completed", {
            "content_length": len(accumulated_content),
        })
        
        logger.info(f"MCP: Streaming generation completed for tool '{request.tool}'")
        
    except Exception as e:
        parent_span.set_status(Status(StatusCode.ERROR, str(e)))
        parent_span.record_exception(e)
        logger.error(f"MCP: Streaming generation failed: {e}", exc_info=True)
        
        # Send error chunk
        error_chunk = MCPStreamChunk(
            tool=request.tool,
            chunk_type="error",
            error=str(e),
        )
        yield f"data: {error_chunk.model_dump_json()}\n\n"
