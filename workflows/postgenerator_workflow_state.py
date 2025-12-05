"""
LangGraph state definition for the agentic post generator.

Defines the shared state structure that flows through all agent nodes.
"""

from typing import TypedDict, List, Dict, Any, Optional


class PostGeneratorState(TypedDict, total=False):
    """
    State schema for the post generator graph.
    
    This state is shared across all nodes (planner, writer, fact_checker, router).
    Each node can read from and write to this state.
    
    Attributes:
        # Input fields (provided by user/API)
        user_id (str): User identifier
        session_id (str): Session/thread identifier
        topic (str): Topic to write about
        platform (str): Target platform (linkedin, twitter, etc.)
        tone (Optional[str]): Writing tone (professional, casual, etc.)
        
        # Planning phase
        plan (str): Structured outline created by planner
        context (str): Retrieved context from FAISS/Azure AI Search
        retrieved_docs (List[Dict]): List of retrieved document metadata
        
        # Writing phase
        draft (str): Generated post content
        messages (List[Dict]): History of agent messages
        
        # Fact-checking phase
        scores (Dict[str, float]): Evaluation scores (faithfulness, answer_relevancy)
        needs_refinement (bool): Whether the post needs to be rewritten
        feedback (str): Feedback for refinement
        
        # Refinement control
        refinement_count (int): Number of refinement iterations
        max_refinements (int): Maximum allowed refinements
        
        # Output
        final_post (str): Final approved post
        trace_id (Optional[str]): Langfuse trace ID
    """
    # Input fields
    user_id: str
    session_id: str
    topic: str
    platform: str
    tone: Optional[str]
    
    # Planning
    plan: str
    context: str
    retrieved_docs: List[Dict[str, Any]]
    
    # Writing
    draft: str
    messages: List[Dict[str, Any]]
    
    # Fact-checking
    scores: Dict[str, float]
    needs_refinement: bool
    feedback: str
    
    # Refinement
    refinement_count: int
    max_refinements: int
    
    # Output
    final_post: str
    trace_id: Optional[str]
