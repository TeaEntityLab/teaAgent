# Error Reference

> **Last updated:** 2026-06-07
> **Source:** `teaagent/errors.py` and error-handling code in modules below.

## Error Hierarchy

```
Exception
 └─ AgentHarnessError              (harness base, all errors carry a .hint)
     ├─ BudgetExceededError        (cost/budget cap hit)
     ├─ ToolValidationError        (tool call schema/argument validation)
     ├─ ToolPermissionError        (permission mode denied the call)
     ├─ ToolExecutionError         (tool execution failure)
     ├─ InvalidToolDecision        (model made a decision the harness cannot route)
     ├─ RunCancelledError          (operator/user cancelled the run)
     └─ AuditDurabilityError       (audit chain write failure in compliance mode)
```

All harness errors inherit from `AgentHarnessError` which guarantees a `hint` attribute
for actionable remediation messages. The CLI `main()` handler renders them as:

```
<message>
  → <hint>
```

## Error Categories

| Category | Meaning | Examples |
|----------|---------|----------|
| `TRANSIENT` | Temporary condition, retryable | Network timeout, rate limit, provider unavailable |
| `MODEL_LOGIC` | Model output could not be interpreted | Invalid JSON, missing required fields, malformed tool call |
| `PERMISSION` | Tool/operation denied by policy | Read-only mode, file policy, JIT denial, multisig failure |
| `SYSTEM` | Harness internal error | Audit chain failure, config loading error, unexpected exception |

## Denial Reason Codes

These are the specific reasons a tool call can be denied, used in the approval
pipeline audit trail:

| Code | Meaning | Trigger |
|------|---------|---------|
| `read_only_mode` | Tool blocked by global read-only mode | `--permission-mode read-only` |
| `workspace_write_mode` | Shell mutate blocked in workspace-write mode | Shell command classified as mutate |
| `file_policy_denied` | File path blocked by `~/.config/teaagent/file_policy.toml` | Path outside allowed globs |
| `plan_contract_denied` | Tool violates active plan scope | Tool outside plan contract bounds |
| `jit_user_denied` | User explicitly rejected the JIT approval prompt | User answered "no" |
| `jit_no_approval` | JIT approval timed out or was never collected | `JITApprovalServer` timeout |
| `multisig_no_quorum` | Multi-signature approval did not reach quorum | Insufficient peer approvals |
| `auto_mode_blocked` | Auto-mode blocked the tool for safety | Auto-mode heuristic check failed |
| `missing_state` | Required run state absent | Run not initialized or corrupted |
| `full_access_not_acknowledged` | `danger-full-access` not yet acknowledged | User skipped the acknowledge step |
| `skill_write_blocked` | Direct active-skill write blocked | Skill writer tried to modify a managed skill |

## CLI Exit Codes

| Code | Constant | Meaning |
|------|----------|---------|
| 0 | `EXIT_SUCCESS` | Normal completion |
| 1 | `EXIT_ERROR` | Harness error or user error |
| 2 | `EXIT_USAGE` | CLI argument/parsing error |

The `main()` function in `teaagent/cli/__init__.py` catches:
- `AgentHarnessError` → code 1, with hint if available
- `KeyboardInterrupt` → code 0, clean exit
- Generic `Exception` → code 1, with issue tracker URL; full traceback with `--verbose`

## Per-Module Error Patterns

| Module | Error Type(s) | Actionability |
|--------|--------------|---------------|
| `runner/_core.py` | `AgentHarnessError`, `ToolPermissionError`, `InvalidToolDecision` | High — all carry hints |
| `audit.py` | `AuditDurabilityError` | High — names the failed path and suggested recovery |
| `approval_manager.py` | `ToolPermissionError` with `DenialReasonCode` | High — reason code maps to specific UX guidance |
| `tools.py` | `ToolValidationError` | Medium — describes which argument failed |
| `tool_permissions.py` | `ToolPermissionError` | Medium — names the rule that blocked |
| `llm/_types.py` | `LLMAdapterError`, `LLMConfigurationError`, `LLMProviderError`, `LLMHTTPError`, `LLMResponseFormatError` | Medium — adapter-specific, some carry provider response |

## Troubleshooting by Error

### "Budget exceeded"
Likely cause: Task exceeded cost cap.  
Fix: Increase `--max-estimated-cost-cents` or set `effort` higher.  
See: `teaagent run --help`, TUI `/effort` command.

### "Tool permission denied"
Likely cause: Current permission mode blocks the tool.  
Fix: Use `--permission-mode allow` for trusted tasks.  
See: `teaagent run --help`, TUI `/permission` command.

### "Run not found"
Likely cause: Run ID is invalid or from a different workspace.  
Fix: Verify the run ID with `teaagent runs` or `teaagent audit list`.  
See: `teaagent runs --help`.

### "Provider not configured"
Likely cause: API key missing for the selected provider.  
Fix: Run `teaagent wizard` or set the corresponding environment variable.  
See: `teaagent doctor model <provider>`.
