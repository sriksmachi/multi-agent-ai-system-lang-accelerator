# MCP Client

Console client for the Multi-Agent LinkedIn Post Generator FastMCP server.

Built using the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) with Streamable HTTP transport.

## Features

✅ **Real-time Streaming** - See content generation progress in real-time  
✅ **Progress Tracking** - Visual progress updates during generation  
✅ **Notification Logging** - Receive intermediate updates from each agent (planner, researcher, writer, reviewer)  
✅ **Tool Discovery** - Automatically lists available MCP tools  
✅ **Session Management** - Handles connection lifecycle and session IDs  

## Quick Start

### Prerequisites

Ensure the FastMCP server is running:
```bash
python api/main.py
```

The server will start at `http://localhost:8000` with MCP endpoint at `/mcp`.

### Run the Client

```bash
cd clients
python mcp_client.py
```

### Example Output

```
Initialized connection
Available tools:
 - generate_linkedin_post_streaming: Generate a professional LinkedIn post with real-time streaming updates.
 - greet: Greet someone by name.

Calling tool: generate_linkedin_post_streaming

🔔 Notification received:
========================================
Notification: Starting generation for: mango global supply chain

Progress: 20% - Workflow ready
🔔 Notification received:
========================================
Notification: [planner] Here is a clear, LinkedIn‑appropriate ou...

Progress: 50% - Drafting post...
🔔 Notification received:
========================================
Notification: [writer] 🌍 A 10‑word insight on the global mango s...

Progress: 90% - Finalizing...
Progress: 100% - Complete!

✅ Final post:

🌍 A 10‑word insight on the global mango supply chain:
...
```

## How It Works

The client uses the official MCP Python SDK with Streamable HTTP transport:

1. **Connection**: Establishes a streaming HTTP connection to the FastMCP server
2. **Tool Discovery**: Lists all available tools and their descriptions
3. **Tool Invocation**: Calls `generate_linkedin_post_streaming` with a topic
4. **Real-time Updates**: 
   - **Progress callbacks** show generation stages (20%, 50%, 90%, 100%)
   - **Notification logs** display intermediate outputs from each agent:
     - `[planner]` - Content outline and structure
     - `[researcher]` - Retrieved documents count
     - `[writer]` - Draft content
     - `[reviewer]` - Quality evaluation (if available)
5. **Final Result**: Displays the complete generated LinkedIn post

## Customization

Edit [`mcp_client.py`](mcp_client.py) to change the topic or tool:

```python
tool_name = "generate_linkedin_post_streaming"
arguments = {"topic": "your topic here"}
```

## Testing with MCP Inspector

The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) is a visual debugging tool for MCP servers. It provides a web-based UI to test tools, view notifications, and inspect server behavior.

### Install and Run MCP Inspector

1. Ensure your FastMCP server is running:
   ```bash
   python api/main.py
   ```

2. Run MCP Inspector with your server URL:
   ```bash
   npx @modelcontextprotocol/inspector http://localhost:8000/mcp
   ```

3. Open the Inspector UI in your browser (typically opens automatically at `http://localhost:5173`)

### Using MCP Inspector

- **Tools Tab**: Browse and test all available tools
- **Run Tool**: Enter parameters and execute tools
- **View Results**: See tool output including notifications/messages
- **Notifications**: Monitor real-time progress updates and logs
- **History**: Review previous tool calls

### Inspector Configuration

The Inspector connects using:
- **Transport Type**: Streamable HTTP
- **URL**: `http://localhost:8000/mcp`
- **Connection**: Direct (no authentication required for local development)

This is useful for:
- Testing tools without writing client code
- Debugging notification and progress callbacks
- Inspecting tool schemas and parameters
- Validating server responses

## Sample Run 

![alt text](image.png)


## Architecture

- **Transport**: Streamable HTTP (`mcp.client.streamable_http`)
- **Protocol**: JSON-RPC 2.0 via MCP SDK
- **Session Management**: Automatic via `ClientSession`
- **Callbacks**:
  - `progress_callback`: Handles progress updates (0.0 to 1.0)
  - `logging_callback`: Handles server notifications and logs

## Available Tools

Run the client to see all available tools. Current tools:
- `generate_linkedin_post_streaming` - Generate posts with streaming updates
- `greet` - Simple greeting tool for testing

## Troubleshooting

**Connection refused**:
- Ensure the FastMCP server is running: `python api/main.py`
- Check the server URL in mcp_client.py matches your server (default: `http://localhost:8000/mcp`)

**No progress updates**:
- Progress callbacks only work with streaming-enabled tools
- Check server logs for errors

**Notifications not showing**:
- Ensure the tool uses `ctx.info()` or `ctx.debug()` methods on the server side
```
    tools = await client.list_tools()
    for tool in tools["tools"]:
        print(f"- {tool['name']}")

asyncio.run(example())
```

## Requirements

Install dependencies:
```bash
pip install -r requirements.txt
```

## Environment

The client expects the API server to be running at `http://localhost:8000` by default.

To use a different URL:
```python
client = MCPClient("https://your-api.azurewebsites.net")
```

Or in interactive mode, modify the base URL in the script.

## License

Same as parent project.
