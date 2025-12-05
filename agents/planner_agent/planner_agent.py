"""
Planner agent for creating post outlines.

This agent:
1. Loads user preferences (tone, platform defaults) from LTM
2. Retrieves relevant context from FAISS/Azure AI Search
3. Creates a structured outline for the post
4. Returns plan with key points and grounding context
"""

import os
from typing import Dict, Any, Optional
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from lib.retriever import FaissRetriever
from lib.memory import LongTermMemory


def load_planner_prompt() -> str:
    """Load the planner system prompt from file."""
    prompt_path = os.path.join("prompts", "planner_system.txt")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # Fallback inline prompt
        return """You are a content planning specialist. Your job is to create a structured outline for social media posts.

Given:
- A topic to write about
- Platform (LinkedIn, Twitter, etc.)
- User's preferred tone
- Relevant research context

Create a detailed outline with:
1. Hook/opening line
2. 3-5 key points to cover
3. Call-to-action or closing thought
4. Suggested hashtags (if appropriate for platform)

Be specific and cite the context where relevant. Keep the outline concise but actionable."""


def create_plan(state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """
    Planner agent node function.
    
    Processes the user request and creates a structured plan for the post.
    
    Args:
        state (Dict): Current graph state with topic, platform, tone, etc.
        
    Returns:
        Dict: Updated state with plan and retrieved context
    """
    print("PLANNER: Creating post outline...")
    
    # Extract inputs from state
    topic = state.get("topic", "")
    platform = state.get("platform", "linkedin")
    tone = state.get("tone", "professional")
    user_id = state.get("user_id", "")
    
    # Load user preferences from LTM if available
    ltm = LongTermMemory()
    user_prefs = ltm.get_user_preferences(user_id)
    
    # Use LTM tone if not explicitly provided
    if user_prefs and not state.get("tone"):
        tone = user_prefs.get("preferred_tone", tone)
        print(f"   Using tone from LTM: {tone}")
    
    # Retrieve relevant context
    retriever = FaissRetriever(index_path=os.getenv("FAISS_INDEX_PATH", "./data/faiss_index"))
    retrieved_docs = retriever.search(topic, k=5)
    
    # Format context for LLM
    context_text = "\n\n".join([
        f"[Source {i+1}]: {doc.content[:500]}..."
        for i, doc in enumerate(retrieved_docs)
    ])
    
    print(f"   Retrieved {len(retrieved_docs)} context documents")
    
    # Create LLM
    llm = AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        temperature=0.7,
    )
    
    # Load prompt template
    system_prompt = load_planner_prompt()
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", """Topic: {topic}
Platform: {platform}
Tone: {tone}

Research Context:
{context}

Create a detailed outline for this post.""")
    ])
    
    # Generate plan
    chain = prompt | llm
    invoke_kwargs = {
        "topic": topic,
        "platform": platform,
        "tone": tone,
        "context": context_text,
    }
    if config:
        response = chain.invoke(invoke_kwargs, config=config)
    else:
        response = chain.invoke(invoke_kwargs)
    
    plan = response.content
    
    print(f"Plan created ({len(plan)} chars)")
    
    # Update state
    state["plan"] = plan
    state["context"] = context_text
    state["retrieved_docs"] = [{"content": doc.content, "score": doc.score} for doc in retrieved_docs]
    
    return state
