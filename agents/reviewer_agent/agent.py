"""
Reviewer agent for evaluating social media post quality.

This agent:
1. Evaluates post quality using DeepEval metrics
2. Provides structured feedback
3. Determines if refinement is needed based on metric thresholds
4. Logs all evaluations with thread_id and user_id for tracing
"""

import os
from typing import Dict, Any, Optional
from pathlib import Path

from langchain_core.runnables import RunnableConfig
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from core.logging_config import get_logger

# Import deepeval
from deepeval import evaluate
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase
from deepeval.models import AzureOpenAIModel

tracer = trace.get_tracer(__name__)
logger = get_logger(__name__)


class ReviewerAgent:
    """
    Reviewer agent that evaluates social media post quality using DeepEval.
    """
    
    def __init__(self):
        """Initialize the reviewer agent."""
        
        # State variables
        self.topic = ""
        self.platform = "linkedin"
        self.tone = "professional"
        self.user_id = ""
        self.plan = ""
        self.context = ""
        self.draft = ""
        self.thread_id = ""
        
        # DeepEval thresholds
        self.relevancy_threshold = 0.5
        self.faithfulness_threshold = 0.5
    
    @tracer.start_as_current_span("ReviewerAgent.evaluate_with_deepeval")
    def evaluate_with_deepeval(
        self, 
        thread_id: Optional[str] = None
    ) -> tuple[Dict[str, float], str]:
        """
        Evaluate post using deepeval metrics.
        
        Args:
            thread_id: Thread ID for logging
            
        Returns:
            Tuple of (scores dict, feedback string)
        """
        try:
            logger.debug(f"   🔍 Running deepeval metrics...")
            
            # Configure deepeval with Azure OpenAI
            os.environ["OPENAI_API_TYPE"] = "azure"
            os.environ["OPENAI_API_VERSION"] = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
            deepeval_model_name = os.getenv("DEEPEVAL_MODEL", "o4-mini")
            deepeval_model = AzureOpenAIModel(
                        deployment_name=deepeval_model_name,
                        temperature=1
            )
            
            scores: Dict[str, float] = {
                "answer_relevancy": 0.5,
                "faithfulness": 0.5
            }
            
            feedback: str = ""
            
            # Create test case
            test_case = LLMTestCase(
                input=self.topic,
                actual_output=self.draft,
                expected_output=self.plan,
                context=[self.context] if self.context else None,
                retrieval_context=[self.context] if self.context else None
            )
            
            # Initialize metrics
            answer_relevancy = AnswerRelevancyMetric(
                threshold=self.relevancy_threshold,
                model=deepeval_model,
                include_reason=True
            )
            
            faithfulness = FaithfulnessMetric(
                threshold=self.faithfulness_threshold,
                model=deepeval_model,
                include_reason=True
            )
            
            # Measure metrics
            answer_relevancy.measure(test_case)
            faithfulness.measure(test_case)
            
            # Extract scores as Dict[str, float]
            scores: Dict[str, float] = {
                "answer_relevancy": float(answer_relevancy.score),
                "faithfulness": float(faithfulness.score)
            }
            
            # Build feedback from reasons
            feedback_parts = []
            if answer_relevancy.reason:
                feedback_parts.append(f"Answer Relevancy ({answer_relevancy.score:.2f}): {answer_relevancy.reason}")
            if faithfulness.reason:
                feedback_parts.append(f"Faithfulness ({faithfulness.score:.2f}): {faithfulness.reason}")
            
            feedback = "\n\n".join(feedback_parts) if feedback_parts else "Evaluation completed."
            
            logger.info(f"   ✅ Deepeval scores - Relevancy: {answer_relevancy.score:.2f}, Faithfulness: {faithfulness.score:.2f}")
            
            # Log deepeval results with thread_id
            logger.info(
                f"[{self.user_id}][{thread_id}] REVIEWER DEEPEVAL - "
                f"relevancy: {answer_relevancy.score:.2f}, faithfulness: {faithfulness.score:.2f}",
                extra={
                    "user_id": self.user_id,
                    "thread_id": thread_id,
                    "evaluation_type": "deepeval",
                    "answer_relevancy": answer_relevancy.score,
                    "faithfulness": faithfulness.score,
                    "answer_relevancy_reason": answer_relevancy.reason[:200] if answer_relevancy.reason else "",
                    "faithfulness_reason": faithfulness.reason[:200] if faithfulness.reason else "",
                    "agent": "reviewer"
                }
            )
            
            # Add to OTEL span
            current_span = trace.get_current_span()
            current_span.set_attribute("reviewer.deepeval.answer_relevancy", answer_relevancy.score)
            current_span.set_attribute("reviewer.deepeval.faithfulness", faithfulness.score)
            
            return scores, feedback
            
        except Exception as e:
            logger.error(
                f"[{self.user_id}][{thread_id}] REVIEWER DEEPEVAL FAILED - {str(e)}",
                extra={
                    "user_id": self.user_id,
                    "thread_id": thread_id,
                    "error": str(e),
                    "agent": "reviewer"
                },
                exc_info=True
            )
            
            # Return default scores on error
            default_scores: Dict[str, float] = {
                "answer_relevancy": 0.5,
                "faithfulness": 0.5
            }
            error_feedback = f"DeepEval evaluation failed: {str(e)}"
            return default_scores, error_feedback
    
    @tracer.start_as_current_span("ReviewerAgent.review_post")
    def review_post(
        self, 
        state: Dict[str, Any], 
        config: Optional[RunnableConfig] = None
    ) -> Dict[str, Any]:
        """
        Review the social media post using DeepEval metrics.
        
        Args:
            state: Current graph state with draft, plan, context, etc.
            config: Optional runnable config for tracing
            
        Returns:
            Updated state with scores, feedback, and needs_refinement flag
        """
        # Extract state variables
        self.thread_id = state.get("thread_id")
        self.topic = state.get("topic", "")
        self.platform = state.get("platform", "linkedin")
        self.tone = state.get("tone", "professional")
        self.user_id = state.get("user_id", "")
        self.plan = state.get("plan", "")
        self.context = state.get("context", "")
        self.draft = state.get("draft", "")
        current_span = trace.get_current_span()
        
        print(f"🔍 REVIEWER: Evaluating post quality with DeepEval...")
        
        with current_span:
            
            # Log input
            logger.info(
                f"[{self.user_id}][{self.thread_id}] REVIEWER INPUT - draft_length: {len(self.draft)} chars",
                extra={
                    "user_id": self.user_id,
                    "thread_id": self.thread_id,
                    "draft_length": len(self.draft),
                    "agent": "reviewer"
                }
            )
            
            # Get DeepEval metrics
            scores, feedback = self.evaluate_with_deepeval(thread_id=self.thread_id)
            
            # Determine if refinement is needed based on thresholds
            # Both metrics should pass their thresholds
            needs_refinement = (
                scores.get("answer_relevancy", 0.0) < self.relevancy_threshold or
                scores.get("faithfulness", 0.0) < self.faithfulness_threshold
            )
            
            print(f"   {'❌ Needs refinement' if needs_refinement else '✅ Quality acceptable'}")
            
            # Log output
            logger.info(
                f"[{self.user_id}][{self.thread_id}] REVIEWER OUTPUT - "
                f"needs_refinement: {needs_refinement}, scores: {scores}",
                extra={
                    "user_id": self.user_id,
                    "thread_id": self.thread_id,
                    "needs_refinement": needs_refinement,
                    "feedback_length": len(feedback),
                    "scores": scores,
                    "agent": "reviewer"
                }
            )
            
            # Add scores to OTEL span
            for metric, value in scores.items():
                current_span.set_attribute(f"reviewer.{metric}", value)
            current_span.set_attribute("reviewer.needs_refinement", needs_refinement)
            
            # Update state
            state["scores"] = scores
            state["feedback"] = feedback
            state["needs_refinement"] = needs_refinement
            
            return state


