"""
Task-oriented LangGraph workflow for social media post generation.

Implements the Planner → Researcher → Writer → Reviewer pattern with:
- OpenTelemetry (OTEL) tracing for observability
- User ID and conversation ID tracking
- Proper error handling and logging
- LangGraph state management using Pydantic models
"""

import os
import json
import asyncio
from typing import Literal, Dict, Any
from datetime import datetime

from langgraph.graph import StateGraph, END
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from .postgenerator_workflow_state import PostGeneratorState
from .agent_orchestrator import AgentOrchestrator
from .reasoning_router import ReasoningRouter, RouterDecision
from core.logging_config import get_logger
from core.cosmos_checkpointer import CosmosDBCheckpointer
import uuid


# Global notification callback for streaming thinking updates
_notification_callback = None

def set_notification_callback(callback):
    """Set the notification callback for streaming router thinking updates."""
    global _notification_callback
    _notification_callback = callback

def get_notification_callback():
    """Get the current notification callback."""
    return _notification_callback


# Initialize logger and tracer
logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)


# ============================================================================
# PLANNER NODE - Creates structured outline and strategy
# ============================================================================
async def planner_node(state: PostGeneratorState) -> Dict[str, Any]:
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
    thread_id = state.thread_id
    
    with tracer.start_as_current_span(
        "planner.create_outline",
        attributes={
            "agent.name": "planner",
            "agent.user_id": user_id,
            "agent.thread_id": thread_id,
            "workflow.step": "plan",
            "topic": topic,
            "platform": platform,
        }
    ) as span:
        span.add_event("gen_ai.planner.started", {"topic": topic})
        
        logger.info(
            f"[{user_id}][{thread_id}] PLANNER: Creating outline for topic '{topic}' on {platform}",
            extra={
                "user_id": user_id,
                "thread_id": thread_id,
                "topic": topic,
                "platform": platform,
                "input_state": state.model_dump()
            }
        )
        
        # Get orchestrator instance and call planner via A2A
        orchestrator = AgentOrchestrator()
        try:
            updates = await orchestrator.call_planner(state.model_dump())
        finally:
            await orchestrator.close()
        
        span.set_attribute("plan_length", len(updates["plan"]))
        span.set_attribute("message_count", len(updates["messages"]))
        span.add_event("gen_ai.planner.completed", {
            "plan_length": len(updates["plan"]),
            "gen_ai.event.content": json.dumps({"plan": updates["plan"]})
        })
        span.set_status(Status(StatusCode.OK))
        
        logger.info(
            f"[{user_id}][{thread_id}] PLANNER: Created plan with {len(updates['plan'])} characters",
            extra={
                "user_id": user_id,
                "plan_length": len(updates["plan"]),
                "output_updates": updates
            }
        )
        
        return updates
    
   
# ============================================================================
# RESEARCHER NODE - Retrieves relevant context
# ============================================================================
async def researcher_node(state: PostGeneratorState) -> Dict[str, Any]:
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
    thread_id = state.thread_id
    
    with tracer.start_as_current_span(
        "researcher.retrieve_context",
        attributes={
            "agent.name": "researcher",
            "agent.user_id": user_id,
            "agent.thread_id": thread_id,
            "workflow.step": "research",
            "topic": topic,
            "has_plan": bool(plan),
        }
    ) as span:
        span.add_event("gen_ai.researcher.started", {"topic": topic})
        
        logger.info(
            f"[{user_id}][{thread_id}] RESEARCHER: Retrieving context for topic '{topic}'",
            extra={"user_id": user_id, "thread_id": thread_id, "topic": topic}
        )
        
        # Get orchestrator instance and call researcher via A2A
        orchestrator = AgentOrchestrator()
        try:
            updates = await orchestrator.call_researcher(state.model_dump())
            retrieved_docs = updates.get("retrieved_docs", [])
            context = updates.get("context", "")
        finally:
            await orchestrator.close()
        
        span.set_attribute("docs_retrieved", len(retrieved_docs))
        span.set_attribute("context_length", len(context))
        span.add_event("research_completed", {
            "docs_count": len(retrieved_docs),
            "context_length": len(context)
        })
        span.set_status(Status(StatusCode.OK))
        
        logger.info(
            f"[{user_id}][{thread_id}] RESEARCHER: Retrieved {len(retrieved_docs)} documents, {len(context)} chars of context",
            extra={
                "user_id": user_id,
                "thread_id": thread_id,
                "docs_count": len(retrieved_docs),
                "context_length": len(context)
            }
        )
        
        return updates


# ============================================================================
# WRITER NODE - Generates post content
# ============================================================================

