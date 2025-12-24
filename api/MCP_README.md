# MCP Server Implementation

This directory contains the Model Context Protocol (MCP) server implementation for the multi-agent LinkedIn post generator.

## Overview

The MCP server exposes the post generation workflow as a standardized, streaming-capable tool that can be consumed by AI agents and applications.

### Key Features

- ✅ **MCP Protocol Compliance**: Implements MCP-streamable-1.0 protocol
- ✅ **Streaming Support**: Real-time token streaming via Server-Sent Events (SSE)
- ✅ **OpenTelemetry Integration**: Full observability with distributed tracing
- ✅ **Tool Discovery**: Dynamic tool listing with parameter schemas
- ✅ **Non-Streaming Mode**: Optional complete response mode
- ✅ **OpenAPI Extension**: `x-ms-agentic-protocol: mcp-streamable-1.0` metadata

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Client                           │
│              (AI Agent / Application)                   │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ HTTP/SSE
                     │
┌────────────────────▼────────────────────────────────────┐
│              FastAPI MCP Server                         │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  GET  /mcp/tools       - List Tools               │  │
│  │  POST /mcp/invoke      - Invoke Tool              │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │         MCP Route Handler                         │  │
│  │  - Request validation                             │  │
│  │  - Tool routing                                   │  │
│  │  - Streaming orchestration                        │  │
│  │  - OpenTelemetry tracing                          │  │
│  └──────────────┬───────────────────────────────────┘  │
│                 │                                        │
└─────────────────┼────────────────────────────────────────┘
                  │
                  │
┌─────────────────▼────────────────────────────────────────┐
│         Multi-Agent Workflow (LangGraph)                 │
│                                                           │
│  Planner → Researcher → Writer → Reviewer                │
│                                                           │
│  - Azure OpenAI integration                              │
│  - Cosmos DB checkpointing                               │
│  - Streaming content generation                          │
└───────────────────────────────────────────────────────────┘
```

## MCP Protocol Specification

### Tool Discovery: `GET /mcp/tools`

Returns available tools with their schemas.

**Response:**
```json
{
  "protocol": "mcp-streamable-1.0",
  "tools": [
    {
      "name": "generate_linkedin_post",
      "description": "Generate a professional LinkedIn post using a multi-agent system...",
      "parameters": [
        {
          "name": "topic",
          "type": "string",
          "description": "Topic or query for the LinkedIn post",
          "required": true
        }
      ],
      "streaming": true
    }
  ],
  "timestamp": "2025-12-23T10:00:00Z"
}
```

### Tool Invocation: `POST /mcp/invoke`

Invokes a tool with optional streaming.

**Request:**
```json
{
  "tool": "generate_linkedin_post",
  "parameters": {
    "topic": "The future of AI in healthcare"
  },
  "user_id": "user_123",
  "thread_id": "thread_abc",
  "stream": true,
  "metadata": {}
}
```

#### Non-Streaming Response (stream=false)

**Response:**
```json
{
  "protocol": "mcp-streamable-1.0",
  "tool": "generate_linkedin_post",
  "result": {
    "post_markdown": "# Amazing Post\n\nContent here...",
    "platform": "linkedin",
    "scores": {"relevance": 0.95},
    "refinement_count": 1,
    "trace_id": "abc123",
    "conversation_id": "conv-xyz"
  },
  "user_id": "user_123",
  "thread_id": "thread_abc",
  "trace_id": "abc123",
  "timestamp": "2025-12-23T10:00:00Z"
}
```

#### Streaming Response (stream=true)

Content-Type: `text/event-stream`

**Stream Chunks:**

1. **Start Chunk**
```json
data: {
  "protocol": "mcp-streamable-1.0",
  "tool": "generate_linkedin_post",
  "chunk_type": "start",
  "metadata": {
    "user_id": "user_123",
    "thread_id": "thread_abc",
    "topic": "The future of AI in healthcare"
  },
  "timestamp": "2025-12-23T10:00:00.000Z"
}
```

2. **Content Chunks** (multiple)
```json
data: {
  "protocol": "mcp-streamable-1.0",
  "tool": "generate_linkedin_post",
  "chunk_type": "content",
  "content": "# The Future ",
  "timestamp": "2025-12-23T10:00:00.123Z"
}

