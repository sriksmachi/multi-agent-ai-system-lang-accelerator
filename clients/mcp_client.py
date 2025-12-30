"""
MCP Client for Multi-Agent LinkedIn Post Generator.

This client provides both interactive console mode and programmatic API access
for calling FastMCP tools with streaming and non-streaming support.

Usage:
    # Interactive mode
    python clients/mcp_client.py
    
    # Programmatic usage
    from clients.mcp_client import MCPClient
    
    client = MCPClient("http://localhost:8000")
    result = await client.generate_post("AI trends in 2025")
"""

import asyncio
import httpx
import json
import sys
from datetime import datetime
from typing import Optional, AsyncGenerator


class MCPClient:
    """Unified client for FastMCP server."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.mcp_url = f"{base_url}/mcp"
    
    async def check_health(self) -> dict:
        """Check API health status."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/health", timeout=5.0)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                return {"status": "error", "message": str(e)}
    
    async def list_tools(self) -> dict:
        """List available MCP tools."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.mcp_url}/tools")
            response.raise_for_status()
            return response.json()
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict,
        stream: bool = False,
    ):
        """
        Call a FastMCP tool.
        
        Args:
            tool_name: Name of the tool (e.g., "generate_linkedin_post")
            arguments: Tool arguments (e.g., {"topic": "AI trends"})
            stream: Enable streaming response
            
        Returns:
            Tool result (dict) or async generator for streaming
        """
        # Extract user_id from arguments or generate one
        user_id = arguments.pop("user_id", f"user-{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        # Build MCPToolCallRequest
        request_body = {
            "tool": tool_name,
            "parameters": arguments,
            "user_id": user_id,
            "stream": stream
        }
        
        if stream:
            return self._call_streaming(request_body)
        else:
            return await self._call_non_streaming(request_body)
    
    async def _call_non_streaming(self, request_body: dict) -> dict:
        """Call tool and get complete response."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.mcp_url}/tools/call",
                json=request_body,
            )
            response.raise_for_status()
            return response.json()
    
    async def _call_streaming(self, request_body: dict) -> AsyncGenerator[dict, None]:
        """Call tool and stream response chunks."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self.mcp_url}/tools/call",
                json=request_body,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            chunk_data = json.loads(line[6:])
                            yield chunk_data
                        except json.JSONDecodeError:
                            continue
    
    # Convenience methods for specific tools
    
    async def generate_post(
        self,
        topic: str,
        user_id: Optional[str] = None,
        stream: bool = False,
    ):
        """
        Generate a LinkedIn post.
        
        Args:
            topic: Topic or query for the post
            user_id: Optional user identifier
            stream: Enable streaming response
            
        Returns:
            Generated post content or stream of chunks
        """
        if not user_id:
            user_id = f"user-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return await self.call_tool(
            tool_name="generate_linkedin_post",
            arguments={"topic": topic, "user_id": user_id},
            stream=stream
        )


# ============================================================================
# Interactive Console Interface
# ============================================================================

class ConsoleInterface:
    """Interactive console interface for the MCP client."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.client = MCPClient(base_url)
        self.base_url = base_url
    
    async def run(self):
        """Run the interactive console."""
        self.print_header()
        
        # Check health
        health = await self.client.check_health()
        if health.get("status") == "healthy":
            print(f"✅ API is {health['status']} (v{health.get('version', 'unknown')})\n")
        else:
            print(f"❌ Cannot connect to API at {self.base_url}")
            print(f"   {health.get('message', 'Unknown error')}")
            print("\n   Start the API with: python -m api.main\n")
            return
        
        # Main loop
        while True:
            try:
                await self.handle_input()
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!\n")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")
    
    async def handle_input(self):
        """Handle user input."""
        print("\nOptions:")
        print("  1. Generate post (non-streaming)")
        print("  2. Generate post (streaming)")
        print("  3. List available tools")
        print("  q. Quit")
        
        choice = input("\nYour choice: ").strip().lower()
        
        if choice in ['q', 'quit', 'exit']:
            print("\n👋 Goodbye!\n")
            sys.exit(0)
        elif choice == '1':
            await self.generate_non_streaming()
        elif choice == '2':
            await self.generate_streaming()
        elif choice == '3':
            await self.list_tools()
        else:
            print("Invalid choice. Please try again.")
    
    async def generate_non_streaming(self):
        """Generate post without streaming."""
        topic = input("\nEnter topic: ").strip()
        if not topic:
            print("Topic cannot be empty.")
            return
        
        print(f"\n🤖 Generating post about: {topic}")
        print("   Please wait...\n")
        
        try:
            result = await self.client.generate_post(topic, stream=False)
            
            print("\n" + "=" * 80)
            print("✅ GENERATED POST")
            print("=" * 80)
            print(f"\n{result.get('content', result)}\n")
            print("=" * 80 + "\n")
            
        except httpx.HTTPStatusError as e:
            print(f"\n❌ HTTP Error {e.response.status_code}: {e.response.text}\n")
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
    
    async def generate_streaming(self):
        """Generate post with streaming."""
        topic = input("\nEnter topic: ").strip()
        if not topic:
            print("Topic cannot be empty.")
            return
        
        print(f"\n🤖 Generating post about: {topic}")
        print("\n" + "=" * 80)
        print("📝 STREAMING RESPONSE")
        print("=" * 80 + "\n")
        
        try:
            full_content = []
            async for chunk in await self.client.generate_post(topic, stream=True):
                chunk_type = chunk.get("chunk_type")
                
                if chunk_type == "start":
                    print("🚀 Stream started...\n")
                elif chunk_type == "content":
                    content = chunk.get("content", "")
                    print(content, end="", flush=True)
                    full_content.append(content)
                elif chunk_type == "metadata":
                    # Optional: print metadata
                    pass
                elif chunk_type == "end":
                    print("\n\n✅ Stream completed!")
                elif chunk_type == "error":
                    print(f"\n\n❌ Error: {chunk.get('error')}")
            
            print("\n" + "=" * 80)
            print(f"✅ Complete! ({len(''.join(full_content))} characters)")
            print("=" * 80 + "\n")
            
        except httpx.HTTPStatusError as e:
            print(f"\n❌ HTTP Error {e.response.status_code}: {e.response.text}\n")
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
    
    async def list_tools(self):
        """List available tools."""
        try:
            tools = await self.client.list_tools()
            
            print("\n" + "=" * 80)
            print("📋 AVAILABLE TOOLS")
            print("=" * 80 + "\n")
            
            for tool in tools.get("tools", []):
                print(f"🔧 {tool.get('name')}")
                print(f"   {tool.get('description', 'No description')}")
                
                schema = tool.get("inputSchema", {})
                props = schema.get("properties", {})
                required = schema.get("required", [])
                
                if props:
                    print(f"   Parameters:")
                    for param_name, param_info in props.items():
                        req_marker = "required" if param_name in required else "optional"
                        param_type = param_info.get("type", "any")
                        print(f"     - {param_name} ({param_type}, {req_marker})")
                print()
            
            print("=" * 80 + "\n")
            
        except Exception as e:
            print(f"\n❌ Error listing tools: {e}\n")
    
    def print_header(self):
        """Print application header."""
        print("\n" + "=" * 80)
        print("Multi-Agent LinkedIn Post Generator - MCP Client")
        print("=" * 80)
        print(f"\nConnected to: {self.base_url}")


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    """Main entry point."""
    # Check if running in interactive mode or with command line args
    if len(sys.argv) > 1:
        # Command line mode (for future enhancement)
        print("Command line mode not yet implemented.")
        print("Run without arguments for interactive mode.")
    else:
        # Interactive mode
        interface = ConsoleInterface()
        await interface.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!\n")