async def writer_node(state: PostGeneratorState) -> Dict[str, Any]:
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
    thread_id = state.thread_id
    is_refinement = refinement_count > 0
    
    with tracer.start_as_current_span(
        f"writer.{'refine_post' if is_refinement else 'generate_post'}",
        attributes={
            "agent.name": "writer",
            "agent.user_id": user_id,
            "agent.thread_id": thread_id,
            "workflow.step": "write",
            "topic": topic,
            "platform": platform,
            "refinement_count": refinement_count,
            "is_refinement": is_refinement,
        }
    ) as span:
        action = "Refining" if is_refinement else "Writing"
        span.add_event(f"gen_ai.writer.{'refining' if is_refinement else 'writing'}", {"attempt": refinement_count + 1})
        
        logger.info(
            f"[{user_id}][{thread_id}] WRITER: {action} post for topic '{topic}' on {platform} (attempt {refinement_count + 1})",
            extra={
                "user_id": user_id,
                "thread_id": thread_id,
                "topic": topic,
                "platform": platform,
                "refinement_count": refinement_count,
                "is_refinement": is_refinement
            }
        )
        
        # Get orchestrator instance and call writer via A2A
        orchestrator = AgentOrchestrator()
        try:
            updates = await orchestrator.call_writer(state.model_dump())
            draft = updates.get("draft", "")
        finally:
            await orchestrator.close()
        
        span.set_attribute("draft_length", len(draft))
        span.add_event("gen_ai.writer.completed", {
            "draft_length": len(draft),
            "refinement_count": refinement_count,
            "gen_ai.event.content": json.dumps({"draft": draft})
        })
        span.set_status(Status(StatusCode.OK))
        
        logger.info(
            f"[{user_id}][{thread_id}] WRITER: Generated draft with {len(draft)} characters",
            extra={
                "user_id": user_id,
                "thread_id": thread_id,
                "draft_length": len(draft),
                "refinement_count": refinement_count
            }
        )
        
        return updates


# ============================================================================
# REVIEWER NODE - Evaluates quality and provides feedback
# ============================================================================

