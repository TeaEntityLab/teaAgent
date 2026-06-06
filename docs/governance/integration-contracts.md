# Integration Contracts (WS5)

> **Status:** Current truth for harness extension boundaries.
> **Implementation:** `teaagent/integration/`

## Goal

Preserve provider and plugin flexibility without uncontrolled framework growth.
CLI, TUI, plugins, and tests should share thin contracts instead of duplicating
orchestration code.

## WS5-001 — Run setup (`AgentService`)

**Module:** `teaagent/integration/run_contract.py`

```python
from pathlib import Path
from teaagent.integration import AgentService, RunSetupRequest, prepare_agent_run
from teaagent.policy import PermissionMode

prepared = prepare_agent_run(
    RunSetupRequest(root=Path('.'), permission_mode=PermissionMode.PROMPT)
)
# prepared.registry, prepared.audit, prepared.budget, prepared.approval_policy
```

`chat_agent` uses `build_run_budget()` and `build_approval_policy()` from this
module for runner construction.

## WS5-002 — Event stream

**Module:** `teaagent/integration/event_stream.py`

Audit records are normalized to a stable `RunEvent` shape with classification
and redacted payloads. Consumers subscribe through `RunEventStream` without
depending on internal `AuditEvent` objects.

```python
from teaagent.integration import normalize_run_event, replay_run_events

stream = replay_run_events(audit_events)
```

## WS5-003 — Approval strategy

**Module:** `teaagent/integration/approval_strategy.py`

Interactive, policy-backed, and test doubles implement `ApprovalStrategy` and
adapt to runner `ApprovalHandler` callbacks via `to_handler()`.

## WS5-004 — Storage interfaces

**Module:** `teaagent/integration/storage.py`

Protocols for runs, audit, approval presets, and memory with local adapters:

```python
from teaagent.integration import storage_bundle_for_workspace

bundle = storage_bundle_for_workspace('.')
events = bundle.audit.read_events('run-id')
```

Subagent durable queues remain under `teaagent/coordination/approval_backend.py`
(WS2-005).

## WS5-005 — Plugin governance

**Module:** `teaagent/integration/plugin_governance.py`

`load_plugins()` validates newly registered tools with `validate_plugin_tools()`.
Tools that fail schema, annotation, or governance lint are unregistered and the
plugin is marked failed.

## Verification

```bash
python3 -m pytest tests/test_ws5_integration_contracts.py -q
python3 -m ruff check teaagent/integration/
```

## Non-goals

- Replacing `AgentRunner` or adding a second agent framework
- Remote storage implementations (protocols only; local defaults ship today)
