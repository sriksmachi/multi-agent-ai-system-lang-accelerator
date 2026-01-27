"""
Planner agent for creating post outlines.

This agent:
2. Creates a structured outline for the post
3. Returns plan with key points and grounding context
"""

from typing import Dict, Any, Optional, List
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from opentelemetry import trace
from core.azureopenai_client import AzureOpenAIClient
from core.logging_config import get_logger

tracer = trace.get_tracer(__name__)
logger = get_logger(__name__)

class PlannerAgent:
    """
    Planner agent that creates structured outlines for social media posts.
    Uses Azure OpenAI for planning.
    """
    
    def __init__(self):
        """Initialize the planner agent with Azure services and prompts."""
        
        # Initialize Azure OpenAI client with API key authentication
        self.openai_client = AzureOpenAIClient(use_managed_identity=False, use_api_key=False)
        
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
        self.thread_id = ""
    
    def _load_prompt(self, filename: str) -> str:
        """
        Load prompt from file.
        
        Args:
            filename: Name of the prompt file
            
        Returns:
            Prompt text content
        """
        # Get the directory where this file is located
        agent_dir = Path(__file__).parent
        prompt_path = agent_dir / "prompts" / filename
        
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            print(f"⚠️  Warning: Prompt file {filename} not found at {prompt_path}")
            return ""
    
    @tracer.start_as_current_span("PlannerAgent.create_plan")
    def create_plan(
        self, 
        state: Dict[str, Any], 
        config: Optional[RunnableConfig] = None
    ) -> Dict[str, Any]:
        """
        Create a structured plan for the post.
        
        Args:
            state: Current graph state with topic, platform, tone, etc.
            config: Optional runnable config for tracing
            
        Returns:
            Updated state with plan and retrieved context
        """
        print("🎯 PLANNER: Creating post outline...")
        
        # Set state variables
        self.thread_id = state.get("thread_id")
        self.topic = state.get("topic", "")
        self.platform = state.get("platform", "linkedin")
        self.tone = state.get("tone", "professional")
        self.user_id = state.get("user_id", "")
        
        with tracer.start_as_current_span("PlannerAgent.agent") as span:
            
            span.set_attribute("planner.input", str(state))
        
            # Log input
            logger.info(
                f"[{self.user_id}] PLANNER INPUT - thread_id: {self.thread_id}, topic: {self.topic}, platform: {self.platform}, tone: {self.tone}",
                extra={
                    "user_id": self.user_id,
                    "thread_id": self.thread_id,
                    "topic": self.topic,
                    "platform": self.platform,
                    "tone": self.tone,
                    "agent": "planner"
                }
            )
            
            # Generate plan using OpenAI client (without context - researcher will gather it)
            user_prompt = self.user_prompt_template.format(
                topic=self.topic,
                platform=self.platform,
                tone=self.tone
            )
            
            # Log the prompt being sent (truncated for brevity)
            logger.debug(
                f"[{self.user_id}] PLANNER - Sending prompt to OpenAI",
                extra={
                    "user_id": self.user_id,
                    "thread_id": self.thread_id,
                    "prompt_length": len(user_prompt),
                    "system_prompt_length": len(self.system_prompt),
                    "agent": "planner"
                }
            )
            
            self.plan = self.openai_client.generate_chat_completion(
                prompt=user_prompt,
                system_prompt=self.system_prompt
            )
            
            print(f"   📝 Plan created ({len(self.plan)} chars)")
            
            # Log output
            logger.info(
                f"[{self.user_id}][{self.thread_id}] PLANNER OUTPUT -,plan_length: {len(self.plan)} chars",
                extra={
                    "user_id": self.user_id,
                    "thread_id": self.thread_id,
                    "plan_length": len(self.plan),
                    "plan_preview": self.plan[:200] + "..." if len(self.plan) > 200 else self.plan,
                    "agent": "planner"
                }
            )
            
            # Update state
            state["plan"] = self.plan
            span.set_attribute("planner.output", str(state))
        return state

# Singleton instance
_planner_agent = None

def get_planner_agent() -> PlannerAgent:
    """Get or create the singleton planner agent instance."""
    global _planner_agent
    if _planner_agent is None:
        _planner_agent = PlannerAgent()
    return _planner_agent

def create_plan(state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """
    Node function for LangGraph integration.
    
    Args:
        state: Current graph state
        config: Optional runnable config
        
    Returns:
        Updated state with plan
    """
    agent = get_planner_agent()
    return agent.create_plan(state, config)
