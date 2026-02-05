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
import re
import time
import threading
import queue
from datetime import datetime
from typing import Optional, Dict, Any

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


async def call_mcp_tool(topic: str, user_id: str, progress_queue: queue.Queue, notification_queue: queue.Queue) -> dict:
    """
    Call the MCP server to generate content with progress and notification callbacks.
    
    Args:
        topic: The topic to generate content about
        user_id: User identifier  
        progress_queue: Queue to send progress updates
        notification_queue: Queue to send notification/log updates
        
    Returns:
        Result dictionary with content or error
    """
    try:
        progress_queue.put(("progress", "Connecting to MCP server...", 0.1))
        
        async def handle_progress(progress: float, total: float = None, message: str = None):
            """Handle progress notifications from MCP server."""
            if total and total > 0:
                percentage = progress / total
            else:
                percentage = progress if progress <= 1.0 else progress / 100.0
            msg = message if message else "Processing..."
            progress_queue.put(("progress", msg, percentage))
        
        async def handle_log(notification_params):
            """Handle log/info notifications from MCP server."""
            if hasattr(notification_params, 'data'):
                notification_queue.put(("log", notification_params.data))
            elif hasattr(notification_params, 'message'):
                notification_queue.put(("log", notification_params.message))
            else:
                notification_queue.put(("log", str(notification_params)))
            
        async with streamablehttp_client(MCP_SERVER_URL) as (read_stream, write_stream, get_session_id):
            async with ClientSession(read_stream, write_stream, logging_callback=handle_log) as session:
                progress_queue.put(("progress", "Initializing session...", 0.15))
                    
                await session.initialize()
                
                progress_queue.put(("progress", "Starting content generation...", 0.2))
                
                # Call the generate tool with progress callback
                result = await session.call_tool(
                    "generate_linkedin_post",
                    arguments={
                        "topic": topic,
                        "user_id": user_id
                    },
                    progress_callback=handle_progress
                )
                
                progress_queue.put(("progress", "Processing response...", 0.95))
                
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


def parse_notification(notification: str) -> Dict[str, Any]:
    """Parse notification text to extract tagged content."""
    result = {"type": "message", "content": notification}
    
    # Check for tagged content
    patterns = {
        "plan": r'\[PLAN\](.*?)\[/PLAN\]',
        "context": r'\[CONTEXT\](.*?)\[/CONTEXT\]',
        "draft": r'\[DRAFT\](.*?)\[/DRAFT\]',
        "scores": r'\[SCORES\](.*?)\[/SCORES\]',
        "feedback": r'\[FEEDBACK\](.*?)\[/FEEDBACK\]',
        "final": r'\[FINAL\](.*?)\[/FINAL\]',
        "result": r'\[RESULT\](.*?)\[/RESULT\]',
    }
    
    for tag, pattern in patterns.items():
        match = re.search(pattern, notification, re.DOTALL)
        if match:
            content = match.group(1).strip()
            if tag == "scores":
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    pass
            elif tag == "result":
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    pass
            return {"type": tag, "content": content}
    
    return result


