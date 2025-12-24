# MCP Server Quick Start Guide

## Prerequisites

- Python 3.8+
- All dependencies installed: `pip install -r requirements.txt`
- FastAPI server configured
- Azure OpenAI credentials set up (in `.env`)

## 1. Start the Server

```bash
cd c:\code\multi-agent-ai-system-lang-accelerator
uvicorn api.main:app --reload
```

Server will start at: **http://localhost:8000**

## 2. Verify MCP Endpoints

### Check API Documentation
Open in browser: http://localhost:8000/docs

Look for the **"MCP Protocol"** section with:
- `GET /mcp/tools`
- `POST /mcp/invoke`

### Quick Test with cURL

**List Tools:**
```bash
curl http://localhost:8000/mcp/tools
```

**Invoke Tool (Non-Streaming):**
```bash
curl -X POST http://localhost:8000/mcp/invoke \
  -H "Content-Type: application/json" \
  -d "{\"tool\":\"generate_linkedin_post\",\"parameters\":{\"topic\":\"Quick test\"},\"user_id\":\"test\",\"stream\":false}"
```

**Invoke Tool (Streaming):**
```bash
curl -X POST http://localhost:8000/mcp/invoke \
  -H "Content-Type: application/json" \
  -d "{\"tool\":\"generate_linkedin_post\",\"parameters\":{\"topic\":\"Streaming test\"},\"user_id\":\"test\",\"stream\":true}" \
  --no-buffer
```

## 3. Run Example Client

```bash
python clients/mcp_client_example.py
```

This will demonstrate:
1. Listing available tools
2. Non-streaming invocation
3. Streaming invocation with real-time output

## 4. Run Tests

```bash
python tests/test_mcp_server.py
```

Tests cover:
- Health check
- Tool discovery
- Non-streaming invocation
- Streaming invocation
- Error handling

## 5. Using the MCP Client

### Python Code Example

```python
import asyncio
from clients.mcp_client_example import MCPClient

async def main():
    client = MCPClient("http://localhost:8000")
    
    # List available tools
    tools = await client.list_tools()
    print(f"Available tools: {[t['name'] for t in tools['tools']]}")
    
    # Non-streaming invocation
    result = await client.invoke_tool(
        tool_name="generate_linkedin_post",
        parameters={"topic": "The future of AI"},
        user_id="my_user_id",
        stream=False
    )
    print(f"Generated post: {result['result']['post_markdown'][:200]}...")
    
    # Streaming invocation
    print("\nStreaming response:")
    async for chunk in await client.invoke_tool(
        tool_name="generate_linkedin_post",
        parameters={"topic": "Best practices for MLOps"},
        user_id="my_user_id",
        stream=True
    ):
        if chunk["chunk_type"] == "content":
            print(chunk["content"], end="", flush=True)

asyncio.run(main())
```

## 6. Monitoring

### View Traces in Azure Application Insights
1. Go to Azure Portal
2. Navigate to your Application Insights resource
3. Look for traces with:
   - Operation Name: `mcp.list_tools` or `mcp.invoke_tool`
   - Custom dimensions: `mcp.tool`, `mcp.user_id`, `mcp.streaming`

### View Logs
```bash
# In the terminal where uvicorn is running
# Look for log entries like:
# INFO:api.routes.mcp_routes:MCP: Invoking tool 'generate_linkedin_post'...
```

## Troubleshooting

### Server won't start
- Check if port 8000 is already in use
- Verify all dependencies are installed: `pip install -r requirements.txt`
- Check environment variables in `.env`

### Tool invocation fails
- Ensure Azure OpenAI credentials are configured
- Check Cosmos DB connection (used for checkpointing)
- Look at server logs for detailed error messages
- Verify the FAISS index exists (run data pipeline if needed)

### Streaming not working
- Ensure you're using a client that supports SSE (Server-Sent Events)
- Check that `stream=true` in request body
- Use `--no-buffer` flag with cURL

## Documentation

- **Full Documentation**: [api/MCP_README.md](api/MCP_README.md)
- **Implementation Summary**: [MCP_IMPLEMENTATION_SUMMARY.md](MCP_IMPLEMENTATION_SUMMARY.md)
- **API Documentation**: http://localhost:8000/docs (when server is running)

## Support

For issues or questions:
1. Check the logs in the terminal
2. Review [api/MCP_README.md](api/MCP_README.md) for detailed examples
3. Look at traces in Application Insights for debugging

---

**You're ready to use the MCP Server! 🚀**
