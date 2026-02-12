"""
Intelligent Reasoning Router for LangGraph workflow.

Uses a reasoning model (Azure OpenAI o1/o3 or gpt-4 with chain-of-thought)
to analyze the current workflow state and decide the next node to execute.
The thinking process is extracted and streamed to clients via notifications.
"""

import os
import sys
import json
from typing import Dict, Any, Optional, Tuple, Callable, Awaitable
from dataclasses import dataclass
from datetime import datetime

# Add parent directory to path for standalone execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential
from azure.identity import get_bearer_token_provider
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from core.logging_config import get_logger

load_dotenv()
logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)


# Router prompt for reasoning about workflow state
ROUTER_SYSTEM_PROMPT = """You are an intelligent workflow router for a LinkedIn post generation system.
Your job is to analyze the current state of the workflow and decide what action to take next.

## Workflow Overview
The workflow consists of these nodes:
1. **planner** - Creates a structured outline/plan for the post
2. **researcher** - Retrieves relevant context and information  
3. **writer** - Generates the post content based on plan and research
4. **reviewer** - Evaluates quality, provides scores and feedback
5. **end** - Workflow is complete

## Decision Rules
Think through the state carefully and decide the next step:

- If `plan` is empty → next: "planner"
- If `plan` exists but `context` is empty → next: "researcher"  
- If `context` exists or says 'No relevant documents found for the topic' but `draft` is empty → next: "writer"
- If `draft` exists but hasn't been reviewed (no scores) → next: "reviewer"
- If review shows `needs_refinement=true` AND `refinement_count < max_refinements`:
  → next: "writer" (for refinement with feedback)
- If review is approved (`needs_refinement=false`) OR max refinements reached:
  → next: "end"

## Response Format
Respond with ONLY a JSON object:
{
    "thinking": "Your detailed reasoning about the current state and why you're making this decision...",
    "decision": "next_node_name",
    "confidence": 0.95,
    "summary": "Brief one-line summary of decision"
}

Valid values for "decision": "planner", "researcher", "writer", "reviewer", "end"
"""


@dataclass
class RouterDecision:
    """Result of the intelligent router's decision."""
    thinking: str
    decision: str
    confidence: float
    summary: str
    raw_response: str = ""
    reasoning_tokens: int = 0


