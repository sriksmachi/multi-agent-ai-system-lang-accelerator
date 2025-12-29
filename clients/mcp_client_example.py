"""
Example MCP client demonstrating how to interact with the MCP Server.

This client shows both streaming and non-streaming usage patterns.
"""

import asyncio
import httpx
import json
from typing import AsyncGenerator


class MCPClient:
    """Simple MCP client for testing."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.mcp_url = f"{base_url}/mcp"
    
    async def list_tools(self) -> dict:
        """List available MCP tools."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.mcp_url}/tools")
            response.raise_for_status()
            return response.json()
    
    async def invoke_tool(
        self,
        tool_name: str,
        parameters: dict,
        user_id: str,
        stream: bool = False,
    ):
        """
        Invoke an MCP tool.
        
        Args:
            tool_name: Name of the tool to invoke
            parameters: Tool parameters
            user_id: User identifier
            stream: Enable streaming response
            
        Returns:
            Complete result (if stream=False) or async generator (if stream=True)
        """
        request_body = {
            "tool": tool_name,
            "parameters": parameters,
            "user_id": user_id,
            "stream": stream,
        }
        
        if stream:
            return self._invoke_streaming(request_body)
        else:
            return await self._invoke_non_streaming(request_body)
    
    async def _invoke_non_streaming(self, request_body: dict) -> dict:
        """Invoke tool and get complete response."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.mcp_url}/invoke",
                json=request_body,
            )
            response.raise_for_status()
            return response.json()
    
    async def _invoke_streaming(self, request_body: dict) -> AsyncGenerator[dict, None]:
        """Invoke tool and stream response chunks."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self.mcp_url}/invoke",
                json=request_body,
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            chunk = json.loads(line[6:])  # Remove "data: " prefix
                            yield chunk
                        except json.JSONDecodeError:
                            continue


async def example_list_tools():
    """Example: List available MCP tools."""
    print("=" * 60)
    print("Example 1: List MCP Tools")
    print("=" * 60)
    
    client = MCPClient()
    tools = await client.list_tools()
    
    print(f"\nProtocol: {tools['protocol']}")
    print(f"Available tools: {len(tools['tools'])}\n")
    
    for tool in tools['tools']:
        print(f"Tool: {tool['name']}")
        print(f"  Description: {tool['description']}")
        print(f"  Streaming: {tool['streaming']}")
        print(f"  Parameters:")
        for param in tool['parameters']:
            required = " (required)" if param['required'] else ""
            print(f"    - {param['name']}: {param['type']}{required}")
            print(f"      {param['description']}")
        print()


async def example_non_streaming():
    """Example: Non-streaming tool invocation."""
    print("=" * 60)
    print("Example 2: Non-Streaming Invocation")
    print("=" * 60)
    
    client = MCPClient()
    
    print("\nInvoking tool 'generate_linkedin_post' (non-streaming)...")
    print("Topic: 'The future of AI in healthcare'\n")
    
    result = await client.invoke_tool(
        tool_name="generate_linkedin_post",
        parameters={"topic": "The future of AI in healthcare"},
        user_id="example_user_123",
        stream=False,
    )
    
    print(f"Protocol: {result['protocol']}")
    print(f"Tool: {result['tool']}")
    print(f"User ID: {result['user_id']}")
    print(f"Trace ID: {result['trace_id']}")
    print(f"\nGenerated Post Preview:")
    print("-" * 60)
    post = result['result'].get('post_markdown', '')
    print(post[:500] + "..." if len(post) > 500 else post)
    print("-" * 60)
    print(f"\nPlatform: {result['result'].get('platform')}")
    print(f"Refinement Count: {result['result'].get('refinement_count')}")


async def example_streaming():
    """Example: Streaming tool invocation."""
    print("=" * 60)
    print("Example 3: Streaming Invocation")
    print("=" * 60)
    
    client = MCPClient()
    
    print("\nInvoking tool 'generate_linkedin_post' (streaming)...")
    print("Topic: 'Best practices for MLOps'\n")
    
    print("Receiving chunks:")
    print("-" * 60)
    
    chunk_count = 0
    content_chunks = []
    
    async for chunk in await client.invoke_tool(
        tool_name="generate_linkedin_post",
        parameters={"topic": "Best practices for MLOps"},
        user_id="example_user_456",
        stream=True,
    ):
        chunk_count += 1
        chunk_type = chunk.get('chunk_type')
        
        if chunk_type == 'start':
            print(f"[{chunk_type.upper()}] Stream started")
            print(f"  Metadata: {chunk.get('metadata')}")
        
        elif chunk_type == 'content':
            content = chunk.get('content', '')
            content_chunks.append(content)
            # Print content as it arrives (showing first 100 chars per chunk)
            preview = content[:100].replace('\n', ' ')
            print(f"[CONTENT] Received {len(content)} chars: {preview}...")
        
        elif chunk_type == 'metadata':
            print(f"[{chunk_type.upper()}] Metadata received")
            print(f"  {chunk.get('metadata')}")
        
        elif chunk_type == 'end':
            print(f"[{chunk_type.upper()}] Stream completed")
        
        elif chunk_type == 'error':
            print(f"[{chunk_type.upper()}] Error: {chunk.get('error')}")
    
    print("-" * 60)
    print(f"\nTotal chunks received: {chunk_count}")
    print(f"Total content length: {sum(len(c) for c in content_chunks)} characters")
    
    # Show complete post
    full_content = ''.join(content_chunks)
    if full_content:
        print(f"\nComplete Post Preview:")
        print("-" * 60)
        print(full_content[:500] + "..." if len(full_content) > 500 else full_content)
        print("-" * 60)


async def main():
    """Run all examples."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 15 + "MCP Client Examples" + " " * 24 + "║")
    print("╚" + "═" * 58 + "╝")
    print()
    
    try:
        
        # Example 3: Streaming invocation
        await example_streaming()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60 + "\n")
        
    except httpx.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        print("Make sure the API server is running at http://localhost:8000")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
