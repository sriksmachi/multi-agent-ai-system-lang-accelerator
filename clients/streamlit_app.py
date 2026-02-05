"""
Streamlit Chat Interface for Multi-Agent AI System

A chat-based UI that connects to the orchestrator API via MCP protocol and shows:
- Real-time progress updates
- Incremental content generation
- Agent workflow visualization
"""

import streamlit as st
import asyncio
import json
import time
import threading
import queue
from datetime import datetime
from typing import Optional

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Configuration
ORCHESTRATOR_URL = "http://localhost:8000"
MCP_SERVER_URL = f"{ORCHESTRATOR_URL}/mcp"

# Page configuration
st.set_page_config(
    page_title="Multi-Agent Content Generator",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .stProgress > div > div > div > div {
        background-color: #4CAF50;
    }
    .agent-message {
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
    }
    .planner-msg { background-color: #E3F2FD; }
    .researcher-msg { background-color: #F3E5F5; }
    .writer-msg { background-color: #E8F5E9; }
    .reviewer-msg { background-color: #FFF3E0; }
    .status-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }
    .status-running { background-color: #FFF9C4; color: #F57F17; }
    .status-complete { background-color: #C8E6C9; color: #2E7D32; }
    .status-error { background-color: #FFCDD2; color: #C62828; }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_workflow" not in st.session_state:
        st.session_state.current_workflow = None
    if "workflow_status" not in st.session_state:
        st.session_state.workflow_status = {}


def check_orchestrator_health() -> bool:
    """Check if orchestrator is healthy by trying the MCP endpoint."""
    import httpx
    try:
        # Try the root endpoint
        response = httpx.get(f"{ORCHESTRATOR_URL}/", timeout=5.0)
        if response.status_code < 500:
            return True
    except Exception:
        pass
    return False


async def call_mcp_tool(topic: str, user_id: str, progress_callback=None) -> dict:
    """
    Call the MCP server to generate content.
    
    Args:
        topic: The topic to generate content about
        user_id: User identifier  
        progress_callback: Optional callback for progress updates
        
    Returns:
        Result dictionary with content or error
    """
    try:
        if progress_callback:
            progress_callback("Connecting to MCP server...", 0.1)
            
        async with streamablehttp_client(MCP_SERVER_URL) as (read_stream, write_stream, get_session_id):
            async with ClientSession(read_stream, write_stream) as session:
                if progress_callback:
                    progress_callback("Initializing session...", 0.15)
                    
                await session.initialize()
                
                if progress_callback:
                    progress_callback("Starting content generation...", 0.2)
                
                # Call the generate tool
                result = await session.call_tool(
                    "generate_linkedin_post",
                    arguments={
                        "topic": topic,
                        "user_id": user_id
                    }
                )
                
                if progress_callback:
                    progress_callback("Processing response...", 0.9)
                
                # Extract content from result
                if result and result.content:
                    for content_item in result.content:
                        if hasattr(content_item, 'text'):
                            return {
                                "status": "success",
                                "content": content_item.text
                            }
                
                return {
                    "status": "error",
                    "error": "No content in response"
                }
                
    except Exception as e:
        return {
            "status": "error", 
            "error": str(e)
        }


def generate_content_with_progress(topic: str, user_id: str, progress_placeholder, status_placeholder) -> Optional[str]:
    """
    Generate content with visual progress updates using MCP client.
    
    Args:
        topic: The topic to generate content about
        user_id: User identifier
        progress_placeholder: Streamlit placeholder for progress bar
        status_placeholder: Streamlit placeholder for status text
        
    Returns:
        Generated content or None if failed
    """
    stages = [
        ("🎯 Planning", "Planner agent creating content outline...", 0.3),
        ("🔍 Researching", "Researcher agent gathering relevant context...", 0.5),
        ("✍️ Writing", "Writer agent drafting content...", 0.7),
        ("📝 Reviewing", "Reviewer agent evaluating quality...", 0.9),
    ]
    
    result_queue = queue.Queue()
    progress_queue = queue.Queue()
    
    def progress_callback(message: str, progress: float):
        """Callback for progress updates from MCP call."""
        progress_queue.put((message, progress))
    
    def run_async_call():
        """Run the async MCP call in a separate thread."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                call_mcp_tool(topic, user_id, progress_callback)
            )
            result_queue.put(("success", result))
        except Exception as e:
            result_queue.put(("error", {"status": "error", "error": str(e)}))
        finally:
            loop.close()
    
    # Start MCP call in background thread
    thread = threading.Thread(target=run_async_call)
    thread.start()
    
    # Show progress while waiting
    stage_idx = 0
    start_time = time.time()
    
    while thread.is_alive():
        # Check for progress updates from callback
        try:
            while not progress_queue.empty():
                message, progress = progress_queue.get_nowait()
                progress_placeholder.progress(progress)
                status_placeholder.info(f"🔄 {message}")
        except queue.Empty:
            pass
        
        # Show stage-based progress if no callback updates
        elapsed = time.time() - start_time
        if stage_idx < len(stages) and elapsed > (stage_idx + 1) * 10:  # Every 10 seconds
            emoji, message, progress = stages[stage_idx]
            progress_placeholder.progress(progress)
            status_placeholder.info(f"{emoji} {message}")
            stage_idx += 1
            
        time.sleep(0.5)
    
    thread.join()
    
    # Get result
    try:
        result_type, result_data = result_queue.get(timeout=1)
        
        progress_placeholder.progress(1.0)
        
        if result_type == "success" and result_data.get("status") == "success":
            status_placeholder.success("✅ Content generated successfully!")
            return result_data.get("content", "")
        else:
            error_msg = result_data.get("error", "Unknown error")
            status_placeholder.error(f"❌ Error: {error_msg}")
            return None
            
    except queue.Empty:
        status_placeholder.error("❌ Timeout waiting for response")
        return None


def display_agent_status(status: dict):
    """Display the current status of each agent."""
    agents = ["Planner", "Researcher", "Writer", "Reviewer"]
    cols = st.columns(4)
    
    for i, agent in enumerate(agents):
        with cols[i]:
            agent_status = status.get(agent.lower(), "pending")
            if agent_status == "running":
                st.markdown(f"🔄 **{agent}**")
                st.caption("Running...")
            elif agent_status == "complete":
                st.markdown(f"✅ **{agent}**")
                st.caption("Complete")
            elif agent_status == "error":
                st.markdown(f"❌ **{agent}**")
                st.caption("Error")
            else:
                st.markdown(f"⏳ **{agent}**")
                st.caption("Pending")


def main():
    """Main application entry point."""
    init_session_state()
    
    # Header
    st.title("🤖 Multi-Agent Content Generator")
    st.markdown("Generate high-quality LinkedIn posts using our multi-agent AI system.")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # Health check
        health_status = check_orchestrator_health()
        if health_status:
            st.success("✅ Orchestrator Connected")
        else:
            st.error("❌ Orchestrator Offline")
            st.caption(f"Make sure the orchestrator is running at {ORCHESTRATOR_URL}")
        
        st.divider()
        
        # User settings
        user_id = st.text_input("User ID", value=f"streamlit-user-{datetime.now().strftime('%Y%m%d')}")
        
        st.divider()
        
        # Agent status
        st.subheader("🔄 Workflow Status")
        if st.session_state.workflow_status:
            display_agent_status(st.session_state.workflow_status)
        else:
            st.caption("No active workflow")
        
        st.divider()
        
        # Quick actions
        st.subheader("🚀 Quick Actions")
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.workflow_status = {}
            st.rerun()
        
        if st.button("🔄 Check Health", use_container_width=True):
            st.rerun()
    
    # Main chat interface
    chat_container = st.container()
    
    # Display chat history
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"], avatar=message.get("avatar")):
                st.markdown(message["content"])
                if "metadata" in message:
                    with st.expander("📊 Details"):
                        st.json(message["metadata"])
    
    # Chat input
    if prompt := st.chat_input("Enter a topic to generate a LinkedIn post about..."):
        if not health_status:
            st.error("❌ Cannot generate content: Orchestrator is offline")
            return
        
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
            "avatar": "👤"
        })
        
        # Display user message
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant", avatar="🤖"):
            # Create placeholders for progress
            status_placeholder = st.empty()
            progress_placeholder = st.empty()
            content_placeholder = st.empty()
            
            # Update workflow status
            st.session_state.workflow_status = {
                "planner": "running",
                "researcher": "pending",
                "writer": "pending",
                "reviewer": "pending"
            }
            
            # Generate content
            content = generate_content_with_progress(
                topic=prompt,
                user_id=user_id,
                progress_placeholder=progress_placeholder,
                status_placeholder=status_placeholder
            )
            
            if content:
                # Clear progress indicators
                progress_placeholder.empty()
                status_placeholder.empty()
                
                # Display generated content
                content_placeholder.markdown(content)
                
                # Add to chat history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": content,
                    "avatar": "🤖",
                    "metadata": {
                        "topic": prompt,
                        "user_id": user_id,
                        "timestamp": datetime.now().isoformat(),
                        "agents": ["planner", "researcher", "writer", "reviewer"]
                    }
                })
                
                # Update workflow status
                st.session_state.workflow_status = {
                    "planner": "complete",
                    "researcher": "complete",
                    "writer": "complete",
                    "reviewer": "complete"
                }
            else:
                content_placeholder.error("Failed to generate content. Please try again.")
                st.session_state.workflow_status = {
                    "planner": "error",
                    "researcher": "error",
                    "writer": "error",
                    "reviewer": "error"
                }
    
    # Footer
    st.divider()
    st.caption("Built with LangGraph, FastMCP, and Azure AI Services")


if __name__ == "__main__":
    main()
