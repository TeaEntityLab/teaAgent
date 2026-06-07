# ADR 0026: CLI Execution Abstraction Layer

## Status

Accepted

## Context

CLI handlers duplicated RunStore, audit, and approval wiring. Multiple entry points (`agent run`, `daily`, TUI) needed consistent construction.

## Decision

Introduce `teaagent/cli/execution.py` with `AgentExecutionFactory` for shared component construction. Handlers obtain stores, loggers, and runners through the factory.

## Consequences

- Reduced duplication in `cli/_handlers/`
- Single place to adjust defaults for new surfaces
- Factory must stay thin — no domain logic
