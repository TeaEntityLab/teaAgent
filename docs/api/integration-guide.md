# Integration Guide

How to extend teaagent: add LLM providers, register tools, define approval policies, build CLI commands, and wire up external systems.

---

## Adding an LLM Provider

### 1. Define the provider config

In `teaagent/llm/_config.py`, add an entry to `PROVIDER_CONFIGS`:

```python
from teaagent.llm._config import ProviderConfig, PROVIDER_CONFIGS

PROVIDER_CONFIGS['my-provider'] = ProviderConfig(
    name='my-provider',
    api_key_env='MY_PROVIDER_API_KEY',          # env var name
    default_model='my-provider/model-v1',
    base_url='https://api.my-provider.com/v1',
    base_url_env='MY_PROVIDER_BASE_URL',        # optional override
)
```

### 2. Add cost tables

```python
from teaagent.llm._config import (
    PROVIDER_COST_PER_1K_INPUT,
    PROVIDER_COST_PER_1K_OUTPUT,
)

PROVIDER_COST_PER_1K_INPUT['my-provider/model-v1'] = 0.003    # $ per 1K input tokens
PROVIDER_COST_PER_1K_OUTPUT['my-provider/model-v1'] = 0.015   # $ per 1K output tokens
```

### 3. Implement the adapter

If your provider is OpenAI-compatible, use `OpenAICompatibleAdapter`:

```python
from teaagent.llm._adapters import OpenAICompatibleAdapter

class MyProviderAdapter(OpenAICompatibleAdapter):
    pass
```

For a custom wire format, subclass `LLMAdapter`:

```python
from teaagent.llm import LLMAdapter, LLMRequest, LLMResponse

class MyProviderAdapter(LLMAdapter):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        # Call your API and return an LLMResponse
        ...

    async def stream(self, request: LLMRequest):
        # Yield tokens as strings
        ...
```

### 4. Register the adapter

In `teaagent/llm/__init__.py`, add a case in `create_llm_adapter`:

```python
def create_llm_adapter(provider: str, model=None) -> LLMAdapter:
    ...
    if provider == 'my-provider':
        return MyProviderAdapter(config=PROVIDER_CONFIGS['my-provider'], model=model)
    ...
```

### 5. Test the integration

```bash
teaagent doctor providers
teaagent model smoke --provider my-provider
```

---

## Registering a Custom Tool

Tools must be registered through `ToolRegistry`. They are available to both the agent loop and the MCP server.

### Minimal example

```python
from teaagent.tools import ToolRegistry, ToolAnnotations, ToolDefinition

registry = ToolRegistry()

registry.register(
    name='fetch_weather',
    description='Fetch current weather for a city. Returns temperature in Celsius.',
    input_schema={
        'type': 'object',
        'properties': {
            'city': {'type': 'string', 'description': 'City name'},
        },
        'required': ['city'],
    },
    output_schema={
        'type': 'object',
        'properties': {
            'temperature_c': {'type': 'number'},
            'description': {'type': 'string'},
        },
    },
    annotations=ToolAnnotations(
        read_only=True,
        destructive=False,
        idempotent=True,
        security_tier='Low',
    ),
    handler=lambda args: {
        'temperature_c': 22.0,
        'description': 'Sunny',
    },
)
```

### With rate limiting

```python
from teaagent.tools import ToolRateLimit

registry.register(
    name='send_email',
    ...
    rate_limit=ToolRateLimit(max_calls=5, window_seconds=60),
)
```

### Handler signature

Handlers receive a validated `dict` and must return a `dict`:

```python
def my_handler(arguments: dict[str, Any]) -> dict[str, Any]:
    # arguments is validated against input_schema before this is called
    result = do_work(arguments['param'])
    return {'output': result}
```

Raise `ValueError` for expected failure cases — the error is caught, logged in the audit trail, and returned to the model as a tool error (not a crash).

### Security annotations

| Annotation | When to set `True` |
|-----------|-------------------|
| `read_only` | Tool never mutates any state |
| `destructive` | Tool may delete, overwrite, or send data externally |
| `idempotent` | Running twice is safe (no double-send, double-write) |
| `stateful` | Tool modifies persistent external state (DB, files, APIs) |

`security_tier` controls which approval rules apply:

