---
type: guide
audience: user, developer
status: stable
version: 1.0.0
last_audit: 2026-06-02
---
# TeaAgent Use Cases

Practical walkthroughs for the most common deployment scenarios.
Each section follows the same pattern: goal → relevant CLI / Python API → key configuration knobs.

**Related docs:**
- [Integration guide](integration-guide.md) — wiring new providers, tools, and UIs
- [Tool development](tool-development.md) — authoring safe, auditable tools
- [Approval policy design](approval-policy-design.md) — trust model configuration
- [CLI reference](../cli.md) — full flag reference
- [USAGE.md](../USAGE.md) — golden path quick-start

---

## 1. Simple Chat Session

**Goal:** Ask the agent a question and get an answer, no filesystem writes.

### CLI

```bash
teaagent chat "Explain the rate-limiting approach in teaagent/http_rate_limit.py"
```

The `chat` command starts a single-turn session in `read-only` permission mode by default.

### TUI

```bash
teaagent tui
```

Type your message at the prompt. The TUI accumulates real session cost displayed in the footer.

### Programmatic

```python
from teaagent import run_chat_agent, ChatAgentConfig, PermissionMode
from pathlib import Path

config = ChatAgentConfig(
    root=Path("."),
    permission_mode=PermissionMode.READ_ONLY,
    max_iterations=5,
)
result = run_chat_agent("Summarise the audit module", config=config)
print(result.content)
```

**Key knobs:**
| Setting | Default | Notes |
|---------|---------|-------|
| `permission_mode` | `PROMPT` | `READ_ONLY` for no-write sessions |
| `max_iterations` | 10 | Hard iteration cap |
| `max_tool_calls` | 10 | Tool call cap within `max_iterations` |

---

## 2. Multi-Turn Conversation with Approvals

**Goal:** Interactive conversation where destructive actions require explicit approval.

### CLI

```bash
teaagent tui
# inside TUI, approve individual tool calls interactively
```

### Programmatic

```python
from teaagent import run_chat_agent, ChatAgentConfig, PermissionMode
from teaagent.runner import ApprovalHandler
from pathlib import Path

def my_approval_handler(tool_name: str, arguments: dict, call_id: str) -> bool:
    """Return True to approve, False to deny."""
    print(f"[approval] {tool_name} with {list(arguments.keys())}")
    return input("Approve? [y/N] ").lower() == "y"

config = ChatAgentConfig(
    root=Path("."),
    permission_mode=PermissionMode.PROMPT,
    approval_handler=my_approval_handler,
    max_iterations=20,
)
result = run_chat_agent("Refactor the cost_tracker module", config=config)
```

### Scoped pre-approval (CLI)

Pre-approve specific tools and paths without prompting every call:

```bash
teaagent approval grant workspace_write_file --path-glob 'src/**' --root .
teaagent approval grant workspace_run_shell_mutate --command-prefix 'pytest ' --root .
teaagent approval list --root .
# Revoke when done:
teaagent approval revoke <grant_id> --root .
```

Pre-approved grants expire after 8 hours by default.

---

## 3. Cost-Limited Autonomous Run

**Goal:** Run the agent autonomously with a hard cost ceiling and no interactive prompts.

```bash
teaagent run gpt "Add docstrings to all public functions" \
  --permission-mode workspace-write \
  --max-cost-cents 50 \
  --skip-plan-check \
  --root .
```

### Programmatic

```python
from teaagent import AgentRunner, AuditLogger, RunBudget
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.workspace_tools import build_workspace_tool_registry
from teaagent.runner import FinalAnswer, ToolRequest
from teaagent import create_llm_adapter
from pathlib import Path

root = Path(".")
registry = build_workspace_tool_registry(root)
audit = AuditLogger(path=root / ".teaagent" / "audit.jsonl")
budget = RunBudget(
    max_iterations=30,
    max_tool_calls=50,
    max_estimated_cost_cents=50,   # hard stop at $0.50
)
policy = ApprovalPolicy(
    permission_mode=PermissionMode.WORKSPACE_WRITE,
    allow_all_destructive=True,    # no interactive prompts
)

llm = create_llm_adapter("gpt")

def decide(context):
    resp = llm.complete(context.llm_request)
    return resp  # the runner parses ToolRequest / FinalAnswer from model output

runner = AgentRunner(registry=registry, audit=audit, budget=budget, approval_policy=policy)
result = runner.run(task="Add docstrings to all public functions", decide=decide)
print(result.status, f"cost={result.cost_cents:.2f}c")
```

