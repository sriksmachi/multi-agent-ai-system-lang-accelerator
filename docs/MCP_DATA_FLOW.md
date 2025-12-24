# MCP Server Data Flow

## Request Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                          MCP Client                                   │
│                   (AI Agent / Application)                            │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             │ HTTP POST /mcp/invoke
                             │ {
                             │   "tool": "generate_linkedin_post",
                             │   "parameters": {"topic": "..."},
                             │   "user_id": "user_123",
                             │   "stream": true
                             │ }
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      FastAPI MCP Server                               │
│                   api/routes/mcp_routes.py                            │
│                                                                        │
│  1. Validate request (MCPToolCallRequest schema)                     │
│  2. Check tool exists in MCP_TOOLS registry                          │
│  3. Start OpenTelemetry span (mcp.invoke_tool)                       │
│  4. Log invocation details                                           │
│  5. Route to tool handler: _generate_post_streaming()                │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             │ Call workflow with stream=True
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   Workflow Orchestrator                               │
│              workflows/postgenerator_workflow.py                      │
│                                                                        │
│  1. Initialize PostGeneratorState                                    │
│  2. Create LangGraph workflow with checkpointer                      │
│  3. Start workflow.stream() generator                                │
│  4. Return async generator to MCP handler                            │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             │ Stream workflow updates
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   Multi-Agent Workflow                                │
│                      (LangGraph)                                      │
│                                                                        │
│  ┌──────────┐      ┌────────────┐      ┌────────┐      ┌──────────┐│
│  │ Planner  │─────▶│ Researcher │─────▶│ Writer │─────▶│ Reviewer ││
│  └──────────┘      └────────────┘      └────────┘      └──────────┘│
│       │                  │                  │                │       │
│       └──────────────────┴──────────────────┴────────────────┘       │
│                             │                                         │
│                  Yields state updates                                 │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             │ State chunks
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   MCP Stream Processor                                │
│              api/routes/mcp_routes.py                                 │
│                  _generate_post_streaming()                           │
│                                                                        │
│  For each workflow chunk:                                            │
│  1. Extract content (draft_post, final_post)                         │
│  2. Convert to MCPStreamChunk                                        │
│  3. Format as SSE: "data: {...}\n\n"                                 │
│  4. Yield to FastAPI StreamingResponse                               │
│                                                                        │
│  Chunk types emitted:                                                │
│  ├─ start:    Stream initialization with metadata                    │
│  ├─ content:  Partial post content (multiple chunks)                 │
│  ├─ metadata: Final metrics (trace_id, scores, etc.)                 │
│  └─ end:      Stream completion                                      │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             │ SSE Stream
                             │ data: {"chunk_type":"start",...}
                             │ data: {"chunk_type":"content","content":"..."}
                             │ data: {"chunk_type":"content","content":"..."}
                             │ data: {"chunk_type":"metadata",...}
                             │ data: {"chunk_type":"end",...}
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     FastAPI Response                                  │
│                   StreamingResponse                                   │
│                                                                        │
│  HTTP Headers:                                                       │
│  - Content-Type: text/event-stream                                   │
│  - Cache-Control: no-cache                                           │
│  - Connection: keep-alive                                            │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             │ SSE Events streamed to client
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          MCP Client                                   │
│                    clients/mcp_client_example.py                      │
│                                                                        │
│  async for chunk in response.aiter_lines():                          │
│    if chunk.startswith("data: "):                                    │
│      data = json.loads(chunk[6:])                                    │
│      match data["chunk_type"]:                                       │
│        case "start":    # Initialize                                 │
│        case "content":  # Process partial content                    │
│        case "metadata": # Store final metadata                       │
│        case "end":      # Finalize                                   │
└──────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### 1. MCP Routes (`api/routes/mcp_routes.py`)
- **Tool Registry**: Defines available MCP tools with schemas
- **Request Validation**: Uses Pydantic to validate incoming requests
- **Tool Routing**: Maps tool names to handler functions
- **Response Formatting**: Converts workflow output to MCP protocol format
- **Error Handling**: Catches and formats errors as MCP error responses
- **Observability**: Emits OpenTelemetry spans and logs

### 2. Workflow (`workflows/postgenerator_workflow.py`)
- **State Management**: Maintains conversation state through LangGraph
- **Agent Orchestration**: Routes tasks through planner → researcher → writer → reviewer
- **Streaming**: Yields state updates as agents complete their work
- **Checkpointing**: Saves state to Cosmos DB for resumability
- **Tracing**: Emits spans for each agent and workflow step

