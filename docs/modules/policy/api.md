# policy — Public API Reference

## Data Models

### `ApprovalPolicy`
| Field | Type | Description |
|---|---|---|
| `preapproved_call_ids` | `frozenset[str]` | Deprecated pre-approved call ids for compatibility. |
| `allow_all_destructive` | `bool` | Global destructive-operation bypass. |
| `permission_mode` | `PermissionMode` | Active permission mode for call evaluation. |
| `approval_store` | `ApprovalPresetStore | None` | Optional persistent approval presets. |
| `multi_sig_config` | `MultiSigQuorumConfig` | Quorum requirements for high-risk approvals. |
| `agent_id` | `str` | Agent identifier for quorum operations. |
| `workspace_root` | `str` | Workspace root used in approval coordination. |

### `PermissionMode`
| Field | Type | Description |
|---|---|---|
| `READ_ONLY` | `str` | Blocks destructive/write tool execution. |
| `WORKSPACE_WRITE` | `str` | Allows workspace writes with governance checks. |
| `PROMPT` | `str` | Requires approval prompt for destructive calls. |
| `ALLOW` | `str` | Allows destructive calls without prompt. |
| `DANGER_FULL_ACCESS` | `str` | Full-access mode for trusted automation. |

## Functions

### `ApprovalPolicy.assert_allowed(*, tool_name: str, call_id: str, destructive: bool, arguments: dict[str, Any] | None = None, jit_state: JITApprovalState | None = None, plan_contract: Any = None, read_only: bool | None = None, description: str = '', handler: Any | None = None) -> None`
**Location**: `teaagent/policy.py:88`
**Pre-condition**: Call metadata and policy context are provided.
**Post-condition**: Returns `None` if allowed; raises permission/policy exception if denied.

### `parse_permission_mode(value: str) -> PermissionMode`
**Location**: `teaagent/policy.py:531`
**Pre-condition**: `value` is permission-mode text.
**Post-condition**: Returns enum on valid input; raises `ValueError` listing supported values otherwise.
