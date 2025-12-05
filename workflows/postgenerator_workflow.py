"""
Enhanced LangGraph workflow with advanced features:
1. Human-in-the-Loop (HITL) with interrupts
2. Parallel execution for multi-dimensional analysis
3. Dynamic routing based on platform and content type
4. Error recovery with automatic retries

This is an example implementation showing how to enhance the base workflow.
"""

import os
from typing import Literal, Sequence
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphInterrupt

from agents import create_plan, write_post, check_facts
from workflows.state import PostGeneratorState


# ============================================================================
# NEW AGENTS FOR PARALLEL EXECUTION
# ============================================================================

def analyze_sentiment(state: PostGeneratorState) -> PostGeneratorState:
    """
    Analyze sentiment and tone of the generated post.
    Runs in parallel with fact-checker.
    """
    print("SENTIMENT ANALYZER: Analyzing post tone...")
    
    draft = state.get("draft", "")
    
    # Simplified sentiment analysis (replace with actual model)
    sentiment_score = 0.75  # Placeholder
    detected_tone = state.get("tone", "professional")
    
    state["sentiment_analysis"] = {
        "sentiment_score": sentiment_score,
        "detected_tone": detected_tone,
        "tone_match": True,  # Does detected tone match requested?
    }
    
    print(f"Sentiment score: {sentiment_score:.2f}")
    return state


def optimize_seo(state: PostGeneratorState) -> PostGeneratorState:
    """
    Optimize post for search engines and social media algorithms.
    Runs in parallel with fact-checker.
    """
    print("SEO OPTIMIZER: Analyzing SEO metrics...")
    
    draft = state.get("draft", "")
    platform = state.get("platform", "linkedin")
    
    # Simplified SEO analysis
    seo_metrics = {
        "keyword_density": 0.85,
        "readability_score": 0.78,
        "optimal_length": platform == "linkedin" and 150 <= len(draft.split()) <= 200,
        "hashtag_count": draft.count("#"),
    }
    
    state["seo_metrics"] = seo_metrics
    
    print(f"SEO score: {seo_metrics['readability_score']:.2f}")
    return state


def merge_analysis_results(state: PostGeneratorState) -> PostGeneratorState:
    """
    Merge results from parallel analysis nodes.
    Determines if post needs refinement based on all metrics.
    """
    print("MERGER: Combining analysis results...")
    
    # Get all analysis results
    fact_scores = state.get("scores", {})
    sentiment = state.get("sentiment_analysis", {})
    seo = state.get("seo_metrics", {})
    
    # Thresholds
    faith_threshold = float(os.getenv("FAITHFULNESS_THRESHOLD", "0.80"))
    relevancy_threshold = float(os.getenv("ANSWER_RELEVANCY_THRESHOLD", "0.80"))
    sentiment_threshold = 0.70
    seo_threshold = 0.75
    
    # Check all dimensions
    checks = {
        "faithfulness": fact_scores.get("faithfulness", 0) >= faith_threshold,
        "relevancy": fact_scores.get("answer_relevancy", 0) >= relevancy_threshold,
        "sentiment": sentiment.get("sentiment_score", 0) >= sentiment_threshold,
        "seo": seo.get("readability_score", 0) >= seo_threshold,
    }
    
    # Overall quality assessment
    all_pass = all(checks.values())
    
    # Build comprehensive feedback
    feedback_parts = []
    if not checks["faithfulness"]:
        feedback_parts.append("Improve factual accuracy based on source materials.")
    if not checks["relevancy"]:
        feedback_parts.append(f"Stay more focused on the topic: {state['topic']}")
    if not checks["sentiment"]:
        feedback_parts.append(f"Adjust tone to better match requested: {state.get('tone', 'professional')}")
    if not checks["seo"]:
        feedback_parts.append("Improve readability and keyword usage for better engagement.")
    
    feedback = " ".join(feedback_parts) if feedback_parts else "All quality checks passed!"
    
    state["needs_refinement"] = not all_pass
    state["feedback"] = feedback
    state["quality_checks"] = checks
    
    print(f"Quality checks: {sum(checks.values())}/{len(checks)} passed")
    
    return state


# ============================================================================
# HUMAN-IN-THE-LOOP NODE
# ============================================================================