### 3. MCP Client (`clients/mcp_client_example.py`)
- **Tool Discovery**: Fetches available tools via GET /mcp/tools
- **Request Construction**: Builds MCP-compliant request payloads
- **SSE Parsing**: Decodes Server-Sent Events stream
- **Chunk Processing**: Handles different chunk types (start, content, metadata, end, error)
- **Error Recovery**: Handles network errors and timeouts

## Data Structures

### Request Payload
```json
{
  "tool": "generate_linkedin_post",
  "parameters": {
    "topic": "The future of AI in healthcare",
    "platform": "linkedin"
  },
  "user_id": "user_123",
  "thread_id": "thread_abc",
  "stream": true,
  "metadata": {
    "client_version": "1.0"
  }
}
```

### Stream Chunks

**Start:**
```json
{
  "protocol": "mcp-streamable-1.0",
  "tool": "generate_linkedin_post",
  "chunk_type": "start",
  "metadata": {
    "user_id": "user_123",
    "thread_id": "thread_abc",
    "topic": "..."
  },
  "timestamp": "2025-12-23T10:00:00.000Z"
}
```

**Content:**
```json
{
  "protocol": "mcp-streamable-1.0",
  "tool": "generate_linkedin_post",
  "chunk_type": "content",
  "content": "# The Future of AI in Healthcare\n\n",
  "timestamp": "2025-12-23T10:00:01.234Z"
}
```

**Metadata:**
```json
{
  "protocol": "mcp-streamable-1.0",
  "tool": "generate_linkedin_post",
  "chunk_type": "metadata",
  "metadata": {
    "content_length": 1234,
    "trace_id": "abc123...",
    "refinement_count": 2,
    "scores": {"relevance": 0.95}
  },
  "timestamp": "2025-12-23T10:00:45.000Z"
}
```

**End:**
```json
{
  "protocol": "mcp-streamable-1.0",
  "tool": "generate_linkedin_post",
  "chunk_type": "end",
  "metadata": {"status": "completed"},
  "timestamp": "2025-12-23T10:00:45.100Z"
}
```

## Observability

### OpenTelemetry Spans

```
run_post_generator [60s]
├─ mcp.invoke_tool [60s]
│  ├─ planner.create_outline [5s]
│  ├─ researcher.search_topic [10s]
│  ├─ writer.draft_post [30s]
│  ├─ reviewer.check_facts [10s]
│  └─ reviewer.refine_post [5s]
└─ mcp.stream_completed
```

### Span Attributes
- `mcp.protocol`: "mcp-streamable-1.0"
- `mcp.tool`: "generate_linkedin_post"
- `mcp.user_id`: User identifier
- `mcp.thread_id`: Thread identifier
- `mcp.streaming`: true/false
- `mcp.trace_id`: Trace ID for correlation
- `mcp.success`: true/false

### Logs
```
INFO: MCP: Invoking tool 'generate_linkedin_post' for user 'user_123' (streaming=True)
INFO: [user_123][thread_abc] PLANNER: Creating outline...
INFO: [user_123][thread_abc] RESEARCHER: Searching for topic...
INFO: [user_123][thread_abc] WRITER: Drafting post...
INFO: [user_123][thread_abc] REVIEWER: Checking facts...
INFO: MCP: Streaming generation completed for tool 'generate_linkedin_post'
```

## Error Handling Flow

```
Client Request
     │
     ▼
MCP Router (Request Validation)
     │
     ├─ Invalid JSON ──────────────▶ 400 Bad Request
     │
     ├─ Unknown Tool ──────────────▶ 400 Bad Request
     │                                "Unknown tool: ..."
     │
     ├─ Missing Parameters ────────▶ 400 Bad Request
     │                                "Missing required parameter: 'topic'"
     │
     ▼
Workflow Execution
     │
     ├─ Workflow Error ────────────▶ Stream: error chunk
     │                                Non-stream: 500 Internal Server Error
     │
     ├─ Timeout ───────────────────▶ Client handles timeout
     │
     └─ Success ───────────────────▶ Complete response
```

## Performance Characteristics

### Non-Streaming Mode
- **Latency**: 30-60 seconds (full workflow completion)
- **Memory**: Holds complete result in memory
- **Best for**: Batch processing, simple integrations

### Streaming Mode
- **Time to First Byte**: 5-10 seconds (planner + researcher)
- **Time to Last Byte**: 30-60 seconds (complete workflow)
- **Memory**: Constant (chunks are yielded as generated)
- **Best for**: Real-time UIs, user-facing applications

### Throughput
- **Concurrent Requests**: Limited by Azure OpenAI quota
- **Checkpointing**: Cosmos DB handles concurrent writes
- **Streaming Overhead**: Minimal (~5% compared to non-streaming)