data: {
  "protocol": "mcp-streamable-1.0",
  "tool": "generate_linkedin_post",
  "chunk_type": "content",
  "content": "of AI in Healthcare\n\n",
  "timestamp": "2025-12-23T10:00:00.246Z"
}
```

3. **Metadata Chunk**
```json
data: {
  "protocol": "mcp-streamable-1.0",
  "tool": "generate_linkedin_post",
  "chunk_type": "metadata",
  "metadata": {
    "content_length": 1234,
    "trace_id": "abc123",
    "refinement_count": 1
  },
  "timestamp": "2025-12-23T10:00:05.000Z"
}
```

4. **End Chunk**
```json
data: {
  "protocol": "mcp-streamable-1.0",
  "tool": "generate_linkedin_post",
  "chunk_type": "end",
  "metadata": {"status": "completed"},
  "timestamp": "2025-12-23T10:00:05.100Z"
}
```

5. **Error Chunk** (on failure)
```json
data: {
  "protocol": "mcp-streamable-1.0",
  "tool": "generate_linkedin_post",
  "chunk_type": "error",
  "error": "Generation failed: ...",
  "timestamp": "2025-12-23T10:00:05.100Z"
}
```

## API Files

### Core Implementation

- **`api/routes/mcp_routes.py`**: MCP endpoint handlers
  - `GET /mcp/tools`: Tool discovery
  - `POST /mcp/invoke`: Tool invocation with streaming
  - Tool registry and routing logic

- **`api/schemas/mcp_schemas.py`**: Pydantic models
  - `MCPTool`: Tool definition
  - `MCPToolCallRequest`: Invocation request
  - `MCPToolCallResponse`: Non-streaming response
  - `MCPStreamChunk`: Streaming chunk format
  - Error schemas

### Integration Points

- **`api/main.py`**: FastAPI app with MCP router registration
- **`workflows/postgenerator_workflow.py`**: Workflow with streaming support
- **`api/schemas/__init__.py`**: Schema exports

## Usage Examples

### Python Client

See [`clients/mcp_client_example.py`](../clients/mcp_client_example.py) for a complete example.

#### List Tools
```python
from mcp_client_example import MCPClient

client = MCPClient("http://localhost:8000")
tools = await client.list_tools()
print(tools)
```

#### Non-Streaming Invocation
```python
result = await client.invoke_tool(
    tool_name="generate_linkedin_post",
    parameters={"topic": "AI in healthcare"},
    user_id="user_123",
    stream=False,
)
print(result["result"]["post_markdown"])
```

#### Streaming Invocation
```python
async for chunk in await client.invoke_tool(
    tool_name="generate_linkedin_post",
    parameters={"topic": "AI in healthcare"},
    user_id="user_123",
    stream=True,
):
    if chunk["chunk_type"] == "content":
        print(chunk["content"], end="", flush=True)
```

### cURL Examples

#### List Tools
```bash
curl -X GET http://localhost:8000/mcp/tools
```

#### Non-Streaming Invocation
```bash
curl -X POST http://localhost:8000/mcp/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "generate_linkedin_post",
    "parameters": {"topic": "AI in healthcare"},
    "user_id": "user_123",
    "stream": false
  }'
```

#### Streaming Invocation
```bash
curl -X POST http://localhost:8000/mcp/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "generate_linkedin_post",
    "parameters": {"topic": "AI in healthcare"},
    "user_id": "user_123",
    "stream": true
  }' \
  --no-buffer
```

## OpenAPI Integration

The MCP endpoint includes the `x-ms-agentic-protocol` extension in the OpenAPI spec:

```yaml
paths:
  /mcp/invoke:
    post:
      x-ms-agentic-protocol: mcp-streamable-1.0
      summary: Invoke MCP Tool
      ...
```

Access the OpenAPI spec at: `http://localhost:8000/docs` or `http://localhost:8000/openapi.json`

## Observability

### OpenTelemetry Tracing

All MCP operations are fully traced:

- **Span Names**: `mcp.list_tools`, `mcp.invoke_tool`, `mcp.stream_*`
- **Attributes**: 
  - `mcp.protocol`: Protocol version
  - `mcp.tool`: Tool name
  - `mcp.user_id`: User identifier
  - `mcp.streaming`: Streaming flag
  - `mcp.trace_id`: Trace identifier
- **Events**: Tool invocation, stream lifecycle, errors

### Logs

Structured logs are emitted for:
- Tool discovery requests
- Tool invocations (start/complete/error)
- Streaming events
- Parameter validation failures

View logs in Azure Application Insights or console output.

## Testing

### Run the Example Client

1. Start the FastAPI server:
   ```bash
   uvicorn api.main:app --reload
   ```

2. Run the example client:
   ```bash
   python clients/mcp_client_example.py
   ```

### Manual Testing

Access the interactive API docs:
```
http://localhost:8000/docs
```

Navigate to the "MCP Protocol" section to test endpoints interactively.

## Extending the MCP Server

### Adding New Tools

1. **Define the Tool** in `api/routes/mcp_routes.py`:
   ```python
   MCP_TOOLS.append(
       MCPTool(
           name="my_new_tool",
           description="Description of the tool",
           parameters=[
               MCPToolParameter(
                   name="param1",
                   type="string",
                   description="Parameter description",
                   required=True,
               )
           ],
           streaming=True,
       )
   )
   ```

2. **Add Tool Handler** in `api/routes/mcp_routes.py`:
   ```python
   async def _handle_my_tool(request: MCPToolCallRequest, span: trace.Span):
       # Implementation
       pass
   ```

3. **Route in `invoke_mcp_tool`**:
   ```python
   if tool_name == "my_new_tool":
       if request.stream:
           return StreamingResponse(_handle_my_tool_streaming(...))
       else:
           return await _handle_my_tool_non_streaming(...)
   ```

## Protocol Compliance

This implementation follows the MCP specification:

- ✅ Tool discovery via standard endpoint
- ✅ Standardized request/response schemas
- ✅ Server-Sent Events for streaming
- ✅ Protocol version in all messages
- ✅ Structured error responses
- ✅ Metadata support for extensibility
- ✅ OpenAPI documentation with extensions

## References

- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [OpenTelemetry Python](https://opentelemetry-python.readthedocs.io/)