| Tier | Approval required when |
|------|----------------------|
| `Low` | Never (unless `permission_mode=read-only`) |
| `Medium` | `permission_mode=prompt` or stricter |
| `High` | Always requires explicit approval in `prompt` mode |
| `Critical` | Always requires explicit approval or multi-sig |

---

## Defining Approval Policies

### Using permission modes

The simplest integration is choosing the right `PermissionMode`:

```python
from teaagent.policy import ApprovalPolicy, PermissionMode, MultiSigQuorumConfig

policy = ApprovalPolicy(
    permission_mode=PermissionMode.WORKSPACE_WRITE,
    preapproved_call_ids=frozenset(),
    allow_all_destructive=False,
    approval_store=None,
    approval_origin_run_id=None,
    enable_jit_prompt=False,
    multi_sig_config=MultiSigQuorumConfig(enabled=False, ...),
    agent_id='my-agent',
    workspace_root='/path/to/project',
)
```

### Pre-approving specific calls

```python
policy = ApprovalPolicy(
    permission_mode=PermissionMode.PROMPT,
    preapproved_call_ids=frozenset(['call_abc123', 'call_def456']),
    ...
)
```

### Checking approval in a tool dispatcher

```python
from teaagent.policy import ApprovalDeniedError

try:
    policy.assert_allowed(
        tool_name='write_file',
        call_id='call_abc123',
        destructive=True,
        arguments={'path': 'src/auth.py', 'content': '...'},
    )
except ApprovalDeniedError as e:
    # Log the denial and surface to the user
    print(f'Denied: {e}')
```

### Multi-signature quorum

For high-stakes environments where multiple peer agents must co-sign destructive actions:

```python
multi_sig = MultiSigQuorumConfig(
    enabled=True,
    required_approvals=2,
    peer_agent_ids=['peer-alpha', 'peer-beta'],
    peer_public_keys={
        'peer-alpha': 'ssh-ed25519 AAAA...',
        'peer-beta': 'ssh-ed25519 BBBB...',
    },
    peer_relay_urls={
        'peer-alpha': 'https://relay.internal/peer-alpha',
        'peer-beta': 'https://relay.internal/peer-beta',
    },
    local_relay_base_url='https://relay.internal/self',
    allow_dev_signatures=False,
    high_risk_patterns=['shell_exec', 'delete_*'],
    timeout_seconds=300,
)
```

---

## Adding a CLI Subcommand

### 1. Write the handler

```python
# teaagent/cli/_handlers/my_command.py
from argparse import Namespace

def handle_my_command(args: Namespace) -> int:
    print(f'Running my-command with option: {args.my_option}')
    return 0
```

### 2. Register the parser

In `teaagent/cli/__init__.py`, in `build_parser()`:

```python
my_parser = subparsers.add_parser('my-command', help='Does X')
my_parser.add_argument('--my-option', default='default')
my_parser.set_defaults(handler=handle_my_command)
```

### 3. Import the handler

```python
from teaagent.cli._handlers.my_command import handle_my_command
```

---

## Registering Hook Handlers

Hooks fire at key points in the agent lifecycle. Register with `hook_registry`:

```python
from teaagent.hooks import hook_registry

@hook_registry.register('before_tool_call')
def my_before_hook(context: dict) -> None:
    print(f"About to call: {context['tool_name']}")

@hook_registry.register('after_tool_call')
def my_after_hook(context: dict) -> None:
    print(f"Tool returned: {context['result']}")
```

### Available hook events

| Event | Context keys | Description |
|-------|-------------|-------------|
| `before_tool_call` | `tool_name`, `call_id`, `arguments` | Before dispatching a tool |
| `after_tool_call` | `tool_name`, `call_id`, `result`, `elapsed_ms` | After tool returns |
| `on_tool_error` | `tool_name`, `call_id`, `error` | When tool raises |
| `before_model_call` | `messages`, `model`, `iteration` | Before sending to LLM |
| `after_model_call` | `response`, `cost_cents`, `tokens` | After LLM responds |
| `on_run_start` | `run_id`, `task`, `config` | Run begins |
| `on_run_end` | `run_id`, `result` | Run completes |
| `on_approval_request` | `approval_request` | Approval prompt triggered |

---

## Integrating with External Audit Systems

The audit log JSONL files can be streamed to external systems:

