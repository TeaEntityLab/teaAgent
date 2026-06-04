# runner — Inspection: Purpose, Dependencies, Exports, Call Graph

## Purpose

The `runner` package is the central execution harness for agent runs. It takes a `DecisionFn` (the model) and a `ToolRegistry` and drives the full agent loop: iteration budgeting, tool dispatch, permission enforcement, audit recording, context compaction, and run summarization. It is the only module that should call `registry.execute()` directly in production code.

---

## Source Files

| File | Role |
|------|------|
| `runner/__init__.py` | Re-exports public API |
| `runner/_core.py` | `AgentRunner` class — the main run loop |
| `runner/_approval_manager.py` | `RunnerApprovalCoordinator` — approval workflow helper |
| `runner/_auto_mode_manager.py` | `AutoModeManager` — auto mode guard wrapper |
| `runner/_plan_validator.py` | `PlanValidator` — plan-before-write enforcement |
| `runner/_types.py` | Data types: `ToolRequest`, `FinalAnswer`, `Decision`, `ApprovalRequest`, `RunResult` |

---

## Exported Symbols (`runner/__init__.py`)

```python
from teaagent.runner import (
    AgentRunner,
    ApprovalHandler,
    ApprovalRequest,
    BudgetPromptHandler,
    Decision,
    DecisionFn,
    FinalAnswer,
    RunResult,
    ToolRequest,
)
```

---

## External Dependencies

### Direct imports in `_core.py`

| Module | Symbol | Purpose |
|--------|--------|---------|
| `teaagent.audit` | `AuditLogger` | Records all run events |
| `teaagent.auto_mode` | `AutoModeConfig` | Auto mode configuration |
| `teaagent.budget` | `RunBudget` | Budget constraints |
| `teaagent.budget_monitor` | `BudgetAction`, `BudgetMonitor` | Budget threshold checks and prompting |
| `teaagent.context` | `ContextCompactor` | Context window compaction |
| `teaagent.errors` | `AgentHarnessError`, `BudgetExceededError`, `ErrorCategory`, `RunCancelledError`, `ToolExecutionError`, `ToolPermissionError` | Error taxonomy |
| `teaagent.file_policy` | `FilePolicy` | File access policy |
| `teaagent.plugins` | `load_plugins` | Entry-point plugin loading |
| `teaagent.policy` | `ApprovalPolicy`, `JITApprovalState`, `PermissionMode` | Permission enforcement |
| `teaagent.subagent_run_context` | `bind_parent_run_id`, `reset_parent_run_id` | Context var for subagent parent tracking |
| `teaagent.tool_call_context` | `ToolCallContext`, `bind_tool_call_context`, `reset_tool_call_context` | Context var for active tool call |
| `teaagent.tools` | `ToolRegistry` | Tool lookup and execution |
| `teaagent.governance.tool_lint` | `lint_registry` | Read-only lint validation |
| `teaagent.ergonomics.run_summary` | `format_run_summary`, `summarize_run` | Post-run summary generation |

### Internal imports in sub-modules

| File | Imports |
|------|---------|
| `_approval_manager.py` | `teaagent.audit.AuditLogger`, `teaagent.policy.{ApprovalPolicy,JITApprovalState,PermissionMode}`, `._types.{ApprovalHandler,ApprovalRequest}` |
| `_auto_mode_manager.py` | `teaagent.auto_mode.{AutoModeConfig,AutoModeGuard}`, `teaagent.errors.ToolPermissionError`, `teaagent.policy.ApprovalPolicy` |
| `_plan_validator.py` | `teaagent.governance.plan_gate.assert_write_allowed`, `teaagent.policy.{ApprovalPolicy,PermissionMode}` |
| `_types.py` | `teaagent.audit.redact_tool_arguments`, `teaagent.ergonomics._approval_grants._compute_argument_digest` |

---

## Entry Points

### Primary: `AgentRunner.run()`

```python
runner.run(
    task="...",
    decide=my_decide_fn,
    run_id=None,                    # optional, uuid4().hex if omitted
    initial_observations=[],        # optional, for resumed runs
    initial_context_extra={},       # optional extra keys merged into context
    run_started_extra={},           # optional extra keys in run_started payload
) -> RunResult
```

### Construction: `AgentRunner.__init__()`

All parameters are keyword-only. Key required parameters:
- `registry: ToolRegistry`
- `audit: AuditLogger`

---

## Internal Call Graph

```
AgentRunner.run()
├── audit.record('run_started')
├── decision_log.inject_summary()              [optional]
└─ [loop per iteration]
    ├── auto_mode_manager.record_iteration()
    ├── audit.record('iteration_started')
    ├── cancel_token.is_set()                  [optional]
    ├── _assert_cost_budget()
    ├── decide(context)                        [caller-supplied]
    ├── _check_budget_warnings()
    │   └── budget_monitor.check_at_threshold()
    ├── _check_compaction_warning()
    ├── _assert_cost_budget()                  [second check, post-decide]
    ├─ [if FinalAnswer]
    │   ├── audit.record('run_completed')
    │   ├── auto_mode_manager.summary()        [if auto mode]
    │   ├── _emit_summary()
    │   │   └── _build_run_summary()
    │   │       └── summarize_run() + format_run_summary()
    │   └── return RunResult(status='completed')
    ├─ [if ToolRequest]
    │   ├── budget check: tool_calls >= max_tool_calls → BudgetExceededError
    │   ├── registry.get(tool_name)
    │   ├── file_policy.assert_allowed()       [optional]
    │   ├── plan_validator.validate_write_allowed()
    │   │   └── assert_write_allowed()         [governance.plan_gate]
    │   ├── auto_mode_manager.validate_tool_allowed()
    │   ├── auto_mode_manager.get_auto_approve_policy()
    │   ├── approval_policy.assert_allowed()
    │   │   [on ToolPermissionError →]
    │   │   ├── approval_manager.create_approval_request()
    │   │   ├── approval_manager.can_request_approval()
    │   │   ├── approval_manager.handle_approval_request()
    │   │   │   ├── audit.record('tool_call_pending_approval')
    │   │   │   ├── [if no handler] audit.record('run_paused') → return False
    │   │   │   └── approval_handler(request) → True/False
    │   │   └── [if not approvable] approval_manager.record_blocked()
    │   ├── audit.record('tool_call_started')
    │   ├── bind_parent_run_id()
    │   ├── bind_tool_call_context()
    │   ├── registry.execute()
    │   ├── reset_tool_call_context()
    │   ├── reset_parent_run_id()
    │   ├── context['observations'].append(observation)
    │   ├── audit.record('tool_call_completed' or 'tool_call_failed')
    │   ├── checkpoint_store.save()            [optional]
    │   └─ [if compactor and len(observations) > threshold]
    │       ├── compactor.compact(context)
    │       └── audit.record('context_compacted')
    └─ [on AgentHarnessError or bare Exception]
        ├── audit.record('run_failed')
        ├── _emit_summary()
        └── return RunResult(status='failed:…')
```

---

## Helper Class Relationships

```
AgentRunner
├── has-a RunnerApprovalCoordinator (runner._approval_manager)
│         └── has-a ApprovalPolicy
│         └── has-a JITApprovalState
│         └── optional ApprovalHandler callback
├── has-a AutoModeManager          (runner._auto_mode_manager)
│         └── optional AutoModeGuard
├── has-a PlanValidator            (runner._plan_validator)
│         └── approval_policy ref
│         └── _plan_contract
│         └── _read_only_registry_lint_errors
└── has-a BudgetMonitor
```
