"""
Planner agent for creating post outlines.

This agent:
1. Retrieves relevant context from Azure AI Search
2. Creates a structured outline for the post
3. Returns plan with key points and grounding context
"""

import os
from typing import Dict, Any, Optional, List
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


class PlannerAgent:
    """
    Planner agent that creates structured outlines for social media posts.
    Uses Azure AI Search for context retrieval and Azure OpenAI for planning.
    """
    
    def __init__(self):
        """Initialize the planner agent with Azure services and prompts."""
        # Azure OpenAI configuration
        self.azure_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        
        # Azure AI Search configuration
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.search_key = os.getenv("AZURE_SEARCH_ADMIN_KEY")
        self.search_index = os.getenv("AZURE_SEARCH_INDEX_NAME", "documents-index")
        
        # Initialize Azure AI Search client
        self.search_client = SearchClient(
            endpoint=self.search_endpoint,
            index_name=self.search_index,
            credential=AzureKeyCredential(self.search_key)
        )
        
        # Initialize Azure OpenAI LLM
        project_client = AIProjectClient(credential=DefaultAzureCredential(), project_url=os.getenv("AZURE_FOUNDRY_PROJECT_URL"))
        self.llm = project_client.get_openai_client()
        
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
        self.retrieved_docs = []
        self.context_text = ""
        self.plan = ""
    
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
    
    def search_context(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search Azure AI Search for relevant context.
        
        Args:
            query: Search query
            top_k: Number of results to retrieve
            
        Returns:
            List of search results with content and scores
        """
        try:
            results = self.search_client.search(
                search_text=query,
                top=top_k,
                select=["content", "title", "source", "chunk_id"]
            )
            
            docs = []
            for result in results:
                docs.append({
                    "content": result.get("content", ""),
                    "title": result.get("title", ""),
                    "source": result.get("source", ""),
                    "score": result.get("@search.score", 0.0)
                })
            
            return docs
            
        except Exception as e:
            print(f"⚠️  Warning: Azure AI Search failed: {e}")
            return []
    
    def format_context(self, docs: List[Dict[str, Any]]) -> str:
        """
        Format retrieved documents into context text.
        
        Args:
            docs: List of retrieved documents
            
        Returns:
            Formatted context string
        """
        if not docs:
            return "No additional context available."
        
        context_parts = []
        for i, doc in enumerate(docs):
            title = doc.get("title", "Untitled")
            content = doc.get("content", "")[:500]  # Limit content length
            source = doc.get("source", "Unknown")
            
            context_parts.append(
                f"[Source {i+1}] {title} (from {source}):\n{content}..."
            )
        
        return "\n\n".join(context_parts)
    
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
        self.topic = state.get("topic", "")
        self.platform = state.get("platform", "linkedin")
        self.tone = state.get("tone", "professional")
        self.user_id = state.get("user_id", "")
        
        # Retrieve relevant context from Azure AI Search
        print(f"   🔍 Searching Azure AI Search for: {self.topic}")
        self.retrieved_docs = self.search_context(self.topic, top_k=5)
        self.context_text = self.format_context(self.retrieved_docs)
        
        print(f"   ✅ Retrieved {len(self.retrieved_docs)} documents")
        
        # Generate plan using LLM
        chain = self.prompt | self.llm
        invoke_kwargs = {
            "topic": self.topic,
            "platform": self.platform,
            "tone": self.tone,
            "context": self.context_text,
        }
        
        if config:
            response = chain.invoke(invoke_kwargs, config=config)
        else:
            response = chain.invoke(invoke_kwargs)
        
        self.plan = response.content
        
        print(f"   📝 Plan created ({len(self.plan)} chars)")
        
        # Update state
        state["plan"] = self.plan
        state["context"] = self.context_text
        state["retrieved_docs"] = self.retrieved_docs
        
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