```python
from teaagent.audit import AuditLogger, AuditEvent
import json

class MyAuditSink(AuditLogger):
    def log(self, event_type: str, payload: dict) -> None:
        super().log(event_type, payload)
        # Forward to external system
        self._send_to_splunk({
            'event_type': event_type,
            'payload': payload,
        })

    def _send_to_splunk(self, data: dict) -> None:
        ...
```

Or tail the JSONL file directly:

```bash
# Stream live audit events for a running agent
tail -f .teaagent/runs/<run_id>.jsonl | jq .event_type
```

Or use the built-in HTTP audit server:

```bash
teaagent audit serve --port 8080
# GET /events — SSE stream of new events
# GET /events/<run_id> — events for a specific run
# GET /runs — list all run IDs
```

---

## Integrating with CI/CD

### Non-interactive mode

Run without a TTY and parse JSON output:

```bash
result=$(teaagent run claude "run the test suite and fix any failures" \
  --permission-mode workspace-write \
  --output-format json \
  --no-stream \
  --quiet)

status=$(echo "$result" | jq -r .status)
if [ "$status" != "completed" ]; then
  echo "Agent failed: $(echo "$result" | jq -r .error_message)"
  exit 1
fi
```

### Cost guard in CI

```bash
teaagent run claude "fix the lint errors" \
  --max-estimated-cost-cents 50 \
  --permission-mode workspace-write \
  --output-format json
```

Exit code 3 if the cost cap is exceeded.

### Pre-approving tool calls

In a CI context where you want to allow specific destructive tool calls without an interactive prompt:

```bash
teaagent run claude "deploy to staging" \
  --permission-mode allow \
  --allow-destructive \
  --git-sandbox
```

---

## Embedding in a Python Application

```python
import asyncio
from teaagent.runner import AgentRunner
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.tools import ToolRegistry
from teaagent.llm import create_llm_adapter

# Set up dependencies
registry = ToolRegistry()
# register your tools...

policy = ApprovalPolicy(
    permission_mode=PermissionMode.ALLOW,
    preapproved_call_ids=frozenset(),
    allow_all_destructive=True,
    approval_store=None,
    approval_origin_run_id=None,
    enable_jit_prompt=False,
    multi_sig_config=...,
    agent_id='my-app',
    workspace_root='/path/to/project',
)

adapter = create_llm_adapter('claude')

# Run a task
runner = AgentRunner(
    adapter=adapter,
    tool_registry=registry,
    approval_policy=policy,
    workspace_root='/path/to/project',
    max_iterations=10,
    max_tool_calls=20,
)

result = asyncio.run(runner.run(task='summarise recent changes'))
print(result.final_answer.content)
print(f'Cost: ${result.cost_cents / 100:.4f}')
```

---

## Backwards Compatibility

| API surface | Status |
|-------------|--------|
| CLI subcommands and flags | **Stable** — flags will not be removed without a deprecation cycle |
| `--output-format json` response shape | **Stable** — new fields may be added; existing fields will not be removed or renamed |
| REPL slash commands | **Stable** |
| JSONL audit log fields | **Stable** — new fields may be added; `event_id`, `event_type`, `run_id`, `created_at`, `payload` are permanent |
| Session JSON schema | **Stable** |
| Config JSON schema | **Stable** — new top-level keys may be added |
| `TeaAgentTUI` constructor signature | **Stable** — new keyword-only args may be added |
| `ToolRegistry.register()` signature | **Stable** |
| `ApprovalPolicy` fields | **Stable** |
| `LLMAdapter.complete()` / `stream()` | **Stable** |
| `RunResult` fields | **Stable** |
| MCP protocol version `2024-11-05` | **Stable** |
| Internal `_` prefixed names | **Experimental** — may change without notice |
| `teaagent.runner` internals | **Experimental** |
| Automation / ultrawork commands | **Experimental** |
| Consensus / multi-sig relay protocol | **Experimental** |
| Cloud submit commands | **Experimental** |

### Deprecation Policy

1. A feature is marked `[deprecated]` in the CLI help and this documentation.
2. It continues to work for at least **two minor releases** after the deprecation notice.
3. It is removed in the next **major release** after the two-release grace period.
4. Experimental APIs may change in any release without a deprecation cycle.
