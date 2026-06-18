# Model Capability Matrix

Last updated: 2026-06-01

This document maps TeaAgent features to model capabilities across different providers and models. Use this to determine which models support specific governance and workflow features.

## Feature Definitions

| Feature | Description | TeaAgent Impact |
|---------|-------------|-----------------|
| **Extended Thinking** | Model can reason internally before outputting | Better plan quality, fewer tool calls |
| **Tool Use** | Model can call structured tools | Core agent functionality |
| **Streaming** | Model can stream responses in real-time | Better UX for long responses |
| **Multi-Sig** | Model can participate in consensus workflows | Federated swarm operations |
| **Cost Tracking** | Model provides token usage metadata | Budget enforcement and reporting |
| **JSON Mode** | Model outputs valid JSON reliably | Structured tool calls |
| **Parallel Tools** | Model can call multiple tools simultaneously | Faster execution |

## Provider Matrix

### OpenAI

| Model | Extended Thinking | Tool Use | Streaming | Multi-Sig | Cost Tracking | JSON Mode | Parallel Tools |
|-------|------------------|----------|-----------|-----------|--------------|-----------|----------------|
| GPT-4o | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| GPT-4o-mini | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| GPT-4-turbo | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| o1-preview | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ |
| o1-mini | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ |

### Anthropic

| Model | Extended Thinking | Tool Use | Streaming | Multi-Sig | Cost Tracking | JSON Mode | Parallel Tools |
|-------|------------------|----------|-----------|-----------|--------------|-----------|----------------|
| Claude 3.5 Sonnet | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Claude 3.5 Haiku | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Claude 3 Opus | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Claude 3 Sonnet | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### Google

| Model | Extended Thinking | Tool Use | Streaming | Multi-Sig | Cost Tracking | JSON Mode | Parallel Tools |
|-------|------------------|----------|-----------|-----------|--------------|-----------|----------------|
| Gemini 1.5 Pro | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Gemini 1.5 Flash | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Gemini 1.0 Pro | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### Local Models (via Ollama, vLLM, etc.)

| Model | Extended Thinking | Tool Use | Streaming | Multi-Sig | Cost Tracking | JSON Mode | Parallel Tools |
|-------|------------------|----------|-----------|-----------|--------------|-----------|----------------|
| Llama 3.1 70B | ❌ | ✅ | ✅ | ✅ | ❌ | ⚠️ | ⚠️ |
| Llama 3.1 8B | ❌ | ✅ | ✅ | ✅ | ❌ | ⚠️ | ⚠️ |
| Mistral 7B | ❌ | ✅ | ✅ | ✅ | ❌ | ⚠️ | ⚠️ |
| Qwen 2.5 72B | ❌ | ✅ | ✅ | ✅ | ❌ | ⚠️ | ⚠️ |

**Legend:**
- ✅ = Fully supported
- ❌ = Not supported
- ⚠️ = Partial support (may require specific parameters or is unreliable)

## Feature Requirements by TeaAgent Component

### Core Agent Loop
- **Required:** Tool Use, JSON Mode
- **Recommended:** Streaming, Cost Tracking
- **Optional:** Extended Thinking, Parallel Tools

### Plan Generation
- **Required:** Tool Use, JSON Mode
- **Recommended:** Extended Thinking
- **Optional:** Streaming

### Multi-Sig Consensus
- **Required:** Tool Use, JSON Mode
- **Recommended:** Cost Tracking
- **Optional:** Extended Thinking

### Budget Enforcement
- **Required:** Cost Tracking
- **Recommended:** Tool Use
- **Optional:** Streaming

## Model Selection Guide

### For Production Use
- **Best overall:** GPT-4o, Claude 3.5 Sonnet
- **Cost-effective:** GPT-4o-mini, Claude 3.5 Haiku
- **Extended thinking:** o1-preview, Claude 3.5 Sonnet

### For Development/Testing
- **Fast iteration:** GPT-4o-mini, Claude 3.5 Haiku, Gemini 1.5 Flash
- **Local testing:** Llama 3.1 8B (via Ollama)

### For High-Stakes Operations
- **Best reasoning:** o1-preview, Claude 3.5 Sonnet
- **Best reliability:** GPT-4o, Claude 3.5 Sonnet

## Updating This Matrix

When adding new provider adapters or model support:

1. Add the provider section above
2. Map each model to the feature columns
3. Update the adapter implementation to report capabilities
4. Test each feature with the new model
5. Update this document with the "Last updated" date

## Related Documentation

- [Provider Adapter Factory](../teaagent/llm/_config.py)
- [Tool Registry](../teaagent/tools.py)
- [Budget Enforcement](../teaagent/budget.py)
- [Multi-Sig Consensus](../teaagent/consensus/consensus_validation.py)
