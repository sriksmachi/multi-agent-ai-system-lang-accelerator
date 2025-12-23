"""
OpenTelemetry GenAI Semantic Conventions Reference

This module provides reference documentation for OpenTelemetry semantic conventions
used in the multi-agent system. The actual instrumentation is handled by:
- opentelemetry-instrumentation-openai-v2 (automatic OpenAI SDK tracing)
- opentelemetry-instrumentation-fastapi (automatic FastAPI tracing)
- Manual span creation using standard OpenTelemetry APIs

For automatic instrumentation:
- OpenAI calls are traced automatically by opentelemetry-instrumentation-openai-v2
- FastAPI endpoints are traced automatically by FastAPIInstrumentor
- No custom wrappers needed!

Semantic Conventions Reference:
https://opentelemetry.io/docs/specs/semconv/gen-ai/

## GenAI Attributes (OTEL Standard)

### System and Model
- gen_ai.system: AI system name (e.g., "openai", "azure_openai")
- gen_ai.request.model: Model being requested
- gen_ai.response.model: Model that generated response
- gen_ai.response.id: Response identifier
- gen_ai.response.finish_reasons: List of finish reasons

### Request Parameters
- gen_ai.request.temperature: Temperature setting
- gen_ai.request.max_tokens: Maximum tokens
- gen_ai.request.top_p: Top-p sampling
- gen_ai.request.frequency_penalty: Frequency penalty
- gen_ai.request.presence_penalty: Presence penalty

### Token Usage
- gen_ai.usage.input_tokens: Prompt tokens consumed
- gen_ai.usage.output_tokens: Completion tokens generated

### Operation Metadata
- gen_ai.operation.name: Operation type (e.g., "chat", "completion")

## Agent Attributes (Custom)
- agent.name: Agent identifier (planner, researcher, writer, reviewer)
- agent.user_id: User context
- agent.thread_id: Conversation/thread context
- agent.type: Type of agent

## Workflow Attributes (Custom)
- workflow.name: Workflow identifier
- workflow.step: Current step (plan, research, write, review, route)
- workflow.state: Current state

## Search Attributes (Custom)
- search.query: Search query text
- search.results_count: Number of results
- search.index: Index name
- search.top_score: Highest relevance score
- search.avg_score: Average relevance score

## Evaluation Attributes (Custom)
- eval.metric: Metric name
- eval.score: Score value
- eval.threshold: Threshold value
- eval.passed: Pass/fail boolean

## Usage Example

```python
from opentelemetry import trace

# Get tracer
tracer = trace.get_tracer(__name__)

# Create a span with GenAI conventions
with tracer.start_as_current_span(
    "gen_ai.client.operation",
    attributes={
        "gen_ai.system": "azure_openai",
        "gen_ai.request.model": "gpt-4",
        "gen_ai.request.temperature": 0.7,
        "gen_ai.operation.name": "chat",
    }
) as span:
    # Your code here
    response = client.chat.completions.create(...)
    
    # Add response attributes
    span.set_attribute("gen_ai.usage.input_tokens", response.usage.prompt_tokens)
    span.set_attribute("gen_ai.usage.output_tokens", response.usage.completion_tokens)
    span.set_attribute("gen_ai.response.model", response.model)
    
    # Add events
    span.add_event("completion_received", {"tokens": response.usage.total_tokens})
```

## Automatic Instrumentation Setup

```python
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Instrument OpenAI SDK (automatic tracing of all OpenAI calls)
OpenAIInstrumentor().instrument()

# Instrument FastAPI app (automatic tracing of all HTTP endpoints)
FastAPIInstrumentor.instrument_app(app)
```

Note: With automatic instrumentation, you get GenAI-compliant tracing without
writing custom wrapper functions!
"""

# This file now serves as reference documentation only.
# All actual tracing is handled by:
# 1. opentelemetry-instrumentation-openai-v2 (for OpenAI calls)
# 2. opentelemetry-instrumentation-fastapi (for FastAPI endpoints)
# 3. Standard OpenTelemetry APIs (for custom spans)