**Key knobs:**
| Field | Type | Purpose |
|-------|------|---------|
| `RunBudget.max_estimated_cost_cents` | `int` | Stops run when pre-flight estimate exceeds limit |
| `RunBudget.max_iterations` | `int` | Loop iteration hard cap |
| `RunBudget.max_tool_calls` | `int` | Total tool-call hard cap |
| `ApprovalPolicy.allow_all_destructive` | `bool` | Disable interactive approval prompts |

---

## 4. Suspended / Resumed Session

**Goal:** Pause a long-running session and resume it later, preserving conversation state.

```bash
# Start a run
teaagent run gpt "Migrate all f-strings to .format()" --root . --permission-mode workspace-write

# In TUI: press Ctrl+Z to suspend
# Resume later:
teaagent resume --root .
```

### Programmatic (checkpoint store)

```python
from teaagent import ChatAgentConfig, run_chat_agent
from teaagent.checkpoint import CheckpointStore
from pathlib import Path

store = CheckpointStore(path=Path(".teaagent/checkpoints"))

config = ChatAgentConfig(
    root=Path("."),
    checkpoint_store=store,
    max_iterations=50,
)

# First run — agent may be interrupted
result = run_chat_agent("Long task…", config=config)

# Resume from last checkpoint
result = run_chat_agent(None, config=config)  # None → resume mode
```

**Undo a completed run:**

```bash
teaagent agent undo --last --root .
```

---

## 5. Custom Tool Integration

**Goal:** Add a domain-specific tool (e.g. database query) that the agent can call.

See the full [tool development guide](tool-development.md) for the complete workflow. Quick recipe:

```python
from teaagent.tools import ToolAnnotations, ToolRegistry
from teaagent.workspace_tools import build_workspace_tool_registry
from teaagent import run_chat_agent, ChatAgentConfig, PermissionMode
from pathlib import Path
import sqlite3

root = Path(".")
registry = build_workspace_tool_registry(root)

registry.register(
    name="db_query",
    description="Run a read-only SQL SELECT against the project database.",
    input_schema={
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "SELECT statement only"},
        },
        "required": ["sql"],
    },
    output_schema={
        "type": "object",
        "properties": {"rows": {"type": "array"}},
        "required": ["rows"],
    },
    annotations=ToolAnnotations(read_only=True, idempotent=True),
    handler=lambda args: {
        "rows": sqlite3.connect("project.db").execute(args["sql"]).fetchall()
    },
)

config = ChatAgentConfig(root=root, permission_mode=PermissionMode.READ_ONLY)
result = run_chat_agent("How many open issues are in the DB?", config=config, registry=registry)
```

---

## 6. LLM Provider Setup

**Goal:** Switch or configure LLM providers (OpenAI, Anthropic, Ollama, etc.).

```bash
# Interactive setup wizard
teaagent setup --root . --provider gpt --write-env

# Smoke-test a provider
teaagent doctor model gpt

# Conformance check (contract tier)
teaagent model conformance --provider anthropic
```

Providers are configured via `.teaagent/config.json` or environment variables:

```json
{
  "provider": "anthropic",
  "model": "claude-sonnet-4-6",
  "fallback_provider": "gpt"
}
```

Or per-environment:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export TEAAGENT_PROVIDER=anthropic
```

See the [integration guide § LLM Provider](integration-guide.md#1-adding-a-new-llm-provider) for building a custom adapter.

---

## 7. Approval Policy Customization

**Goal:** Configure exactly which operations require approval, for whom, and with what evidence.

```bash
# Workspace-write mode, prompt only for git push and shell mutations
teaagent run gpt "update changelog" \
  --permission-mode workspace-write \
  --root .
```

### Multi-sig quorum (high-stakes operations)

```json
{
  "multi_sig": {
    "enabled": true,
    "required_approvals": 2,
    "peer_agent_ids": ["agent-alice", "agent-bob"],
    "high_risk_patterns": ["git push", "rm -rf"]
  }
}
```

Load via:

```python
from teaagent.approval_manager import MultiSigQuorumConfig
from pathlib import Path

config = MultiSigQuorumConfig.from_workspace_config(Path("."))
```

See [Approval Policy Design](approval-policy-design.md) for pattern-matching, path-scoping, and JIT approval design.

---

## 8. Plan-then-Execute Workflow

**Goal:** Generate a human-reviewable plan before any writes occur.

```bash
# Generate plan artifact (read-only, no writes)
teaagent plan gpt "refactor the auth module" --root . --permission-mode read-only

# Review the plan, then bind execution to it
teaagent run gpt --from-plan .teaagent/plans/20260602-refactor-auth.md \
  --permission-mode workspace-write \
  --root .
```

The run record logs the plan artifact path and content hash in the audit trail.

---

## See Also

- [Examples](examples/) — copy-paste working Python snippets
- [Migration guide](migration.md) — coming from Claude Code, Codex, or OpenCode
- [Architecture](../architecture.md) — system design overview