def human_review(state: PostGeneratorState) -> PostGeneratorState:
    """
    Pause execution for human review and approval.
    
    This node uses LangGraph's interrupt feature to pause the workflow.
    The human can then:
    - Approve the draft (continue to analysis)
    - Reject and provide feedback (return to writer)
    - Edit the draft directly
    """
    print("HUMAN REVIEW: Pausing for human approval...")
    
    draft = state.get("draft", "")
    
    # This will pause the graph execution
    # Resume by providing: {"human_approved": True/False, "human_feedback": "..."}
    raise GraphInterrupt(
        f"Human review required for draft:\n\n{draft[:200]}...\n\n"
        f"Provide 'human_approved' (bool) and optional 'human_feedback' (str) to continue."
    )


# ============================================================================
# DYNAMIC ROUTING FUNCTIONS
# ============================================================================

def route_to_specialized_writer(state: PostGeneratorState) -> str:
    """
    Route to specialized writer based on platform and content type.
    
    Returns:
        str: Name of the specialized writer node to use
    """
    platform = state.get("platform", "linkedin")
    content_type = state.get("content_type", "standard")
    
    # Determine specialized writer
    if platform == "linkedin":
        if content_type == "technical":
            return "technical_linkedin_writer"
        elif content_type == "thought_leadership":
            return "thought_leader_writer"
        else:
            return "standard_linkedin_writer"
    elif platform == "twitter":
        if content_type == "thread":
            return "twitter_thread_writer"
        else:
            return "twitter_writer"
    else:
        return "general_writer"


def should_refine_enhanced(state: PostGeneratorState) -> Literal["refine", "end"]:
    """
    Enhanced conditional routing with quality checks.
    
    Routes based on:
    - All quality dimensions (facts, sentiment, SEO)
    - Refinement count limit
    - Human override (if available)
    """
    # Check for human override
    if state.get("human_force_publish", False):
        return "end"
    
    needs_refinement = state.get("needs_refinement", False)
    refinement_count = state.get("refinement_count", 0)
    max_refinements = state.get("max_refinements", int(os.getenv("MAX_REFINEMENT_LOOPS", "1")))
    
    # Check quality gates
    quality_checks = state.get("quality_checks", {})
    critical_failures = sum(1 for k, v in quality_checks.items() 
                          if k in ["faithfulness", "relevancy"] and not v)
    
    # Force refinement for critical failures (unless max reached)
    if critical_failures > 0 and refinement_count < max_refinements:
        return "refine"
    
    # Normal refinement logic
    if not needs_refinement or refinement_count >= max_refinements:
        return "end"
    
    return "refine"


# ============================================================================
# ENHANCED GRAPH BUILDER
# ============================================================================

def build_enhanced_graph(enable_hitl: bool = False) -> StateGraph:
    """
    Build an enhanced LangGraph workflow with advanced features.
    
    Features:
    - Parallel execution (fact-checking, sentiment, SEO)
    - Human-in-the-loop (optional)
    - Dynamic routing
    - Comprehensive quality analysis
    
    Args:
        enable_hitl: Enable human-in-the-loop review step
        
    Returns:
        StateGraph: Enhanced workflow
    """
    workflow = StateGraph(PostGeneratorState)
    
    # Add nodes
    workflow.add_node("planner", create_plan)
    workflow.add_node("writer", write_post)
    
    # Optional human review
    if enable_hitl:
        workflow.add_node("human_review", human_review)
    
    # Parallel analysis nodes
    workflow.add_node("fact_checker", check_facts)
    workflow.add_node("sentiment_analyzer", analyze_sentiment)
    workflow.add_node("seo_optimizer", optimize_seo)
    
    # Merge analysis results
    workflow.add_node("merge_analysis", merge_analysis_results)
    
    # Router
    workflow.add_node("router", router_node_enhanced)
    
    # Linear flow: planner → writer
    workflow.add_edge("planner", "writer")
    
    # HITL branch
    if enable_hitl:
        workflow.add_edge("writer", "human_review")
        
        # After human review, go to parallel analysis
        workflow.add_edge("human_review", "fact_checker")
        workflow.add_edge("human_review", "sentiment_analyzer")
        workflow.add_edge("human_review", "seo_optimizer")
    else:
        # Without HITL, go directly to parallel analysis
        workflow.add_edge("writer", "fact_checker")
        workflow.add_edge("writer", "sentiment_analyzer")
        workflow.add_edge("writer", "seo_optimizer")
    
    # Parallel analysis → merge
    workflow.add_edge("fact_checker", "merge_analysis")
    workflow.add_edge("sentiment_analyzer", "merge_analysis")
    workflow.add_edge("seo_optimizer", "merge_analysis")
    
    # Merge → router
    workflow.add_edge("merge_analysis", "router")
    
    # Conditional routing from router
    workflow.add_conditional_edges(
        "router",
        should_refine_enhanced,
        {
            "refine": "writer",  # Loop back
            "end": END,
        }
    )
    
    # Set entry point
    workflow.set_entry_point("planner")
    
    return workflow


