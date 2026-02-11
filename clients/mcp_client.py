import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Your FastMCP server root (or /mcp if custom path)
# for Local testing, use localhost. In production, use the internal service name (e.g., http://planner-agent:8003)
# for Azure Container Apps, use public URL from log of deploy-apps.ps1 script or Azure Portal (e.g., https://planner-agent-abc123.azurecontainerapps.io/mcp)
SERVER_URL = "https://ca-orchestrator-maala-acc.bravebay-65e1f8d4.westus2.azurecontainerapps.io/mcp"  

async def main():
    # Create the Streamable HTTP transport context manager
    async with streamablehttp_client(SERVER_URL) as (read_stream, write_stream, get_session_id):
        # Optional: Get session ID (useful for debugging multi-session servers)
        session_id = get_session_id()
        if session_id:
            print(f"Connected with session ID: {session_id}")
            
        async def handle_progress(progress, arg1, arg2):
            # Convert progress to percentage
            percentage = int(progress * 100)
            message =  arg2 if arg2 else "Processing..."
            print(f"\rProgress: {percentage}% - {message}", end="", flush=True)
                
        async def handle_log(notificationParams):
            print("\n🔔 Notification received:")
            print('=' * 40)
            print(f"Notification: {notificationParams.data[:50]}\n")
        
        # Create the client session (handles JSON-RPC protocol)
        async with ClientSession(read_stream, write_stream, logging_callback=handle_log) as session:
            await session.initialize()
            print("Initialized connection")

            # Discover tools
            tools_response = await session.list_tools()
            print("Available tools:")
            for tool in tools_response.tools:
                print(f" - {tool.name}: {tool.description}")

            # Call a streaming tool (e.g., your generate_linkedin_post_streaming)
            tool_name = "generate_linkedin_post_streaming"  # Replace with your tool name
            arguments = {"topic": "mango global supply chain in 10 words"}

            print(f"\nCalling tool: {tool_name}")
            
            result = await session.call_tool(
                tool_name,
                arguments=arguments,
                # Enable streaming notifications
               progress_callback=handle_progress
            )
            
            # Final result is now always in result.content
            full_content = "".join(block.text for block in result.content if hasattr(block, "text"))

            print("\n✅ Final post:\n")
            print(full_content)

asyncio.run(main())