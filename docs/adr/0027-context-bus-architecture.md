# ADR 0027: Context Bus Architecture

## Status

Accepted

## Context

Phase 5 introduced cross-cutting context propagation for subagents, skills, and audit correlation.

## Decision

Use a context bus pattern (`teaagent/context_bus.py`) for scoped run metadata, tool call correlation IDs, and subscriber hooks. Producers emit; consumers subscribe without direct coupling.

## Consequences

- Easier tracing across subagent boundaries
- Requires discipline to avoid bus as global mutable state
- Tests use explicit bus instances for isolation
