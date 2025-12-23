"""
LangGraph state definition for the agentic post generator.

Defines the shared state structure that flows through all agent nodes.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class PostGeneratorState(BaseModel):
    """
    State schema for the post generator graph using Pydantic.
    
    This state is shared across all nodes (planner, writer, fact_checker, router).
    Each node can read from and write to this state.
    """
    
    # Input fields (provided by user/API)
    user_id: str = Field(..., description="User identifier")
    topic: str = Field(..., description="Topic to write about")
    platform: str = Field(default="linkedin", description="Target platform (linkedin, twitter, etc.)")
    tone: Optional[str] = Field(default=None, description="Writing tone (professional, casual, etc.)")
    
    # Planning phase
    plan: str = Field(default="", description="Structured outline created by planner")
    context: str = Field(default="", description="Retrieved context from FAISS/Azure AI Search")
    retrieved_docs: List[Dict[str, Any]] = Field(default_factory=list, description="List of retrieved document metadata")
    
    # Writing phase
    draft: str = Field(default="", description="Generated post content")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="History of agent messages")
    
    # Fact-checking phase
    scores: Dict[str, float] = Field(default_factory=dict, description="Evaluation scores (faithfulness, answer_relevancy)")
    needs_refinement: bool = Field(default=False, description="Whether the post needs to be rewritten")
    feedback: str = Field(default="", description="Feedback for refinement")
    
    # Refinement control
    refinement_count: int = Field(default=0, description="Number of refinement iterations")
    max_refinements: int = Field(default=3, description="Maximum allowed refinements")
    
    # Output
    final_post: str = Field(default="", description="Final approved post")
    thread_id: Optional[str] = Field(default=None, description="Thread identifier for tracing")
    
    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True
        json_schema_extra = {
            "example": {
                "user_id": "user-123",
                "topic": "Benefits of AI in healthcare",
                "platform": "linkedin",
                "tone": "professional"
            }
        }
