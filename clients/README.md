# MCP Client

Unified client for the Multi-Agent LinkedIn Post Generator FastMCP server.

Built using the official [FastMCP Client library](https://gofastmcp.com/clients/client).

## Features

✅ **Interactive Console Mode** - User-friendly menu-driven interface  
✅ **Programmatic API** - Use as a Python library  
✅ **Streaming Support** - Real-time content generation  
✅ **Non-Streaming Support** - Get complete results at once  
✅ **Tool Discovery** - List available MCP tools  
✅ **Official FastMCP Client** - Uses the official FastMCP client library  

## Quick Start

### Interactive Mode

```bash
python clients/mcp_client.py
```

This launches an interactive menu where you can:
1. Generate posts
2. List available tools
3. Exit

### Programmatic Usage

```python
from clients.mcp_client import MCPClientWrapper
import asyncio

async def example():
    # Initialize client with MCP endpoint URL
    client = MCPClientWrapper("http://localhost:8000/mcp")
    
    async with client:
        # Generate post (non-streaming)
        result = await client.generate_post("The future of AI")
        print(result)
        
        # Generate post (streaming)
        result = await client.generate_post("AI ethics", stream=True)
        print(result)
        
        # List tools
        tools = await client.list_tools()
        print(f"Available tools: {len(tools)} tools")
        
        # Call any tool directly
        result = await client.call_tool(
            "generate_linkedin_post",
            {"topic": "Cloud computing trends"}
        )

asyncio.run(example())
    tools = await client.list_tools()
    for tool in tools["tools"]:
        print(f"- {tool['name']}")

asyncio.run(example())
```

## API Reference

### MCPClient

**Constructor:**
```python
client = MCPClient(base_url="http://localhost:8000")
```

**Methods:**

#### `check_health() -> dict`
Check API health status.

```python
health = await client.check_health()
# Returns: {"status": "healthy", "message": "...", "version": "..."}
```

#### `list_tools() -> dict`
List available MCP tools.

```python
tools = await client.list_tools()
# Returns: {"tools": [...]}
```

#### `call_tool(tool_name: str, arguments: dict, stream: bool = False)`
Call a specific MCP tool.

```python
result = await client.call_tool(
    tool_name="generate_linkedin_post",
    arguments={"topic": "AI trends", "user_id": "user123"},
    stream=False
)
```

#### `generate_post(topic: str, user_id: Optional[str] = None, stream: bool = False)`
Convenience method to generate a LinkedIn post.

```python
# Non-streaming
result = await client.generate_post("Quantum computing")

# Streaming
async for chunk in await client.generate_post("AI ethics", stream=True):
    print(chunk.get("content", ""), end="")
```

## Requirements

- Python 3.8+
- httpx
- asyncio

Install dependencies:
```bash
pip install httpx
```

## Environment

The client expects the API server to be running at `http://localhost:8000` by default.

To use a different URL:
```python
client = MCPClient("https://your-api.azurewebsites.net")
```

Or in interactive mode, modify the base URL in the script.

## Examples

### Example 1: Simple Post Generation

```python
from clients.mcp_client import MCPClient
import asyncio

async def main():
    client = MCPClient()
    result = await client.generate_post("The impact of AI on healthcare")
    print(result["content"])

asyncio.run(main())
```

### Example 2: Streaming with Progress

```python
from clients.mcp_client import MCPClient
import asyncio

async def main():
    client = MCPClient()
    
    print("Generating post...")
    content_parts = []
    
    async for chunk in await client.generate_post(
        "Sustainable technology and green computing",
        stream=True
    ):
        if chunk.get("type") == "content":
            part = chunk["content"]
            content_parts.append(part)
            print(part, end="", flush=True)
    
    print(f"\n\nTotal characters: {len(''.join(content_parts))}")

asyncio.run(main())
```

### Example 3: Tool Discovery

```python
from clients.mcp_client import MCPClient
import asyncio

async def main():
    client = MCPClient()
    tools = await client.list_tools()
    
    print("Available Tools:")
    for tool in tools["tools"]:
        print(f"\n🔧 {tool['name']}")
        print(f"   {tool['description']}")
        
        schema = tool.get("inputSchema", {})
        if schema.get("properties"):
            print("   Parameters:")
            for param, info in schema["properties"].items():
                print(f"     - {param}: {info.get('type', 'any')}")

asyncio.run(main())
```

## Troubleshooting

**Error: "Cannot connect to API"**
- Make sure the API server is running: `python -m api.main`
- Check the URL is correct
- Verify no firewall is blocking the connection

**Error: "HTTP 404"**
- Ensure you're using FastMCP endpoints (`/mcp/tools/call`)
- Check API server logs for details

**Error: "Timeout"**
- Post generation can take 30-60 seconds
- Increase timeout in client if needed:
  ```python
  # Modify timeout in MCPClient class
  async with httpx.AsyncClient(timeout=180.0) as client:
  ```

## License

Same as parent project.