async def reviewer_node(state: PostGeneratorState) -> Dict[str, Any]:
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
    thread_id = state.thread_id
    
    with tracer.start_as_current_span(
        "reviewer.evaluate_quality",
        attributes={
            "agent.name": "reviewer",
            "agent.user_id": user_id,
            "agent.thread_id": thread_id,
            "workflow.step": "review",
            "topic": topic,
            "draft_length": len(draft),
        }
    ) as span:
        span.add_event("gen_ai.reviewer.started", {"draft_length": len(draft)})
        
        logger.info(
            f"[{user_id}][{thread_id}] REVIEWER: Evaluating post quality for topic '{topic}'",
            extra={"user_id": user_id, "thread_id": thread_id, "topic": topic, "draft_length": len(draft)}
        )
        
        # Get orchestrator instance and call reviewer via A2A
        orchestrator = AgentOrchestrator()
        try:
            # Call reviewer to get evaluation results
            reviewer_result = await orchestrator.call_reviewer(state.model_dump())
            
            # Extract actual scores and feedback from reviewer
            scores = reviewer_result.get("scores", {"answer_relevancy": 0.5, "faithfulness": 0.5})
            feedback = reviewer_result.get("feedback", "Evaluation completed")
            needs_refinement = reviewer_result.get("needs_refinement", False)
            final_post = reviewer_result.get("final_post", state.draft)
            
            # Update state with actual evaluation results
            updates = {
                "scores": scores,
                "feedback": feedback,
                "needs_refinement": needs_refinement,
                "final_post": final_post if not needs_refinement else "",  # Only set final_post if approved
                "messages": state.messages + [{
                    "role": "reviewer",
                    "content": feedback,
                    "scores": scores,
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }
        finally:
            await orchestrator.close()
        
        # Add evaluation scores as span attributes
        for metric, value in scores.items():
            span.set_attribute(f"score_{metric}", value)
        span.set_attribute("needs_refinement", needs_refinement)
        
        # Log evaluation events with gen_ai.evaluation pattern
        # Get response_id from span context
        current_span = trace.get_current_span()
        response_id = str(current_span.get_span_context().span_id) if current_span else ""
        
        span.set_attribute("gen_ai.response.id", response_id)
        
        # Log individual metric evaluations
        for metric, score in scores.items():
            span.add_event(f"gen_ai.evaluation.{metric}", {
                "gen_ai.evaluator.name": metric,
                "gen_ai.evaluation.score": float(score),
                "gen_ai.response.id": response_id,
                "gen_ai.event.content": json.dumps({"comments": f"{metric} evaluation", "passed": score >= 7})
            })
        
        # Log overall evaluation result
        avg_score = sum(scores.values()) / len(scores) if scores else 0
        span.add_event("gen_ai.reviewer.completed", {
            "needs_refinement": needs_refinement,
            "avg_score": avg_score,
            "gen_ai.event.content": json.dumps({"feedback": feedback, "scores": scores})
        })
        span.set_status(Status(StatusCode.OK))
        
        logger.info(
            f"[{user_id}][{thread_id}] REVIEWER: Scores - {scores}, Needs refinement: {needs_refinement}",
            extra={
                "user_id": user_id,
                "thread_id": thread_id,
                "scores": scores,
                "needs_refinement": needs_refinement
            }
        )
        
        return updates


# ============================================================================
# ROUTER NODE - Decides next action
# ============================================================================

async def router_node(state: PostGeneratorState) -> Dict[str, Any]:
    """
    Intelligent Router: Uses reasoning model to decide next workflow step.
    
    The router:
    1. Analyzes the current workflow state
    2. Uses a reasoning model to think through the decision
    3. Extracts and streams the thinking process to clients
    4. Returns the decision with thinking metadata
    
    Decision logic is determined by the reasoning model based on:
    - Current state completeness (plan, context, draft, scores)
    - Quality thresholds and refinement limits
    - Workflow progression requirements
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with routing decision and thinking process
    """
    user_id = state.user_id
    needs_refinement = state.needs_refinement
    refinement_count = state.refinement_count
    max_refinements = state.max_refinements
    topic = state.topic
    thread_id = state.thread_id
    
    with tracer.start_as_current_span(
        "router.intelligent_decision",
        attributes={
            "agent.name": "intelligent_router",
            "agent.user_id": user_id,
            "agent.thread_id": thread_id,
            "workflow.step": "route",
            "needs_refinement": needs_refinement,
            "refinement_count": refinement_count,
            "max_refinements": max_refinements,
        }
    ) as span:
        logger.info(
            f"[{user_id}][{thread_id}] INTELLIGENT ROUTER: Analyzing state for topic '{topic}'",
            extra={
                "user_id": user_id,
                "thread_id": thread_id,
                "topic": topic,
                "needs_refinement": needs_refinement,
                "refinement_count": refinement_count,
                "max_refinements": max_refinements
            }
        )
        
        # Create reasoning router with notification callback
        notification_callback = get_notification_callback()
        router = ReasoningRouter(notification_callback=notification_callback)
        
        # Get intelligent decision from reasoning model
        router_decision: RouterDecision = await router.decide_next_node(state.model_dump())
        
        # Build updates with thinking process
        updates = {
            "router_thinking": router_decision.thinking,
            "router_decision": router_decision.decision,
            "next_node": router_decision.decision,
            "current_node": "router",
        }
        
        # Handle special cases based on decision
        if router_decision.decision == "end":
            # Finalize the post
            updates["final_post"] = state.final_post if state.final_post else state.draft
            updates["workflow_status"] = "completed"
            updates["needs_refinement"] = False
            logger.info(
                f"[{user_id}][{thread_id}] ROUTER: Finalizing post",
                extra={"user_id": user_id, "thread_id": thread_id, "decision": "end"}
            )
        elif router_decision.decision == "writer" and refinement_count > 0:
            # This is a refinement loop
            updates["refinement_count"] = refinement_count + 1
            updates["workflow_status"] = f"refining (attempt {refinement_count + 1})"
            logger.info(
                f"[{user_id}][{thread_id}] ROUTER: Refinement cycle {refinement_count + 1}",
                extra={"user_id": user_id, "thread_id": thread_id, "decision": "writer"}
            )
        else:
            updates["workflow_status"] = f"proceeding to {router_decision.decision}"
        
        # Log detailed decision info
        span.set_attribute("router.decision", router_decision.decision)
        span.set_attribute("router.confidence", router_decision.confidence)
        span.set_attribute("router.thinking_length", len(router_decision.thinking))
        span.add_event("gen_ai.router.intelligent_decision", {
            "decision": router_decision.decision,
            "confidence": router_decision.confidence,
            "summary": router_decision.summary,
            "thinking_preview": router_decision.thinking[:500] if router_decision.thinking else "",
            "gen_ai.event.content": json.dumps({
                "thinking": router_decision.thinking,
                "decision": router_decision.decision,
                "summary": router_decision.summary
            })
        })
        span.set_status(Status(StatusCode.OK))
        
        logger.info(
            f"[{user_id}][{thread_id}] ROUTER: Decision='{router_decision.decision}' "
            f"(confidence={router_decision.confidence:.2f}): {router_decision.summary}",
            extra={
                "user_id": user_id,
                "thread_id": thread_id,
                "decision": router_decision.decision,
                "confidence": router_decision.confidence,
                "thinking_length": len(router_decision.thinking)
            }
        )
        
        return updates


# ============================================================================
# CONDITIONAL ROUTING FUNCTION
# ============================================================================

def get_next_node(state: PostGeneratorState) -> Literal["planner", "researcher", "writer", "reviewer", "end"]:
    """
    Intelligent conditional edge function for routing decision.
    
    Uses the router's LLM-based decision stored in state.next_node.
    Falls back to rule-based logic if next_node is not set.
    
    Args:
        state: Current workflow state
        
    Returns:
        Next node name based on intelligent router decision
    """
    # Use the intelligent router's decision
    next_node = state.next_node
    
    if next_node in ["planner", "researcher", "writer", "reviewer", "end"]:
        logger.debug(f"Routing to '{next_node}' based on intelligent router decision")
        return next_node
    
    # Fallback to rule-based logic if next_node not set
    logger.warning(f"next_node='{next_node}' is invalid, using fallback logic")
    
    if not state.plan:
        return "planner"
    elif not state.context:
        return "researcher"
    elif not state.draft:
        return "writer"
    elif not state.scores:
        return "reviewer"
    elif state.needs_refinement and state.refinement_count < state.max_refinements:
        return "writer"
    else:
        return "end"


def should_refine(state: PostGeneratorState) -> Literal["refine", "end"]:
    """
    Legacy conditional edge function for routing decision.
    Kept for backwards compatibility.
    
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
    Build the post generator LangGraph workflow with intelligent routing.
    
    Workflow structure with LLM-driven router:
    1. Router → Analyzes state, thinks through decision, routes to next node
    2. Planner → Creates outline (if plan needed)
    3. Researcher → Retrieves context (if research needed)
    4. Writer → Generates post (if draft needed)
    5. Reviewer → Evaluates quality (if review needed)
    6. Router → Re-analyzes and decides next step or end
    
    The router uses a reasoning model to:
    - Analyze current workflow state
    - Think through the decision (visible to user)
    - Route to appropriate next node
    
    Returns:
        Compiled StateGraph ready for execution
    """
    # Create workflow
    workflow = StateGraph(PostGeneratorState)
    
    # Add nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("router", router_node)
    
    # Each agent node routes back to the router for intelligent decision
    workflow.add_edge("planner", "router")
    workflow.add_edge("researcher", "router")
    workflow.add_edge("writer", "router")
    workflow.add_edge("reviewer", "router")
    
    # Intelligent routing from router based on LLM decision
    workflow.add_conditional_edges(
        "router",
        get_next_node,
        {
            "planner": "planner",
            "researcher": "researcher",
            "writer": "writer",
            "reviewer": "reviewer",
            "end": END,
        }
    )
    
    # Set entry point to router (it will analyze state and route to first needed node)
    workflow.set_entry_point("router")
    return workflow


# ============================================================================
# MAIN EXECUTION FUNCTION
# ============================================================================

def configure_post_generator(
    user_id: str,
    topic: str,
    platform: str = "linkedin",
    tone: str = None,
    max_refinements: int = None,
    thread_id: str = None
):
    """
    Build and compile the post generator workflow.
    
    Args:
        user_id: User identifier for tracking
        topic: Topic to write about
        platform: Target platform (linkedin, twitter, etc.)
        tone: Writing tone (professional, casual, etc.)
        max_refinements: Maximum refinement iterations
        thread_id: Thread identifier for checkpointing
        
    Returns:
        Tuple of (compiled_workflow, initial_state, config)
    """
    thread_id = thread_id or str(uuid.uuid4())

    # Build workflow
    workflow = build_post_generator_workflow()
    
    # Initialize Cosmos DB checkpointer
    logger.info(f"[{user_id}][{thread_id}] Initializing Cosmos DB checkpointer")
    checkpointer = CosmosDBCheckpointer()
    
    # Compile workflow with or without checkpointer
    if checkpointer.container:
        logger.info(f"[{user_id}][{thread_id}] Cosmos DB checkpointer ready")
        compiled_workflow = workflow.compile(checkpointer=checkpointer)
        logger.info(f"[{user_id}][{thread_id}] Graph compiled with checkpointer")
    else:
        logger.warning(f"[{user_id}][{thread_id}] Cosmos DB not available, compiling without checkpointer")
        compiled_workflow = workflow.compile()
    
    # Configure checkpointing
    config = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": "",
        }
    }
    
    # Initialize state
    initial_state = PostGeneratorState(
        user_id=user_id,
        topic=topic,
        platform=platform,
        thread_id=thread_id,
        tone=tone,
        max_refinements=max_refinements or int(os.getenv("MAX_REFINEMENT_LOOPS", "2"))
    )
    
    logger.info(f"[{user_id}][{thread_id}] Workflow compiled and ready")
    
    return compiled_workflow, initial_state, config


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "PostGeneratorState",
    "build_post_generator_workflow",
    "configure_post_generator",
]
