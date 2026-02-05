"""
Researcher agent - retrieves relevant context from Azure AI Search.

This agent:
1. Takes the plan from the planner
2. Searches Azure AI Search for relevant context
3. Returns formatted context for the writer
"""

import os
from typing import Dict, Any, Optional, List
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from langchain_core.runnables import RunnableConfig
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from core.logging_config import get_logger

tracer = trace.get_tracer(__name__)
logger = get_logger(__name__)


class ResearcherAgent:
    """
    Researcher agent that retrieves relevant context from Azure AI Search.
    """
    
    def __init__(self):
        """Initialize the researcher agent with Azure AI Search."""
        
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
    
    def search_context(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search Azure AI Search for relevant context.
        
        Args:
            query: Search query
            top_k: Number of results to retrieve
            
        Returns:
            List of search results with content and scores
        """
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(
            "search.query",
            attributes={
                "search.query": query[:500],
                "search.index": self.search_index,
                "top_k": top_k
            }
        ) as span:
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
                
                span.set_attribute("search.results_count", len(docs))
                if docs:
                    span.set_attribute("search.top_score", docs[0]["score"])
                    span.set_attribute("search.avg_score", sum(d["score"] for d in docs) / len(docs))
                
                span.set_status(Status(StatusCode.OK))
                return docs
                
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                logger.warning(f"Azure AI Search failed: {e}")
                logger.error(f"Azure AI Search failed: {e}", exc_info=True)
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
    
    def research(self, state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
        """
        Research based on the plan from planner.
        
        Args:
            state: Current graph state with plan and topic
            config: Optional runnable config
            
        Returns:
            Updated state with context and retrieved documents
        """
        # Extract thread_id
        thread_id = state.get("thread_id")
        if config and isinstance(config, dict):
            thread_id = config.get("configurable", {}).get("thread_id", thread_id)
        
        user_id = state.get("user_id", "")
        topic = state.get("topic", "")
        plan = state.get("plan", "")
        
        logger.info(f"🔬 RESEARCHER: Retrieving context based on plan...")
        
        # Log input
        logger.info(
            f"[{user_id}][{thread_id}] RESEARCHER INPUT - topic: {topic}",
            extra={
                "user_id": user_id,
                "thread_id": thread_id,
                "topic": topic,
                "has_plan": bool(plan),
                "agent": "researcher"
            }
        )
        
        # Search for relevant context based on topic and plan
        # Use topic as primary search query
        logger.info(f"🔍 Searching Azure AI Search for: {topic}")
        retrieved_docs = self.search_context(topic, top_k=5)
        context_text = self.format_context(retrieved_docs)
        
        logger.info(f"✅ Retrieved {len(retrieved_docs)} documents")
        
        # Add to span
        current_span = trace.get_current_span()
        current_span.set_attribute("researcher.thread_id", thread_id or "")
        current_span.set_attribute("researcher.user_id", user_id)
        current_span.set_attribute("researcher.docs_count", len(retrieved_docs))
        current_span.set_attribute("researcher.context_length", len(context_text))
        
        # Log output
        logger.info(
            f"[{user_id}][{thread_id}] RESEARCHER OUTPUT - docs_count: {len(retrieved_docs)}",
            extra={
                "user_id": user_id,
                "thread_id": thread_id,
                "docs_count": len(retrieved_docs),
                "context_length": len(context_text),
                "agent": "researcher"
            }
        )
        
        # Update state
        state["context"] = context_text
        state["retrieved_docs"] = retrieved_docs
        
        return state


# Singleton instance
_researcher_agent = None

def get_researcher_agent() -> ResearcherAgent:
    """Get or create the singleton researcher agent instance."""
    global _researcher_agent
    if _researcher_agent is None:
        _researcher_agent = ResearcherAgent()
    return _researcher_agent

def research_topic(state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """
    Node function for LangGraph integration.
    
    Args:
        state: Current graph state
        config: Optional runnable config
        
    Returns:
        Updated state with context and retrieved documents
    """
    agent = get_researcher_agent()
    return agent.research(state, config)
