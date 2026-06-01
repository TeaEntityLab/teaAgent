# ADR 0018: Async-from-sync bridge for approval paths

## Status

Proposed

## Context

Approval and multi-signature collection use asyncio coroutines (federated sync,
JIT server) but are invoked from synchronous tool dispatch and policy checks.
Historically some paths called `asyncio.set_event_loop()` inside worker threads,
which is fragile and can interact badly with caller threads.

## Decision

Use `teaagent.async_bridge.run_coroutine_sync`:

- No running loop in the current thread → `asyncio.run(coro)`.
- Running loop in the current thread → submit `asyncio.run(coro)` to a
  `ThreadPoolExecutor` provided by the caller (`ApprovalPolicy`,
  `MultiSigApprovalManager`).

Never call `asyncio.set_event_loop()` from approval or policy code.

## Consequences

- Signature collection from async IDE/MCP hosts does not close the host loop.
- Callers inside a running loop must pass an executor (already present on policy
  and multisig managers).
- New sync→async bridges should reuse `run_coroutine_sync` rather than ad-hoc
  loop management.