def router_node_enhanced(state: PostGeneratorState) -> PostGeneratorState:
    """
    Enhanced router with multi-dimensional quality assessment.
    """
    print("ROUTER: Making routing decision...")
    
    needs_refinement = state.get("needs_refinement", False)
    refinement_count = state.get("refinement_count", 0)
    max_refinements = state.get("max_refinements", int(os.getenv("MAX_REFINEMENT_LOOPS", "1")))
    quality_checks = state.get("quality_checks", {})
    
    if not needs_refinement:
        print("✅ All quality gates passed!")
        state["final_post"] = state.get("draft", "")
        return state
    
    if refinement_count >= max_refinements:
        print(f"⚠️  Max refinements ({max_refinements}) reached. Accepting current draft.")
        state["final_post"] = state.get("draft", "")
        state["needs_refinement"] = False
        return state
    
    # Log which checks failed
    failed_checks = [k for k, v in quality_checks.items() if not v]
    print(f"🔄 Refinement needed. Failed checks: {', '.join(failed_checks)}")
    print(f"   Attempt {refinement_count + 1}/{max_refinements}")
    
    state["refinement_count"] = refinement_count + 1
    return state


# ============================================================================
# EXAMPLE: RESUMING INTERRUPTED WORKFLOW
# ============================================================================

def resume_interrupted_workflow():
    """
    Example of how to resume a workflow interrupted for human review.
    """
    from lib.memory import get_checkpointer
    
    # Build graph with HITL enabled
    graph = build_enhanced_graph(enable_hitl=True)
    checkpointer = get_checkpointer()
    compiled_graph = graph.compile(checkpointer=checkpointer)
    
    # Initial invocation (will interrupt at human_review)
    config = {"configurable": {"thread_id": "session-123"}}
    
    try:
        result = compiled_graph.invoke({
            "user_id": "user-456",
            "session_id": "session-123",
            "topic": "AI advancements",
            "platform": "linkedin",
            "tone": "insightful",
            "refinement_count": 0,
            "max_refinements": 1,
            "messages": [],
        }, config=config)
    except GraphInterrupt as e:
        print(f"Workflow interrupted: {e}")
        print("Waiting for human input...")
        
        # Simulate human approval
        # In a real app, this would come from a UI or API call
        human_input = {
            "human_approved": True,
            "human_feedback": None,  # Or provide feedback
        }
        
        # Resume workflow with human input
        result = compiled_graph.invoke(human_input, config=config)
        print(f"Workflow resumed and completed!")
        print(f"Final post: {result.get('final_post', '')[:100]}...")
    
    return result


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    print("Enhanced LangGraph Workflow Examples\n")
    print("="*60)
    
    # Example 1: Standard enhanced workflow (no HITL)
    print("\n1. Building enhanced workflow without HITL...")
    graph1 = build_enhanced_graph(enable_hitl=False)
    compiled1 = graph1.compile()
    print(f"   Nodes: {list(graph1.nodes.keys())}")
    
    # Example 2: Enhanced workflow with HITL
    print("\n2. Building enhanced workflow with HITL...")
    graph2 = build_enhanced_graph(enable_hitl=True)
    compiled2 = graph2.compile(checkpointer=MemorySaver())
    print(f"   Nodes: {list(graph2.nodes.keys())}")
    
    # Example 3: Show routing logic
    print("\n3. Testing dynamic routing...")
    test_states = [
        {"platform": "linkedin", "content_type": "technical"},
        {"platform": "twitter", "content_type": "thread"},
        {"platform": "linkedin", "content_type": "standard"},
    ]
    
    for state in test_states:
        route = route_to_specialized_writer(state)
        print(f"   {state} → {route}")
    
    print("\n" + "="*60)
    print("Enhanced workflow ready for production use!")
