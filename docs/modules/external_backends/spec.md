# external_backends — Behavior Specification

## Purpose

Provider-agnostic backend adapter layer for LLM providers. Manages provider configuration, model selection, and cost tracking.

## Current State

The `BackendRegistry` class in `teaagent/backend_registry.py` provides the core registry functionality. Provider-specific adapters are in `teaagent/external_backends.py`.

## Behavior

- Provider registration via a Registry pattern
- Dynamic model selection based on task requirements
- Cost estimation for provider/model combinations
