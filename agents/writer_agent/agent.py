"""
Writer agent for creating social media posts.

This agent:
1. Takes the plan and context from previous agents
2. Writes engaging social media content
3. Follows platform-specific guidelines
4. Incorporates feedback for refinements
"""

import os
from typing import Dict, Any, Optional
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from opentelemetry import trace
from core.azureopenai_client import AzureOpenAIClient
from core.logging_config import get_logger

tracer = trace.get_tracer(__name__)
logger = get_logger(__name__)


class WriterAgent:
    """
    Writer agent that creates social media posts based on plans and context.
    """
    
    def __init__(self):
        """Initialize the writer agent."""
        
        # Initialize Azure OpenAI client with API key authentication
        self.openai_client = AzureOpenAIClient(use_managed_identity=False, use_api_key=True)
        
        # Load prompts from files
        self.system_prompt = self._load_prompt("system_prompt.txt")
        self.user_prompt_template = self._load_prompt("user_prompt.txt")
        
        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", self.user_prompt_template)
        ])
        
        # State variables
        self.topic = ""
        self.platform = "linkedin"
        self.tone = "professional"
        self.user_id = ""
        self.plan = ""
        self.context = ""
        self.feedback = ""
        self.draft = ""
    
    def _load_prompt(self, filename: str) -> str:
        """
        Load prompt from file.
        
        Args:
            filename: Name of the prompt file
            
        Returns:
            Prompt text content
        """
        agent_dir = Path(__file__).parent
        prompt_path = agent_dir / "prompts" / filename
        
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Prompt file {filename} not found at {prompt_path}")
            return ""
    
    @tracer.start_as_current_span("WriterAgent.write_post")
    def write_post(
        self, 
        state: Dict[str, Any], 
        config: Optional[RunnableConfig] = None
    ) -> Dict[str, Any]:
        """
        Write a social media post based on plan and context.
        
        Args:
            state: Current graph state with plan, context, etc.
            config: Optional runnable config for tracing
            
        Returns:
            Updated state with draft
        """
        # Extract thread_id from config or state
        thread_id = state.get("thread_id")
        if config and isinstance(config, dict):
            thread_id = config.get("configurable", {}).get("thread_id", thread_id)
        
        # Set state variables
        self.topic = state.get("topic", "")
        self.platform = state.get("platform", "linkedin")
        self.tone = state.get("tone", "professional")
        self.user_id = state.get("user_id", "")
        self.plan = state.get("plan", "")
        self.context = state.get("context", "")
        self.feedback = state.get("feedback", "")
        refinement_count = state.get("refinement_count", 0)
        
        # Build feedback section
        feedback_text = ""
        if self.feedback and refinement_count > 0:
            feedback_text = f"\nFEEDBACK FROM REVIEWER (Refinement #{refinement_count}):\n{self.feedback}\n\nPlease address this feedback in your revision."
        
        action = "Refining post" if refinement_count > 0 else "Writing post"
        print(f"✍️  WRITER: {action} for {self.platform}...")
        
        # Log input
        logger.info(
            f"[{self.user_id}] WRITER INPUT - thread_id: {thread_id}, topic: {self.topic}, platform: {self.platform}, refinement: {refinement_count}",
            extra={
                "user_id": self.user_id,
                "thread_id": thread_id,
                "topic": self.topic,
                "platform": self.platform,
                "tone": self.tone,
                "refinement_count": refinement_count,
                "has_feedback": bool(self.feedback),
                "agent": "writer"
            }
        )
        
        # Set span attributes
        current_span = trace.get_current_span()
        current_span.set_attribute("writer.thread_id", thread_id or "")
        current_span.set_attribute("writer.user_id", self.user_id)
        current_span.set_attribute("writer.topic", self.topic)
        current_span.set_attribute("writer.platform", self.platform)
        current_span.set_attribute("writer.refinement_count", refinement_count)
        
        # Generate post using OpenAI client
        user_prompt = self.user_prompt_template.format(
            topic=self.topic,
            platform=self.platform,
            tone=self.tone,
            plan=self.plan,
            context=self.context,
            feedback=feedback_text
        )
        
        logger.debug(
            f"[{self.user_id}] WRITER - Sending prompt to OpenAI",
            extra={
                "user_id": self.user_id,
                "thread_id": thread_id,
                "prompt_length": len(user_prompt),
                "agent": "writer"
            }
        )
        
        self.draft = self.openai_client.generate_chat_completion(
            prompt=user_prompt,
            system_prompt=self.system_prompt
        )
        
        print(f"   📝 Draft created ({len(self.draft)} chars)")
        
        # Log output
        logger.info(
            f"[{self.user_id}] WRITER OUTPUT - thread_id: {thread_id}, draft_length: {len(self.draft)} chars",
            extra={
                "user_id": self.user_id,
                "thread_id": thread_id,
                "draft_length": len(self.draft),
                "draft_preview": self.draft[:200] + "..." if len(self.draft) > 200 else self.draft,
                "agent": "writer"
            }
        )
        
        # Update state
        state["draft"] = self.draft
        
        return state


# Singleton instance
_writer_agent = None

def get_writer_agent() -> WriterAgent:
    """Get or create the singleton writer agent instance."""
    global _writer_agent
    if _writer_agent is None:
        _writer_agent = WriterAgent()
    return _writer_agent

def write_post(state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """
    Node function for LangGraph integration.
    
    Args:
        state: Current graph state
        config: Optional runnable config
        
    Returns:
        Updated state with draft
    """
    agent = get_writer_agent()
    return agent.write_post(state, config)
