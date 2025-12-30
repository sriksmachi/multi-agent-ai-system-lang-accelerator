# FastMCP Integration

This project uses [FastMCP](https://github.com/jlowin/fastmcp) to provide a standards-compliant MCP (Model Context Protocol) server with automatic streaming support.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
│                                                              │
│  ┌─────────────────┐                                        │
│  │  /health        │  Health check endpoint                 │
│  └─────────────────┘                                        │
│                                                              │
│  ┌──────────────────────────────────────────────────────────┤
│  │              FastMCP Server (/mcp/*)                     │
│  │                                                          │
│  │  • Automatic MCP protocol compliance                    │
│  │  • Built-in streaming support                           │
│  │  • JSON-RPC 2.0 compatible                              │
│  │  • Server-Sent Events (SSE)                             │
│  │                                                          │
│  │  Endpoints:                                             │
│  │    GET  /mcp/tools       - List available tools         │
│  │    POST /mcp/tools/call  - Call tools (streaming/non)   │
│  │    POST /mcp/v1/         - JSON-RPC 2.0 endpoint        │
│  │                                                          │
│  │  Tools:                                                 │
│  │    - generate_linkedin_post                             │
│  │    - generate_linkedin_post_streaming                   │
│  └──────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

## Endpoints

### FastMCP Endpoints

#### 1. **GET /mcp/tools** - List Available Tools
Returns list of all available MCP tools.

**Response:**
```json
{
  "tools": [
    {
      "name": "generate_linkedin_post",
      "description": "Generate a professional LinkedIn post...",
      "inputSchema": {
        "type": "object",
        "properties": {
          "topic": {"type": "string"},
          "user_id": {"type": "string"}
        },
        "required": ["topic"]
      }
    },
    {
      "name": "generate_linkedin_post_streaming",
      "description": "Generate a professional LinkedIn post with streaming...",
      "inputSchema": {...}
    }
  ]
}
```

#### 2. **POST /mcp/tools/call** - Call MCP Tool (Primary Endpoint)
Main endpoint for calling MCP tools with automatic streaming support.

**Annotation for Copilot Studio:**
```yaml
x-ms-agentic-protocol: mcp-streamable-1.0
```

**Request:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "generate_linkedin_post",
    "arguments": {
      "topic": "The future of AI in healthcare",
      "user_id": "user123"
    }
  }
}
```

**Response (Non-Streaming):**
```json
{
  "content": "🚀 The Future of AI in Healthcare\n\nArtificial Intelligence...",
  "isError": false
}
```

**Response (Streaming - SSE):**
```
data: {"type": "content", "content": "🚀 The Future of AI"}

data: {"type": "content", "content": " in Healthcare\n\n"}

data: {"type": "content", "content": "Artificial Intelligence is..."}
```

#### 3. **POST /mcp/v1/** - JSON-RPC 2.0 Endpoint
Standard JSON-RPC 2.0 endpoint for MCP protocol compliance.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "tools/call",
  "params": {
    "name": "generate_linkedin_post",
    "arguments": {"topic": "AI trends"}
  }
}
```

## Usage Examples

### Python Client

The unified MCP client provides both interactive console and programmatic access.

**Interactive Mode:**
```bash
python clients/mcp_client.py
```

**Programmatic Usage:**
```python
from clients.mcp_client import MCPClient

client = MCPClient("http://localhost:8000")

# Non-streaming
result = await client.generate_post("AI trends in 2025")
print(result["content"])

# Streaming
async for chunk in await client.generate_post("AI ethics", stream=True):
    if chunk.get("type") == "content":
        print(chunk["content"], end="", flush=True)

# List available tools
tools = await client.list_tools()
for tool in tools["tools"]:
    print(f"{tool['name']}: {tool['description']}")

# Generic tool call
result = await client.call_tool(
    tool_name="generate_linkedin_post",
    arguments={"topic": "Quantum computing", "user_id": "user123"},
    stream=False
)
```

### cURL

```bash
# Non-streaming
curl -X POST http://localhost:8000/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "generate_linkedin_post",
      "arguments": {
        "topic": "The future of quantum computing"
      }
    }
  }'

# Streaming
curl -X POST http://localhost:8000/mcp/tools/call \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "generate_linkedin_post_streaming",
      "arguments": {"topic": "AI ethics"}
    }
  }'
```

### Copilot Studio Integration

1. **Import OpenAPI Spec:**
   ```
   https://your-api.azurewebsites.net/openapi.json
   ```

2. **Select Operation:**
   - Choose `CallMCPTool` (operationId)
   - Endpoint: `/mcp/tools/call`

3. **Configure Parameters:**
   ```yaml
   method: tools/call
   params:
     name: generate_linkedin_post
     arguments:
       topic: System.Activity.Text
       user_id: System.User.Id
   ```

4. **The endpoint is annotated with:**
   ```yaml
   x-ms-agentic-protocol: mcp-streamable-1.0
   ```

## Benefits of FastMCP

✅ **Automatic Protocol Compliance** - FastMCP handles MCP protocol details
✅ **Built-in Streaming** - SSE streaming works out of the box
✅ **Type Safety** - Full Pydantic integration
✅ **OpenTelemetry** - Automatic tracing and observability
✅ **Standards-Based** - JSON-RPC 2.0 compatible
✅ **Easy to Use** - Simple decorator-based tool registration

## Implementation

### FastMCP Server Definition

File: [`api/fastmcp_server.py`](../api/fastmcp_server.py "api/fastmcp_server.py")

```python
from fastmcp import FastMCP

mcp = FastMCP("LinkedIn Post Generator")

@mcp.tool()
async def generate_linkedin_post(topic: str, user_id: str = None) -> str:
    """Generate a professional LinkedIn post."""
    result = run_post_generator(user_id=user_id, topic=topic)
    return result["post"]

@mcp.tool()
async def generate_linkedin_post_streaming(topic: str, user_id: str = None):
    """Generate a LinkedIn post with streaming."""
    async for chunk in run_post_generator(user_id=user_id, topic=topic, stream=True):
        yield chunk
```

### FastAPI Integration

File: [`api/main.py`](../api/main.py "api/main.py")

```python
from api.fastmcp_server import mcp

app = FastAPI(title="Multi-Agent LinkedIn Post Generator with FastMCP")
app.mount("/mcp", mcp.get_asgi_app())
```

That's it! FastMCP handles all the MCP protocol details automatically.


## Running the Server

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python -m api.main

# Or with uvicorn
uvicorn api.main:app --reload
```

## Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
python -m api.main

# Run client (interactive mode)
python clients/mcp_client.py
```

## OpenAPI/Swagger

Access the interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **OpenAPI JSON**: http://localhost:8000/openapi.json
- **OpenAPI YAML**: http://localhost:8000/swagger.yaml (if served)

## References

- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Model Context Protocol (MCP) Spec](https://modelcontextprotocol.io/)
- [Microsoft Copilot Studio MCP Integration](https://learn.microsoft.com/en-us/microsoft-copilot-studio/)
