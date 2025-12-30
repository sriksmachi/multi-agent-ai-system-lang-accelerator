"""
FastMCP-based MCP server implementation.

This provides a simplified MCP server using the FastMCP library,
which automatically handles MCP protocol compliance and streaming.
"""

import logging
from typing import Optional
from datetime import datetime

from fastmcp import FastMCP
from opentelemetry import trace

from workflows import run_post_generator

# Initialize logger and tracer
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# Create FastMCP server
mcp = FastMCP("LinkedIn Post Generator")

@mcp.tool()
async def generate_linkedin_post(
    topic: str,
    user_id: Optional[str] = None,
) -> str:
    """
    Generate a professional LinkedIn post using a multi-agent system.
    
    The system uses planner, researcher, writer, and reviewer agents to
    create high-quality, fact-checked content optimized for LinkedIn.
    
    Args:
        topic: Topic or query for the LinkedIn post
        user_id: Optional user identifier for tracking
        
    Returns:
        Generated LinkedIn post content
    """
    # Generate user_id if not provided
    if not user_id:
        user_id = f"mcp-user-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    thread_id = f"thread_{user_id}_{datetime.now().strftime('%Y%m%d')}"
    
    logger.info(f"[{user_id}] FastMCP: Generating LinkedIn post for topic: {topic}")
    
    with tracer.start_as_current_span(
        "fastmcp_generate_linkedin_post",
        attributes={
            "user_id": user_id,
            "topic": topic,
            "tool": "generate_linkedin_post",
        }
    ) as span:
        try:
            # Run the workflow (non-streaming)
            result = run_post_generator(
                user_id=user_id,
                topic=topic,
                thread_id=thread_id,
                stream=False
            )
            
            span.set_attribute("success", True)
            span.set_attribute("post_length", len(result.get("post", "")))
            
            logger.info(f"[{user_id}] FastMCP: Post generation completed")
            
            return result.get("post", result.get("post_markdown", ""))
            
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            span.record_exception(e)
            logger.error(f"[{user_id}] FastMCP: Error generating post: {e}", exc_info=True)
            raise


@mcp.tool()
async def generate_linkedin_post_streaming(
    topic: str,
    user_id: Optional[str] = None,
):
    """
    Generate a professional LinkedIn post with streaming response.
    
    Streams the post generation process in real-time, allowing you to see
    content as it's being created by the multi-agent system.
    
    Args:
        topic: Topic or query for the LinkedIn post
        user_id: Optional user identifier for tracking
        
    Yields:
        Chunks of the generated post as they're created
    """
    # Generate user_id if not provided
    if not user_id:
        user_id = f"mcp-user-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    thread_id = f"thread_{user_id}_{datetime.now().strftime('%Y%m%d')}"
    
    logger.info(f"[{user_id}] FastMCP: Streaming LinkedIn post for topic: {topic}")
    
    with tracer.start_as_current_span(
        "fastmcp_generate_linkedin_post_streaming",
        attributes={
            "user_id": user_id,
            "topic": topic,
            "tool": "generate_linkedin_post_streaming",
            "streaming": True,
        }
    ) as span:
        try:
            # Run the workflow in streaming mode
            async for chunk in run_post_generator(
                user_id=user_id,
                topic=topic,
                thread_id=thread_id,
                stream=True
            ):
                # Extract content from SSE format
                if chunk.startswith("data: "):
                    import json
                    try:
                        chunk_data = json.loads(chunk[6:])
                        if chunk_data.get("chunk_type") == "content":
                            yield chunk_data.get("content", "")
                    except json.JSONDecodeError:
                        pass
            
            span.set_attribute("success", True)
            logger.info(f"[{user_id}] FastMCP: Streaming completed")
            
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            span.record_exception(e)
            logger.error(f"[{user_id}] FastMCP: Error streaming post: {e}", exc_info=True)
            raise


# Export the FastMCP instance and app
__all__ = ["mcp"]