def generate_content_with_progress(
    topic: str, 
    user_id: str, 
    progress_placeholder, 
    status_placeholder,
    plan_placeholder=None,
    draft_placeholder=None,
    final_placeholder=None
) -> Optional[Dict[str, Any]]:
    """
    Generate content with visual progress updates using MCP client.
    
    Args:
        topic: The topic to generate content about
        user_id: User identifier
        progress_placeholder: Streamlit placeholder for progress bar
        status_placeholder: Streamlit placeholder for status text
        plan_placeholder: Optional placeholder for plan display
        draft_placeholder: Optional placeholder for draft display
        final_placeholder: Optional placeholder for final post display
        
    Returns:
        Result dict with content and intermediate results, or None if failed
    """
    result_queue = queue.Queue()
    progress_queue = queue.Queue()
    notification_queue = queue.Queue()
    
    # Track intermediate results
    intermediate_results = {
        "plan": "",
        "context": "",
        "draft": "",
        "final_post": "",
        "scores": {},
        "feedback": ""
    }
    
    def run_async_call():
        """Run the async MCP call in a separate thread."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                call_mcp_tool(topic, user_id, progress_queue, notification_queue)
            )
            result_queue.put(("success", result))
        except Exception as e:
            result_queue.put(("error", {"status": "error", "error": str(e)}))
        finally:
            loop.close()
    
    # Start MCP call in background thread
    thread = threading.Thread(target=run_async_call)
    thread.start()
    
    # Track what we've displayed
    displayed = {"plan": False, "draft": False, "final": False}
    
    while thread.is_alive():
        # Check for progress updates
        try:
            while not progress_queue.empty():
                msg_type, message, progress = progress_queue.get_nowait()
                if msg_type == "progress":
                    progress_placeholder.progress(min(progress, 0.99))
                    status_placeholder.info(f"🔄 {message}")
        except queue.Empty:
            pass
        
        # Check for notification updates (intermediate results)
        try:
            while not notification_queue.empty():
                msg_type, notification = notification_queue.get_nowait()
                if msg_type == "log":
                    parsed = parse_notification(notification)
                    
                    if parsed["type"] == "plan":
                        intermediate_results["plan"] = parsed["content"]
                        if plan_placeholder and not displayed["plan"]:
                            plan_placeholder.markdown(parsed["content"])
                            displayed["plan"] = True
                            status_placeholder.info("🎯 Plan created!")
                    
                    elif parsed["type"] == "context":
                        intermediate_results["context"] = parsed["content"]
                        status_placeholder.info("🔍 Research complete!")
                    
                    elif parsed["type"] == "draft":
                        intermediate_results["draft"] = parsed["content"]
                        if draft_placeholder and not displayed["draft"]:
                            draft_placeholder.markdown(parsed["content"])
                            displayed["draft"] = True
                            status_placeholder.info("✍️ Draft written!")
                    
                    elif parsed["type"] == "scores":
                        intermediate_results["scores"] = parsed["content"]
                        if isinstance(parsed["content"], dict):
                            scores_text = " | ".join([
                                f"**{k}**: {v:.2f}" if isinstance(v, float) else f"**{k}**: {v}" 
                                for k, v in parsed["content"].items()
                            ])
                            status_placeholder.info(f"📊 Scores: {scores_text}")
                    
                    elif parsed["type"] == "feedback":
                        intermediate_results["feedback"] = parsed["content"]
                        status_placeholder.info("📝 Review complete!")
                    
                    elif parsed["type"] == "final":
                        intermediate_results["final_post"] = parsed["content"]
                        if final_placeholder and not displayed["final"]:
                            final_placeholder.markdown(parsed["content"])
                            displayed["final"] = True
                    
                    elif parsed["type"] == "result":
                        if isinstance(parsed["content"], dict):
                            intermediate_results.update(parsed["content"])
                            
        except queue.Empty:
            pass
            
        time.sleep(0.1)
    
    thread.join()
    
    # Get final result
    try:
        result_type, result_data = result_queue.get(timeout=1)
        
        progress_placeholder.progress(1.0)
        
        if result_type == "success" and result_data.get("status") == "success":
            status_placeholder.success("✅ Content generated successfully!")
            
            # Use final_post from intermediate if available, otherwise from result
            final_content = intermediate_results.get("final_post") or result_data.get("content", "")
            
            return {
                "status": "success",
                "content": final_content,
                "intermediate": intermediate_results
            }
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
                    metadata = message["metadata"]
                    with st.expander("📊 Details"):
                        # Show plan if available
                        if metadata.get("plan"):
                            st.markdown("**🎯 Plan:**")
                            st.markdown(metadata["plan"])
                            st.markdown("---")
                        
                        # Show draft if different from final
                        if metadata.get("draft") and metadata.get("draft") != message["content"]:
                            st.markdown("**✍️ Draft:**")
                            st.markdown(metadata["draft"])
                            st.markdown("---")
                        
                        # Show scores if available
                        if metadata.get("scores"):
                            st.markdown("**📊 Quality Scores:**")
                            for key, value in metadata["scores"].items():
                                if isinstance(value, float):
                                    st.metric(key.replace("_", " ").title(), f"{value:.2f}")
                                else:
                                    st.metric(key.replace("_", " ").title(), str(value))
                            st.markdown("---")
                        
                        # Show feedback if available
                        if metadata.get("feedback"):
                            st.markdown("**💬 Reviewer Feedback:**")
                            st.markdown(metadata["feedback"])
                            st.markdown("---")
                        
                        # Basic metadata
                        st.json({
                            "topic": metadata.get("topic", ""),
                            "user_id": metadata.get("user_id", ""),
                            "timestamp": metadata.get("timestamp", "")
                        })
    
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
            # Create placeholders for progress and intermediate content
            status_placeholder = st.empty()
            progress_placeholder = st.empty()
            
            # Expandable sections for intermediate results
            plan_expander = st.expander("🎯 **Content Plan**", expanded=True)
            plan_placeholder = plan_expander.empty()
            
            draft_expander = st.expander("✍️ **Draft**", expanded=False)
            draft_placeholder = draft_expander.empty()
            
            st.markdown("---")
            st.markdown("### 📝 Final Post")
            final_placeholder = st.empty()
            
            # Update workflow status
            st.session_state.workflow_status = {
                "planner": "running",
                "researcher": "pending",
                "writer": "pending",
                "reviewer": "pending"
            }
            
            # Generate content with intermediate updates
            result = generate_content_with_progress(
                topic=prompt,
                user_id=user_id,
                progress_placeholder=progress_placeholder,
                status_placeholder=status_placeholder,
                plan_placeholder=plan_placeholder,
                draft_placeholder=draft_placeholder,
                final_placeholder=final_placeholder
            )
            
            if result:
                # Clear progress indicators
                progress_placeholder.empty()
                status_placeholder.empty()
                
                # Get results
                intermediate = result.get("intermediate", {})
                final_content = result.get("content", "")
                
                # Display final content if not already shown
                if final_content:
                    final_placeholder.markdown(final_content)
                
                # Show success message with scores
                scores = intermediate.get("scores", {})
                if scores:
                    scores_text = " | ".join([
                        f"**{k.replace('_', ' ').title()}**: {v:.2f}" if isinstance(v, float) else f"**{k}**: {v}" 
                        for k, v in scores.items()
                    ])
                    st.success(f"✅ Generated! {scores_text}")
                else:
                    st.success("✅ Content generated successfully!")
                
                # Add to chat history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": final_content,
                    "avatar": "🤖",
                    "metadata": {
                        "topic": prompt,
                        "user_id": user_id,
                        "timestamp": datetime.now().isoformat(),
                        "plan": intermediate.get("plan", ""),
                        "draft": intermediate.get("draft", ""),
                        "scores": scores,
                        "feedback": intermediate.get("feedback", "")
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
                final_placeholder.error("Failed to generate content. Please try again.")
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