# Singleton instance
_reviewer_agent = None

def get_reviewer_agent() -> ReviewerAgent:
    """Get or create the singleton reviewer agent instance."""
    global _reviewer_agent
    if _reviewer_agent is None:
        _reviewer_agent = ReviewerAgent()
    return _reviewer_agent

def check_facts(state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """
    Node function for LangGraph integration.
    
    Args:
        state: Current graph state
        config: Optional runnable config
        
    Returns:
        Updated state with evaluation results
    """
    agent = get_reviewer_agent()
    return agent.review_post(state, config)


if __name__ == "__main__":
    """
    Main method to validate the reviewer agent independently.
    
    Usage:
        python -m agents.reviewer_agent.agent
    """
    import sys
    
    print("=" * 80)
    print("🧪 REVIEWER AGENT - STANDALONE VALIDATION")
    print("=" * 80)
    
    # Sample test state
    test_state = {
        "thread_id": "test-thread-123",
        "user_id": "test-user",
        "topic": "The future of artificial intelligence in healthcare",
        "platform": "linkedin",
        "tone": "professional",
        "plan": "Create a professional LinkedIn post about AI in healthcare, highlighting 3 key benefits: diagnosis accuracy, personalized treatment, and operational efficiency.",
        "context": "Recent studies show AI can improve diagnostic accuracy by 20%, reduce treatment planning time by 40%, and optimize hospital operations by 30%.",
        "draft": """🏥 The Future of AI in Healthcare

Artificial Intelligence is transforming healthcare in unprecedented ways. Here are three game-changing benefits:

1. Enhanced Diagnosis Accuracy - AI-powered diagnostic tools are improving accuracy by 20%, helping doctors catch diseases earlier.

2. Personalized Treatment Plans - Machine learning algorithms analyze patient data to create customized treatment plans, reducing planning time by 40%.

3. Operational Efficiency - AI optimizes hospital workflows and resource allocation, improving operations by 30%.

The healthcare industry is at an inflection point. Those who embrace AI will lead the transformation.

#AI #Healthcare #Innovation #Technology"""
    }
    
    try:
        # Create reviewer agent
        print("\n✅ Creating reviewer agent instance...")
        agent = get_reviewer_agent()
        
        # Test the review process
        print("\n📋 Test State:")
        print(f"   Topic: {test_state['topic']}")
        print(f"   Platform: {test_state['platform']}")
        print(f"   Draft length: {len(test_state['draft'])} characters")
        
        # Run the reviewer
        print("\n🚀 Running review process...\n")
        result = agent.review_post(test_state)
        
        # Display results
        print("\n" + "=" * 80)
        print("📊 REVIEW RESULTS")
        print("=" * 80)
        
        print(f"\n✅ Needs Refinement: {result.get('needs_refinement', 'N/A')}")
        
        print("\n📈 Scores:")
        scores = result.get('scores', {})
        for metric, value in scores.items():
            status = "✅" if value >= 0.5 else "❌"
            print(f"   {status} {metric}: {value:.3f}")
        
        print("\n💬 Feedback:")
        feedback = result.get('feedback', '')
        if feedback:
            for line in feedback.split('\n'):
                if line.strip():
                    print(f"   {line}")
        else:
            print("   No feedback provided")
        
        print("\n" + "=" * 80)
        print("✅ VALIDATION COMPLETE")
        print("=" * 80)
        
        # Exit with appropriate code
        sys.exit(0 if not result.get('needs_refinement', True) else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Validation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ VALIDATION FAILED")
        print("=" * 80)
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
