"""
Task-oriented LangGraph workflow for social media post generation.

Implements the Planner → Researcher → Writer → Reviewer pattern with:
- OpenTelemetry (OTEL) tracing for observability
- User ID and conversation ID tracking
- Proper error handling and logging
- LangGraph state management using Pydantic models
"""

import os
import logging
from typing import Literal, Dict, Any
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from .postgenerator_workflow_state import PostGeneratorState
from core.logging_config import get_logger

# Initialize logger and tracer
logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)


# ============================================================================
# PLANNER NODE - Creates structured outline and strategy
# ============================================================================

def planner_node(state: PostGeneratorState) -> Dict[str, Any]:
    """
    Planner Agent: Creates a structured outline for the post.
    
    Responsibilities:
    - Understand the topic and target platform
    - Determine key points to cover
    - Identify information needs for researcher
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with plan
    """
    user_id = state.user_id
    topic = state.topic
    platform = state.platform
    
    with tracer.start_as_current_span(
        "planner_node",
        attributes={
            "user_id": user_id,
            "topic": topic,
            "platform": platform,
        }
    ) as span:
        try:
            logger.info(
                f"[{user_id}] PLANNER: Creating outline for topic '{topic}' on {platform}",
                extra={"user_id": user_id, "topic": topic, "platform": platform}
            )
            
            # Import here to avoid circular dependencies
            from agents.planner_agent.planner_agent import create_plan
            
            # Create plan
            plan_result = create_plan(state.model_dump())
            
            # Update state
            updates = {
                "plan": plan_result.get("plan", ""),
                "messages": state.messages + [{
                    "role": "planner",
                    "content": plan_result.get("plan", ""),
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }
            
            span.set_attribute("plan_length", len(updates["plan"]))
            span.set_status(Status(StatusCode.OK))
            
            logger.info(
                f"[{user_id}] PLANNER: Created plan with {len(updates['plan'])} characters",
                extra={"user_id": user_id, "plan_length": len(updates["plan"])}
            )
            
            return updates
            
        except Exception as e:
            logger.error(
                f"[{user_id}] PLANNER: Error creating plan: {e}",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True
            )
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


# ============================================================================
# RESEARCHER NODE - Retrieves relevant context
# ============================================================================

def researcher_node(state: PostGeneratorState) -> Dict[str, Any]:
    """
    Researcher Agent: Retrieves relevant context and information.
    
    Responsibilities:
    - Search knowledge base for relevant information
    - Retrieve supporting facts and data
    - Provide context for writer
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with context and retrieved documents
    """
    user_id = state.user_id
    topic = state.topic
    plan = state.plan
    
    with tracer.start_as_current_span(
        "researcher_node",
        attributes={
            "user_id": user_id,
            "topic": topic,
            "has_plan": bool(plan),
        }
    ) as span:
        try:
            logger.info(
                f"[{user_id}] RESEARCHER: Retrieving context for topic '{topic}'",
                extra={"user_id": user_id, "topic": topic}
            )
            
            # Import here to avoid circular dependencies
            from agents.researcher_agent.agent import research_topic
            
            # Perform research
            research_result = research_topic(state.model_dump())
            
            # Update state
            retrieved_docs = research_result.get("retrieved_docs", [])
            context = research_result.get("context", "")
            
            updates = {
                "context": context,
                "retrieved_docs": retrieved_docs,
                "messages": state.messages + [{
                    "role": "researcher",
                    "content": f"Retrieved {len(retrieved_docs)} documents",
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }
            
            span.set_attribute("docs_retrieved", len(retrieved_docs))
            span.set_attribute("context_length", len(context))
            span.set_status(Status(StatusCode.OK))
            
            logger.info(
                f"[{user_id}] RESEARCHER: Retrieved {len(retrieved_docs)} documents, {len(context)} chars of context",
                extra={
                    "user_id": user_id,
                    "docs_count": len(retrieved_docs),
                    "context_length": len(context)
                }
            )
            
            return updates
            
        except Exception as e:
            logger.error(
                f"[{user_id}] RESEARCHER: Error retrieving context: {e}",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True
            )
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


# ============================================================================
# WRITER NODE - Generates post content
# ============================================================================

def writer_node(state: PostGeneratorState) -> Dict[str, Any]:
    """
    Writer Agent: Generates the social media post.
    
    Responsibilities:
    - Write post based on plan and context
    - Follow platform-specific guidelines
    - Apply requested tone and style
    - Incorporate feedback if refining
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with draft
    """
    user_id = state.user_id
    topic = state.topic
    platform = state.platform
    refinement_count = state.refinement_count
    
    with tracer.start_as_current_span(
        "writer_node",
        attributes={
            "user_id": user_id,
            "topic": topic,
            "platform": platform,
            "refinement_count": refinement_count,
        }
    ) as span:
        try:
            is_refinement = refinement_count > 0
            action = "Refining" if is_refinement else "Writing"
            
            logger.info(
                f"[{user_id}] WRITER: {action} post for {platform} (attempt {refinement_count + 1})",
                extra={
                    "user_id": user_id,
                    "platform": platform,
                    "refinement_count": refinement_count,
                    "is_refinement": is_refinement
                }
            )
            
            # Import here to avoid circular dependencies
            from agents.reviewer_agent.agent import write_post
            
            # Generate post
            write_result = write_post(state.model_dump())
            
            # Update state
            draft = write_result.get("draft", "")
            updates = {
                "draft": draft,
                "messages": state.messages + [{
                    "role": "writer",
                    "content": draft,
                    "timestamp": datetime.utcnow().isoformat(),
                    "refinement": refinement_count
                }]
            }
            
            span.set_attribute("draft_length", len(draft))
            span.set_attribute("is_refinement", is_refinement)
            span.set_status(Status(StatusCode.OK))
            
            logger.info(
                f"[{user_id}] WRITER: Generated draft with {len(draft)} characters",
                extra={
                    "user_id": user_id,
                    "draft_length": len(draft),
                    "refinement_count": refinement_count
                }
            )
            
            return updates
            
        except Exception as e:
            logger.error(
                f"[{user_id}] WRITER: Error generating post: {e}",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True
            )
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


# ============================================================================
# REVIEWER NODE - Evaluates quality and provides feedback
# ============================================================================

def reviewer_node(state: PostGeneratorState) -> Dict[str, Any]:
    """
    Reviewer Agent: Evaluates post quality and provides feedback.
    
    Responsibilities:
    - Check factual accuracy
    - Assess relevancy to topic
    - Evaluate tone and style
    - Determine if refinement is needed
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with scores, feedback, and refinement decision
    """
    user_id = state.user_id
    draft = state.draft
    topic = state.topic
    
    with tracer.start_as_current_span(
        "reviewer_node",
        attributes={
            "user_id": user_id,
            "topic": topic,
            "draft_length": len(draft),
        }
    ) as span:
        try:
            logger.info(
                f"[{user_id}] REVIEWER: Evaluating post quality",
                extra={"user_id": user_id, "draft_length": len(draft)}
            )
            
            # Import here to avoid circular dependencies
            from agents.reviewer_agent.agent import check_facts
            
            # Review post
            review_result = check_facts(state.model_dump())
            
            # Extract results
            scores = review_result.get("scores", {})
            feedback = review_result.get("feedback", "")
            needs_refinement = review_result.get("needs_refinement", False)
            
            # Update state
            updates = {
                "scores": scores,
                "feedback": feedback,
                "needs_refinement": needs_refinement,
                "messages": state.messages + [{
                    "role": "reviewer",
                    "content": feedback,
                    "scores": scores,
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }
            
            # Add telemetry
            for metric, value in scores.items():
                span.set_attribute(f"score_{metric}", value)
            span.set_attribute("needs_refinement", needs_refinement)
            span.set_status(Status(StatusCode.OK))
            
            logger.info(
                f"[{user_id}] REVIEWER: Scores - {scores}, Needs refinement: {needs_refinement}",
                extra={
                    "user_id": user_id,
                    "scores": scores,
                    "needs_refinement": needs_refinement
                }
            )
            
            return updates
            
        except Exception as e:
            logger.error(
                f"[{user_id}] REVIEWER: Error evaluating post: {e}",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True
            )
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


# ============================================================================
# ROUTER NODE - Decides next action
# ============================================================================

def router_node(state: PostGeneratorState) -> Dict[str, Any]:
    """
    Router: Decides whether to refine or finalize the post.
    
    Decision logic:
    - If quality is acceptable: finalize
    - If below threshold and refinements available: refine
    - If max refinements reached: finalize anyway
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with final_post if ending
    """
    user_id = state.user_id
    needs_refinement = state.needs_refinement
    refinement_count = state.refinement_count
    max_refinements = state.max_refinements
    
    with tracer.start_as_current_span(
        "router_node",
        attributes={
            "user_id": user_id,
            "needs_refinement": needs_refinement,
            "refinement_count": refinement_count,
            "max_refinements": max_refinements,
        }
    ) as span:
        try:
            logger.info(
                f"[{user_id}] ROUTER: Making routing decision",
                extra={
                    "user_id": user_id,
                    "needs_refinement": needs_refinement,
                    "refinement_count": refinement_count,
                    "max_refinements": max_refinements
                }
            )
            
            updates = {}
            
            if not needs_refinement:
                # Quality is acceptable
                updates["final_post"] = state.draft
                decision = "finalize"
                logger.info(
                    f"[{user_id}] ROUTER: Quality acceptable, finalizing post",
                    extra={"user_id": user_id, "decision": decision}
                )
            elif refinement_count >= max_refinements:
                # Max refinements reached
                updates["final_post"] = state.draft
                updates["needs_refinement"] = False
                decision = "finalize (max refinements)"
                logger.warning(
                    f"[{user_id}] ROUTER: Max refinements ({max_refinements}) reached, finalizing anyway",
                    extra={
                        "user_id": user_id,
                        "decision": decision,
                        "refinement_count": refinement_count
                    }
                )
            else:
                # Needs refinement
                updates["refinement_count"] = refinement_count + 1
                decision = f"refine (attempt {refinement_count + 2})"
                logger.info(
                    f"[{user_id}] ROUTER: Sending back for refinement (attempt {refinement_count + 2}/{max_refinements})",
                    extra={
                        "user_id": user_id,
                        "decision": decision,
                        "next_refinement": refinement_count + 1
                    }
                )
            
            span.set_attribute("decision", decision)
            span.set_status(Status(StatusCode.OK))
            
            return updates
            
        except Exception as e:
            logger.error(
                f"[{user_id}] ROUTER: Error making routing decision: {e}",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True
            )
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


# ============================================================================
# CONDITIONAL ROUTING FUNCTION
# ============================================================================

def should_refine(state: PostGeneratorState) -> Literal["refine", "end"]:
    """
    Conditional edge function for routing decision.
    
    Args:
        state: Current workflow state
        
    Returns:
        "refine" to loop back to writer, "end" to finish
    """
    needs_refinement = state.needs_refinement
    refinement_count = state.refinement_count
    max_refinements = state.max_refinements
    
    # Finalize if quality is good or max refinements reached
    if not needs_refinement or refinement_count >= max_refinements:
        return "end"
    
    # Otherwise, refine
    return "refine"


# ============================================================================
# WORKFLOW BUILDER
# ============================================================================

def build_post_generator_workflow() -> StateGraph:
    """
    Build the post generator LangGraph workflow.
    
    Workflow structure:
    1. Planner → Creates outline
    2. Researcher → Retrieves context
    3. Writer → Generates post
    4. Reviewer → Evaluates quality
    5. Router → Decides refine or end
    6. (Optional) Loop back to Writer for refinement
    
    Returns:
        Compiled StateGraph ready for execution
    """
    with tracer.start_as_current_span("build_workflow") as span:
        logger.info("Building post generator workflow")
        
        # Create workflow
        workflow = StateGraph(PostGeneratorState)
        
        # Add nodes
        workflow.add_node("planner", planner_node)
        workflow.add_node("researcher", researcher_node)
        workflow.add_node("writer", writer_node)
        workflow.add_node("reviewer", reviewer_node)
        workflow.add_node("router", router_node)
        
        # Define edges (linear flow with conditional loop)
        workflow.add_edge("planner", "researcher")
        workflow.add_edge("researcher", "writer")
        workflow.add_edge("writer", "reviewer")
        workflow.add_edge("reviewer", "router")
        
        # Conditional routing from router
        workflow.add_conditional_edges(
            "router",
            should_refine,
            {
                "refine": "writer",  # Loop back for refinement
                "end": END,          # Finish workflow
            }
        )
        
        # Set entry point
        workflow.set_entry_point("planner")
        
        span.set_status(Status(StatusCode.OK))
        logger.info("Post generator workflow built successfully")
        
        return workflow


# ============================================================================
# MAIN EXECUTION FUNCTION
# ============================================================================

def run_post_generator(
    user_id: str,
    topic: str,
    platform: str = "linkedin",
    tone: str = None,
    max_refinements: int = None,
) -> Dict[str, Any]:
    """
    Execute the post generator workflow.
    
    Args:
        user_id: User identifier for tracking
        topic: Topic to write about
        platform: Target platform (linkedin, twitter, etc.)
        tone: Writing tone (professional, casual, etc.)
        max_refinements: Maximum refinement iterations
        
    Returns:
        Dict with final_post, scores, trace_id, etc.
    """
    # Generate conversation ID
    conversation_id = f"conv-{user_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    with tracer.start_as_current_span(
        "run_post_generator",
        attributes={
            "user_id": user_id,
            "conversation_id": conversation_id,
            "topic": topic,
            "platform": platform,
        }
    ) as span:
        try:
            logger.info(
                f"[{user_id}] Starting post generation workflow",
                extra={
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "topic": topic,
                    "platform": platform,
                    "tone": tone
                }
            )
            
            # Build and compile workflow
            workflow = build_post_generator_workflow()
            compiled_workflow = workflow.compile()
            
            # Initialize state
            initial_state = PostGeneratorState(
                user_id=user_id,
                topic=topic,
                platform=platform,
                tone=tone,
                max_refinements=max_refinements or int(os.getenv("MAX_REFINEMENT_LOOPS", "2"))
            )
            
            # Execute workflow
            result = compiled_workflow.invoke(initial_state.model_dump())
            
            # Extract final results
            final_post = result.get("final_post", "")
            scores = result.get("scores", {})
            refinement_count = result.get("refinement_count", 0)
            
            # Get trace ID from current span
            trace_id = format(span.get_span_context().trace_id, '032x')
            
            output = {
                "post_markdown": final_post,
                "scores": scores,
                "refinement_count": refinement_count,
                "trace_id": trace_id,
                "conversation_id": conversation_id,
                "platform": platform,
            }
            
            span.set_attribute("success", True)
            span.set_attribute("refinement_count", refinement_count)
            span.set_attribute("post_length", len(final_post))
            span.set_status(Status(StatusCode.OK))
            
            logger.info(
                f"[{user_id}] Post generation completed successfully",
                extra={
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "refinement_count": refinement_count,
                    "post_length": len(final_post),
                    "trace_id": trace_id
                }
            )
            
            return output
            
        except Exception as e:
            logger.error(
                f"[{user_id}] Post generation failed: {e}",
                extra={
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "error": str(e)
                },
                exc_info=True
            )
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "PostGeneratorState",
    "build_post_generator_workflow",
    "run_post_generator",
]