class ReasoningRouter:
    """
    Intelligent router that uses a reasoning model to decide workflow transitions.
    
    Extracts the thinking process from the model and makes it available for
    streaming to clients as real-time updates.
    """
    
    def __init__(
        self,
        deployment_name: Optional[str] = None,
        notification_callback: Optional[Callable[[str, str], Awaitable[None]]] = None
    ):
        """
        Initialize the reasoning router.
        
        Args:
            deployment_name: Azure OpenAI deployment name (defaults to env var)
            notification_callback: Async callback for sending thinking updates
                                   Signature: async def callback(thinking: str, decision: str)
        """
        self.deployment_name = deployment_name or os.getenv(
            "AZURE_OPENAI_REASONING_DEPLOYMENT",
            os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        )
        self.notification_callback = notification_callback
        self._client = self._initialize_client()
    
    def _initialize_client(self) -> AzureOpenAI:
        """Initialize Azure OpenAI client."""
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        reasoning = {
            "effort": "medium", 
            "summary": "detailed",  
        }
        model_kwargs = {"reasoning": reasoning}
        
        if api_key:
            logger.info("ReasoningRouter: Using API key authentication")
            return AzureOpenAI(
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_key=api_key,
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
                timeout=60
            )
        else:
            logger.info("ReasoningRouter: Using token-based authentication")
            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(
                credential,
                "https://cognitiveservices.azure.com/.default"
            )
            return AzureOpenAI(
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                azure_ad_token_provider=token_provider,
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
                timeout=60,
            )
    
    def _build_state_summary(self, state: Dict[str, Any]) -> str:
        """Build a summary of the current workflow state for the router."""
        return f"""## Current Workflow State

**User ID**: {state.get('user_id', 'unknown')}
**Topic**: {state.get('topic', 'not set')}
**Platform**: {state.get('platform', 'linkedin')}
**Thread ID**: {state.get('thread_id', 'none')}

### Planning Phase
- **Plan**: {f'"{state.get("plan")[:200]}..."' if state.get('plan') else 'NOT CREATED'}

### Research Phase  
- **Context**: {f'"{state.get("context")[:200]}..."' if state.get('context') else 'NOT RETRIEVED'}
- **Documents Retrieved**: {len(state.get('retrieved_docs', []))}

### Writing Phase
- **Draft**: {f'"{state.get("draft")[:200]}..."' if state.get('draft') else 'NOT WRITTEN'}
- **Refinement Count**: {state.get('refinement_count', 0)}
- **Max Refinements**: {state.get('max_refinements', 3)}

### Review Phase
- **Scores**: {json.dumps(state.get('scores', {})) if state.get('scores') else 'NOT REVIEWED'}
- **Needs Refinement**: {state.get('needs_refinement', 'not evaluated')}
- **Feedback**: {state.get('feedback', 'none')}

### Output
- **Final Post**: {f'"{state.get("final_post")[:100]}..."' if state.get('final_post') else 'NOT FINALIZED'}

### Workflow Status
- **Current Node**: {state.get('current_node', 'router')}
- **Previous Decision**: {state.get('router_decision', 'none')}
"""
    
    async def decide_next_node(self, state: Dict[str, Any]) -> RouterDecision:
        """
        Use reasoning model to decide the next workflow node.
        
        Args:
            state: Current workflow state dictionary
            
        Returns:
            RouterDecision with thinking, decision, and metadata
        """
        user_id = state.get('user_id', 'unknown')
        thread_id = state.get('thread_id', 'unknown')
        
        with tracer.start_as_current_span(
            "reasoning_router.decide",
            attributes={
                "agent.name": "reasoning_router",
                "agent.user_id": user_id,
                "agent.thread_id": thread_id,
                "workflow.step": "route",
            }
        ) as span:
            try:
                state_summary = self._build_state_summary(state)
                user_prompt = f"Analyze this workflow state and decide the next step:\n\n{state_summary}"
                
                span.add_event("gen_ai.router.request", {
                    "state_summary_length": len(state_summary)
                })
                
                logger.info(
                    f"[{user_id}][{thread_id}] ReasoningRouter: Analyzing state for next node decision",
                    extra={"user_id": user_id, "thread_id": thread_id}
                )
                
                # Call the reasoning model
                # Note: o-series models (o1, o3, o4-mini) don't support temperature parameter
                response = self._client.chat.completions.create(
                    model=self.deployment_name,
                    messages=[
                        {"role": "user", "content": f"{ROUTER_SYSTEM_PROMPT}\n\n{user_prompt}"}
                    ],
                    max_completion_tokens=2000,
                    reasoning_effort="high",  # Pass it HERE if using o1/o3 models to enable detailed reasoning content
                )
                
                raw_content = response.choices[0].message.content
                
                logger.info(f"Reasoning Tokens: {response.usage.completion_tokens_details.reasoning_tokens}")
                
                # Parse the JSON response
                decision = self._parse_router_response(raw_content)
                decision.raw_response = raw_content
                
                # Track token usage
                if hasattr(response, 'usage') and response.usage:
                    if hasattr(response.usage, 'completion_tokens_details'):
                        details = response.usage.completion_tokens_details
                        if hasattr(details, 'reasoning_tokens'):
                            decision.reasoning_tokens = details.reasoning_tokens
                    span.set_attribute("gen_ai.usage.input_tokens", response.usage.prompt_tokens)
                    span.set_attribute("gen_ai.usage.output_tokens", response.usage.completion_tokens)
                
                # Send notification if callback is registered
                if self.notification_callback:
                    await self.notification_callback(decision.thinking, decision.decision)
                
                span.set_attribute("router.decision", decision.decision)
                span.set_attribute("router.confidence", decision.confidence)
                span.set_attribute("router.reasoning_length", len(decision.thinking))
                span.add_event("gen_ai.router.decision", {
                    "decision": decision.decision,
                    "confidence": decision.confidence,
                    "summary": decision.summary,
                    "gen_ai.event.content": json.dumps({
                        "thinking": decision.thinking[:500],
                        "decision": decision.decision
                    })
                })
                span.set_status(Status(StatusCode.OK))
                
                logger.info(
                    f"[{user_id}][{thread_id}] ReasoningRouter: Decision='{decision.decision}' "
                    f"(confidence={decision.confidence:.2f}): {decision.summary}",
                    extra={
                        "user_id": user_id,
                        "thread_id": thread_id,
                        "decision": decision.decision,
                        "confidence": decision.confidence,
                        "thinking_length": len(decision.thinking)
                    }
                )
                
                return decision
                
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                logger.error(f"ReasoningRouter error: {e}", exc_info=True)
                
                # Fallback to rule-based routing
                return self._fallback_decision(state)
    
    def _parse_router_response(self, content: str) -> RouterDecision:
        """Parse the router's JSON response and extract thinking."""
        try:
            # Try to parse as JSON
            # Handle markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            data = json.loads(content)
            
            # Combine reasoning_content (from o1/o3) with thinking field
            thinking = ""
            if data.get("thinking"):
                if thinking:
                    thinking = f"[Model Reasoning]\n{thinking}\n\n[Explicit Thinking]\n{data['thinking']}"
                else:
                    thinking = data["thinking"]
            
            return RouterDecision(
                thinking=thinking,
                decision=data.get("decision", "planner"),
                confidence=float(data.get("confidence", 0.5)),
                summary=data.get("summary", "No summary provided")
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse router response: {e}")
            # Extract any visible thinking and use default decision
            return RouterDecision(
                thinking=f"Parse error - raw response: {content[:500]}",
                decision="planner",
                confidence=0.3,
                summary="Fallback to planner due to parse error"
            )
    
    def _fallback_decision(self, state: Dict[str, Any]) -> RouterDecision:
        """Rule-based fallback when reasoning model fails."""
        plan = state.get("plan", "")
        context = state.get("context", "")
        draft = state.get("draft", "")
        scores = state.get("scores", {})
        needs_refinement = state.get("needs_refinement", False)
        refinement_count = state.get("refinement_count", 0)
        max_refinements = state.get("max_refinements", 3)
        
        thinking = "Fallback rule-based decision:\n"
        
        if not plan:
            decision = "planner"
            thinking += "- Plan is empty, need to create plan first."
        elif not context:
            decision = "researcher"
            thinking += "- Plan exists but no context, need research."
        elif not draft:
            decision = "writer"
            thinking += "- Have plan and context but no draft, need to write."
        elif not scores:
            decision = "reviewer"
            thinking += "- Draft exists but not reviewed, need review."
        elif needs_refinement and refinement_count < max_refinements:
            decision = "writer"
            thinking += f"- Needs refinement ({refinement_count}/{max_refinements}), refining draft."
        else:
            decision = "end"
            thinking += "- Review complete or max refinements reached, finalizing."
        
        return RouterDecision(
            thinking=thinking,
            decision=decision,
            confidence=1.0,
            summary=f"Rule-based fallback: {decision}"
        )


# Singleton instance for reuse
_router_instance: Optional[ReasoningRouter] = None


def get_reasoning_router(
    notification_callback: Optional[Callable[[str, str], Awaitable[None]]] = None
) -> ReasoningRouter:
    """Get or create the reasoning router singleton."""
    global _router_instance
    if _router_instance is None:
        _router_instance = ReasoningRouter(notification_callback=notification_callback)
    elif notification_callback:
        _router_instance.notification_callback = notification_callback
    return _router_instance



if __name__ == "__main__":
    """Validate reasoning support and test decide_next_node."""
    import sys
    import asyncio
    
    # Test decide_next_node with sample data
    print("\n" + "=" * 60)
    print("Testing decide_next_node with sample state")
    print("=" * 60)
    
    sample_state = {
        "user_id": "test-user",
        "thread_id": "test-thread",
        "topic": "AI in software development",
        "platform": "linkedin",
        "plan": "",  # Empty plan triggers planner
        "context": "",
        "draft": "",
        "scores": {},
        "refinement_count": 0,
        "max_refinements": 3
    }
    
    async def test_router():
        router = ReasoningRouter()
        decision = await router.decide_next_node(sample_state)
        print(f"\nDecision: {decision.decision}")
        print(f"Confidence: {decision.confidence}")
        print(f"Summary: {decision.summary}")
        print(f"Thinking: {decision.thinking[:300]}...")
    
    asyncio.run(test_router())