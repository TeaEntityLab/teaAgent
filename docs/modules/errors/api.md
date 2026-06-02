# errors — Public API Reference

## Data Models

### `DenialReasonCode`
| Field | Type | Description |
|---|---|---|
| `READ_ONLY_MODE` | `str` | Denied by read-only mode gate. |
| `WORKSPACE_WRITE_MODE` | `str` | Denied by workspace-write restrictions. |
| `FILE_POLICY_DENIED` | `str` | Denied by file policy match. |
| `PLAN_CONTRACT_DENIED` | `str` | Denied for missing/invalid plan contract. |
| `JIT_USER_DENIED` | `str` | User denied JIT approval request. |
| `JIT_NO_APPROVAL` | `str` | Approval required but not granted. |
| `MULTISIG_NO_QUORUM` | `str` | Quorum signature threshold not met. |
| `AUTO_MODE_BLOCKED` | `str` | Auto-mode policy blocked call. |
| `MISSING_STATE` | `str` | Required approval state unavailable. |

### `ErrorCategory`
| Field | Type | Description |
|---|---|---|
| `TRANSIENT` | `str` | Temporary/retryable failures. |
| `MODEL_LOGIC` | `str` | Model decision or budget contract failures. |
| `PERMISSION` | `str` | Policy and approval denials. |
| `SYSTEM` | `str` | Runtime/system execution failures. |

### `AgentHarnessError`
| Field | Type | Description |
|---|---|---|
| `hint` | `Optional[str]` | Optional actionable remediation hint. |
| `category` | `ErrorCategory` | Classification consumed by callers. |

## Functions

### `AgentHarnessError.__init__(message: str, *, hint: Optional[str] = None) -> None`
**Location**: `teaagent/errors.py:47`
**Pre-condition**: `message` is presentable error text.
**Post-condition**: Initializes error with optional hint for user-facing output.

### `ToolPermissionError.__init__(message: str, *, hint: Optional[str] = None, reason_code: Optional[DenialReasonCode] = None) -> None`
**Location**: `teaagent/errors.py:89`
**Pre-condition**: Permission denial context exists.
**Post-condition**: Creates permission-classified error with optional structured denial code.

### `RunCancelledError.__init__(message: str = 'run cancelled', *, hint: Optional[str] = None) -> None`
**Location**: `teaagent/errors.py:123`
**Pre-condition**: Cancellation path triggered.
**Post-condition**: Creates cancellation error with resume-oriented default hint.
