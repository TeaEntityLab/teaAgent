# approval_manager — Public API Reference

## `PermissionMode` (Enum)
**Location**: `approval_manager.py:32`

```python
class PermissionMode(str, Enum):
    READ_ONLY = 'read-only'
    WORKSPACE_WRITE = 'workspace-write'
    PROMPT = 'prompt'
    ALLOW = 'allow'
    DANGER_FULL_ACCESS = 'danger-full-access'
```

This is the canonical definition. See also [governance/api.md](../governance/api.md) for the permission mode table.

---

## `JITApprovalState` (dataclass)
**Location**: `approval_manager.py:39`

In-memory per-session approval state.

```python
@dataclass
class JITApprovalState:
    approved_call_ids: set[str]
    session_approved_tools: set[str]

    def approve_once(self, call_id: str) -> None
    def approve_session(self, tool_name: str) -> None
    def is_call_approved(self, call_id: str) -> bool
    def is_tool_session_approved(self, tool_name: str) -> bool
```

---

## `MultiSigQuorumConfig` (frozen dataclass)
**Location**: `approval_manager.py:73`

```python
@dataclass(frozen=True)
class MultiSigQuorumConfig:
    enabled: bool = False
    required_approvals: int = 2
    peer_agent_ids: list[str] = field(default_factory=list)
    peer_public_keys: dict[str, str] = field(default_factory=dict)
```

---

## `ApprovalManager`
**Location**: `approval_manager.py`

Primary approval coordination class.

### `__init__`
```python
ApprovalManager(
    permission_mode: PermissionMode = PermissionMode.PROMPT,
    *,
    jit_state: Optional[JITApprovalState] = None,
    store: Optional[ApprovalPresetStore] = None,
    quorum_config: Optional[MultiSigQuorumConfig] = None,
    audit_logger: Optional[AuditLogger] = None,
)
```

### `assert_allowed`
```python
def assert_allowed(
    self,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    call_id: Optional[str] = None,
    security_tier: str = 'Medium',
) -> None
```
- **Pre**: none
- **Post**: Returns silently if tool is allowed.
- **Raises**: `ToolPermissionError` with a `DenialReasonCode` if not allowed.
- **Evaluation order**: permission mode → JIT call_id → JIT session → store preset → store scoped → pre-approved call IDs → multi-sig quorum → JIT TTY prompt → raise

### `is_allowed`
```python
def is_allowed(
    self,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    call_id: Optional[str] = None,
) -> bool
```
Non-raising version of `assert_allowed`. Returns `True` or `False`.

### `grant`
```python
def grant(
    self,
    tool_name: str,
    *,
    scope: Literal['once', 'session', 'permanent'],
    call_id: Optional[str] = None,
) -> None
```
Grants approval for `tool_name`. `once` = single call, `session` = this process lifetime, `permanent` = written to store.

### `deny`
```python
def deny(self, tool_name: str, *, scope: Literal['session', 'permanent']) -> None
```
Denies `tool_name`. `deny` takes precedence over allow grants.

---

## `ApprovalPresetStore`
**Location**: `ergonomics/approval_store.py`

Persistent approval storage backed by `approvals.json`.

```python
class ApprovalPresetStore:
    @classmethod
    def from_path(cls, path: Path) -> 'ApprovalPresetStore': ...

    def is_allowed(self, tool_name: str, arguments: dict) -> bool
    def grant_permanent(self, tool_name: str, *, scope_key: Optional[str] = None) -> None
    def deny_permanent(self, tool_name: str) -> None
    def revoke(self, tool_name: str) -> None
    def list_grants(self) -> list[dict[str, Any]]
```

TTLs: permanent grants expire after `APPROVAL_TTL_HOURS=24.0`; session grants after `SESSION_TTL_HOURS=8.0`.

---

## `DenialReasonCode` (Enum)
**Location**: `teaagent/errors.py`

```python
class DenialReasonCode(str, Enum):
    PERMISSION_MODE = 'permission_mode'
    DENIED_BY_GRANT = 'denied_by_grant'
    NO_GRANT_FOUND = 'no_grant_found'
    TTL_EXPIRED = 'ttl_expired'
    QUORUM_NOT_MET = 'quorum_not_met'
    READ_ONLY_RUNTIME = 'read_only_runtime'
```
