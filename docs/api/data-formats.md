# Data Format Specifications

All persistent data lives under the workspace-relative `.teaagent/` directory unless noted otherwise.

---

## Directory Layout

```
.teaagent/
├── config.json              # Workspace configuration
├── tui_state.json           # TUI session state (last exit)
├── workspace_registry.json  # Global workspace lock registry (~/.teaagent/)
├── runs/
│   └── <run_id>.jsonl       # Audit log + run events (one event per line)
├── sessions/
│   └── <session_id>.json    # Saved chat sessions
├── plans/
│   └── <timestamp>-<slug>.md
├── undo/
│   └── <run_id>/            # Undo journal snapshots
└── graph.db                 # GraphQLite database (optional)
```

---

## Audit Log Format

**Path:** `.teaagent/runs/<run_id>.jsonl`  
**Format:** JSONL (one JSON object per line, UTF-8)  
**Appended:** Each event is appended atomically during a run.

### Event Record

```json
{
  "event_id": "a1b2c3d4e5f6...",
  "event_type": "string",
  "run_id": "run_20260602_abc123",
  "created_at": "2026-06-02T10:00:00.000Z",
  "payload": { ... },
  "prev_hash": "hex-string-or-null",
  "hash": "hex-string-or-null",
  "chain_hmac": "hex-string-or-null"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | string | UUID hex, globally unique |
| `event_type` | string | See event type table below |
| `run_id` | string | Identifies the parent run |
| `created_at` | string | ISO 8601 with milliseconds, UTC |
| `payload` | object | Event-specific data (see below) |
| `prev_hash` | string\|null | SHA-256 of previous event record (chain integrity) |
| `hash` | string\|null | SHA-256 of this event record |
| `chain_hmac` | string\|null | HMAC-SHA256 of this record using chain key |

### Audit Levels

| Level | Data included |
|-------|--------------|
| `L0` | `event_type`, `run_id`, `created_at` only (metrics-safe) |
| `L1` | L0 + `event_id`, tool name (no arguments) |
| `L2` | L1 + redacted payload (sensitive fields masked as `"[REDACTED]"`) |
| `L3` | Full unredacted record |

### Event Payloads

#### `run_start`

```json
{
  "task": "string",
  "provider": "string",
  "model": "string",
  "permission_mode": "string",
  "max_iterations": 10,
  "max_tool_calls": 10,
  "max_estimated_cost_cents": 0,
  "git_sandbox": false,
  "allow_destructive": false
}
```

#### `run_end`

```json
{
  "status": "completed | failed | approval_denied | limit_exceeded | cost_exceeded",
  "iterations": 3,
  "tool_calls": 7,
  "cost_cents": 0.042,
  "input_tokens": 4200,
  "output_tokens": 1800,
  "error_message": "string | null",
  "final_answer": "string | null"
}
```

#### `tool_call`

```json
{
  "tool_name": "write_file",
  "call_id": "call_abc123",
  "arguments": { "path": "src/auth.py", "content": "[REDACTED at L2]" },
  "reasoning": "string | null",
  "annotations": {
    "read_only": false,
    "destructive": true,
    "security_tier": "High"
  }
}
```

#### `tool_result`

```json
{
  "tool_name": "write_file",
  "call_id": "call_abc123",
  "result": { "success": true, "bytes_written": 4096 },
  "elapsed_ms": 23
}
```

#### `tool_error`

```json
{
  "tool_name": "write_file",
  "call_id": "call_abc123",
  "error_type": "PermissionError",
  "error_message": "Permission denied: src/auth.py"
}
```

#### `approval_request`

```json
{
  "call_id": "call_abc123",
  "tool_name": "shell_exec",
  "arguments": { "command": "rm -rf dist/" },
  "reason": "Destructive tool requires approval",
  "annotations": { "destructive": true, "security_tier": "High" }
}
```

#### `approval_granted` / `approval_denied`

```json
{
  "call_id": "call_abc123",
  "tool_name": "shell_exec",
  "granted_by": "jit_prompt | preset | multi_sig | pre_approved",
  "reason": "string | null"
}
```

#### `model_request`

```json
{
  "provider": "claude",
  "model": "claude-opus-4-8",
  "input_tokens": 4200,
  "tool_count": 3,
  "iteration": 2
}
```

#### `model_response`

```json
{
  "stop_reason": "tool_use | end_turn | max_tokens",
  "output_tokens": 450,
  "cost_cents": 0.011,
  "tool_calls_requested": 2
}
```

#### `cost_checkpoint`

```json
{
  "cumulative_cost_cents": 0.034,
  "cumulative_input_tokens": 8400,
  "cumulative_output_tokens": 2700,
  "cap_cents": 100
}
```

---

## Session JSON Schema

**Path:** `.teaagent/sessions/<session_id>.json`

```json
{
  "$schema": "https://teaagent.dev/schemas/session/v1.json",
  "id": "abc123",
  "created_at": "2026-06-01T09:14:00Z",
  "updated_at": "2026-06-02T10:22:00Z",
  "label": "auth refactor",
  "messages": [
    {
      "role": "user | assistant | system",
      "content": "string"
    }
  ],
  "focus_stack": {
    "frames": [
      {
        "topic": "string",
        "state": "created | kept | pushed | returned | cleared",
        "message_start_index": 0,
        "message_end_index": 12,
        "conclusion": "string | null"
      }
    ]
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique session identifier |
| `created_at` | string | ISO 8601, UTC |
| `updated_at` | string | ISO 8601, updated on every save |
| `label` | string | Human-readable label (may be empty) |
| `messages` | array | Ordered message history |
| `focus_stack.frames` | array | Context focus stack entries |

---

## Configuration Format

**Path:** `.teaagent/config.json`

```json
{
  "llm": {
    "provider": "claude",
    "model": "claude-opus-4-8",
    "base_url": "https://api.anthropic.com"
  },
  "approval": {
    "mode": "prompt",
    "presets": {
      "my-preset": [
        {
          "tool": "read_file",
          "allow": true
        },
        {
          "tool": "write_file",
          "allow": false,
          "reason": "writes require review"
        }
      ]
    }
  },
  "multi_sig": {
    "enabled": false,
    "required_approvals": 2,
    "peer_agent_ids": ["peer-a", "peer-b"],
    "peer_public_keys": {
      "peer-a": "ssh-ed25519 AAAA..."
    },
    "peer_relay_urls": {
      "peer-a": "https://relay.example.com"
    },
    "local_relay_base_url": null,
    "allow_dev_signatures": false,
    "high_risk_patterns": ["shell_exec", "rm_*"],
    "timeout_seconds": 300
  },
  "permissions": {
    "mode": "workspace-write"
  },
  "telemetry": {
    "otlp_endpoint": null,
    "service_name": "teaagent",
    "console": false
  },
  "profiles": {
    "ci": {
      "llm": { "provider": "gpt" },
      "approval": { "mode": "allow" }
    }
  }
}
```

Profile values override top-level values when `--profile ci` is passed.

---

## TUI State Format

**Path:** `.teaagent/tui_state.json`

```json
{
  "provider": "claude",
  "model": null,
  "root": "/Users/me/project",
  "allow_destructive": false,
  "permission_mode": "prompt",
  "progress": true,
  "stream": false,
  "subagent": false,
  "chat": false,
  "session_id": "abc123",
  "pinned_files": ["src/auth.py"],
  "heartbeat": 0,
  "effort": "normal",
  "route_model_enabled": false
}
```

---

## Cost Tracking Format

Cost data is extracted from audit logs. The `CostTracker` class aggregates across all `.jsonl` files in `.teaagent/runs/`.

**Per-run summary record (in memory):**

```json
{
  "run_id": "run_20260602_abc123",
  "label": "auth refactor",
  "model": "claude-opus-4-8",
  "created_at": "2026-06-02T10:00:00Z",
  "status": "completed",
  "cost_cents": 4.2,
  "input_tokens": 12000,
  "output_tokens": 4000
}
```

---

## Suspension State Format

When a run is suspended to background (via `background` REPL command or `--background` flag), a checkpoint is written:

**Path:** `.teaagent/runs/<run_id>/checkpoint.json`

```json
{
  "run_id": "run_20260602_abc123",
  "suspended_at": "2026-06-02T10:45:00Z",
  "iteration": 3,
  "tool_calls_made": 5,
  "messages": [ ... ],
  "pending_tool_request": {
    "tool_name": "shell_exec",
    "arguments": { "command": "make test" },
    "call_id": "call_def456",
    "reasoning": null
  },
  "cost_cents_so_far": 1.8,
  "input_tokens_so_far": 6000,
  "output_tokens_so_far": 1200
}
```

`pending_tool_request` is non-null only when the run was suspended mid-approval (the tool call had not yet been dispatched).

---

## Workspace Lock Registry

**Path:** `~/.teaagent/workspace_registry.json`  
(Global — shared across all workspaces on the machine.)

```json
{
  "/abs/path/to/project-a": {
    "workspace_path": "/abs/path/to/project-a",
    "owner_pid": 12345,
    "acquired_at": "2026-06-02T10:00:00Z"
  },
  "/abs/path/to/project-b": {
    "workspace_path": "/abs/path/to/project-b",
    "owner_pid": 67890,
    "acquired_at": "2026-06-02T11:00:00Z"
  }
}
```

---

## Plan Artifact Format

**Path:** `.teaagent/plans/<timestamp>-<slug>.md`  
**Format:** Markdown with YAML front matter.

```markdown
---
task: "migrate SQLite to PostgreSQL"
created_at: "2026-06-02T10:00:00Z"
provider: "claude"
model: "claude-opus-4-8"
status: "draft"
---

# Plan: migrate SQLite to PostgreSQL

## Steps

1. Audit current schema in `models.py`
2. Add `asyncpg` dependency
3. ...
```

---

## Undo Journal Format

**Path:** `.teaagent/undo/<run_id>/`

Each file modified during a run has a snapshot:

```
.teaagent/undo/run_abc123/
├── manifest.json       # List of all modified files
└── snapshots/
    ├── <encoded_path>  # Pre-modification file content
    └── ...
```

**`manifest.json`:**

```json
{
  "run_id": "run_abc123",
  "created_at": "2026-06-02T10:00:00Z",
  "files": [
    {
      "path": "src/auth.py",
      "snapshot_key": "c2F2ZWQ...",
      "existed_before": true,
      "size_before": 4096
    }
  ]
}
```
