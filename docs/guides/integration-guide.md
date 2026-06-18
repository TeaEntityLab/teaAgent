---
type: guide
audience: developer, integrator
status: stable
version: 1.0.0
last_audit: 2026-06-02
---
# Integration Guide

Step-by-step guides for extending and embedding TeaAgent.

**Related docs:**
- [Tool development](tool-development.md) — full tool authoring reference
- [Approval policy design](approval-policy-design.md) — trust model
- [Provider authoring](../provider-authoring.md) — existing provider reference
- [Plugin skill catalog](../plugin-skill-catalog.md) — published plugins

---

## 1. Adding a New LLM Provider

TeaAgent routes all model calls through the `LLMAdapter` protocol defined in `teaagent/llm.py`.

### Protocol

```python
class LLMAdapter(Protocol):
    provider: str
    def complete(self, request: LLMRequest) -> LLMResponse: ...
```

### Step-by-step

**1. Implement the adapter**

```python
# my_provider/adapter.py
from teaagent.llm import LLMAdapter, LLMRequest, LLMResponse, LLMResponseFormatError

class MyProviderAdapter:
    provider = "my-provider"

    def __init__(self, api_key: str, model: str = "my-model-v1"):
        self._api_key = api_key
        self._model = model

    def complete(self, request: LLMRequest) -> LLMResponse:
        import httpx

        payload = {
            "model": request.model or self._model,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in request.messages
            ],
            "max_tokens": request.max_tokens or 4096,
            "temperature": request.temperature or 0.7,
        }
        if request.system:
            payload["system"] = request.system

        resp = httpx.post(
            "https://api.my-provider.example/v1/complete",
            json=payload,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        if not content:
            raise LLMResponseFormatError("my-provider returned empty content")

        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            raw=data,
        )
```

**2. Register the provider config**

Add an entry to `PROVIDER_CONFIGS` in `teaagent/llm.py`, or register at runtime:

```python
from teaagent.llm import PROVIDER_CONFIGS, ProviderConfig

PROVIDER_CONFIGS["my-provider"] = ProviderConfig(
    name="my-provider",
    env_key="MY_PROVIDER_API_KEY",
    default_model="my-model-v1",
    adapter_class="my_provider.adapter.MyProviderAdapter",
)
```

**3. Run conformance check**

```bash
teaagent model conformance --provider my-provider
```

Conformance tiers: `smoke` (non-empty content) → `contract` (system prompt, token reporting) → `TOOL_CALLING` → `LATENCY`.

**4. Add tests**

```python
# tests/test_my_provider.py
from my_provider.adapter import MyProviderAdapter
from teaagent.llm import LLMRequest, LLMMessage

def test_complete(respx_mock):
    respx_mock.post("https://api.my-provider.example/v1/complete").mock(
        return_value=httpx.Response(200, json={
            "choices": [{"message": {"content": "hello"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        })
    )
    adapter = MyProviderAdapter(api_key="test")
    resp = adapter.complete(LLMRequest(messages=[LLMMessage(role="user", content="hi")]))
    assert resp.content == "hello"
    assert resp.input_tokens == 10
```

**Required behavior checklist:**

> **Last codebase audit: 2026-06-04** — Cross-referenced against all provider adapters and the LLM
> base classes. Items marked ✅ are verified in the shipped adapters. Unchecked boxes remain
> **human review gates for new providers**.

- [x] `LLMResponseFormatError` raised on empty/malformed response (not empty string returned)
      ✅ Defined in `teaagent/llm.py`. Raised by OpenAI, Anthropic, and built-in adapters when
      response body is empty or missing content. See `LLMResponseFormatError` usage across adapters.
- [x] `LLMProviderError` raised on provider-side blocks/errors
      ✅ Defined in `teaagent/llm.py`. Raised by all shipped adapters on HTTP 4xx/5xx,
      rate limits, and provider-specific error responses.
- [x] `input_tokens` and `output_tokens` populated when provider reports them
      ✅ `LLMResponse.input_tokens` / `output_tokens` populated from provider usage stats
      in all shipped adapters (OpenAI, Anthropic, Gemini, OpenRouter, etc.).
- [x] Raw response preserved in `LLMResponse.raw`
      ✅ `LLMResponse.raw` stores the complete provider response dict in all shipped adapters.
- [x] `request.system` respected when provider supports system prompts
      ✅ System prompt forwarding verified in OpenAI, Anthropic, Gemini adapters.
      Some providers (e.g. older OSS models) may not support it — adapter handles gracefully.
- [x] `max_tokens` and `temperature` forwarded where supported
      ✅ Both parameters forwarded from `LLMRequest` to provider payload in all shipped adapters.

---

## 2. Adding a Tool

Tools extend what the agent can _do_. All tools must go through `ToolRegistry`.

See the full [tool development guide](tool-development.md) for annotations, error handling, and audit patterns. Quick recipe:

```python
from teaagent.tools import ToolAnnotations, ToolRegistry
from teaagent.workspace_tools import build_workspace_tool_registry
from pathlib import Path

root = Path(".")
registry = build_workspace_tool_registry(root)

registry.register(
    name="send_slack_message",
    description="Send a message to a Slack channel. Requires SLACK_TOKEN env var.",
    input_schema={
        "type": "object",
        "properties": {
            "channel": {"type": "string"},
            "text": {"type": "string"},
        },
        "required": ["channel", "text"],
    },
    output_schema={
        "type": "object",
        "properties": {"ok": {"type": "boolean"}, "ts": {"type": "string"}},
        "required": ["ok"],
    },
    annotations=ToolAnnotations(
        read_only=False,
        destructive=True,   # requires approval token in default policy
        idempotent=False,
        stateful=False,
    ),
    handler=_slack_handler,
)
```

**Package as a plugin** — see [§ Plugin Development](#4-plugin-development).

---

## 3. Creating a Custom Approval Policy

The `ApprovalPolicy` dataclass wires permission mode, JIT approvals, path scoping, and multi-sig quorum.

### Minimal read-only policy

```python
from teaagent.policy import ApprovalPolicy, PermissionMode

policy = ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY)
```

### Path-scoped write policy

```python
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.ergonomics.approval_store import ApprovalPresetStore
from pathlib import Path

store = ApprovalPresetStore(root=Path("."))
# Pre-grant workspace_write_file for src/ only
store.grant("workspace_write_file", path_glob="src/**")

policy = ApprovalPolicy(
    permission_mode=PermissionMode.WORKSPACE_WRITE,
    approval_store=store,
)
```

### Hook-level permission guard

Add a `PreToolUse` hook for fine-grained control without modifying the policy:

```python
from teaagent.hooks import HookRegistry, HookPermissionMode, permission_check_hook

registry_hook = HookRegistry()
registry_hook.register_pre_hook(
    permission_check_hook(
        mode=HookPermissionMode.ASK,
        allow_patterns=frozenset({"src/**", "tests/**"}),
        deny_patterns=frozenset({"secrets/**", ".env"}),
    )
)
```

See [Approval Policy Design](approval-policy-design.md) for full pattern reference.

---

## 4. Plugin Development

Plugins register additional tools via Python entry-points. TeaAgent discovers them at startup without code changes.

### Project layout

```
my-teaagent-plugin/
├── pyproject.toml
├── src/
│   └── my_plugin/
│       ├── __init__.py
│       └── tools.py          # register() goes here
└── tests/
    └── test_tools.py
```

### `pyproject.toml` entry-point

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "teaagent-my-plugin"
version = "0.1.0"
dependencies = ["teaagent>=0.1"]

[project.entry-points."teaagent.tools"]
my_plugin = "my_plugin.tools:register"
```

The entry-point value must be callable with signature `register(registry: ToolRegistry) -> None`.

### `tools.py`

```python
# src/my_plugin/tools.py
from teaagent.tools import ToolAnnotations, ToolRegistry

def register(registry: ToolRegistry) -> None:
    registry.register(
        name="my_plugin_greet",
        description="Return a greeting string.",
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
        output_schema={
            "type": "object",
            "properties": {"greeting": {"type": "string"}},
            "required": ["greeting"],
        },
        annotations=ToolAnnotations(read_only=True, idempotent=True),
        handler=lambda args: {"greeting": f"Hello, {args['name']}!"},
    )
```

### Loading plugins

```python
from teaagent.plugins import load_plugins
from teaagent.tools import ToolRegistry

registry = ToolRegistry()
result = load_plugins(registry)
if not result.ok:
    print("Failed plugins:", result.failed)
```

Or via `build_workspace_tool_registry` which calls `load_plugins` automatically.

### Plugin security

TeaAgent audits plugin source on load (`_audit_plugin_source`). Third-party packages are flagged if they cannot be resolved to a verified file location. Review `PluginLoadResult.failed` for any load failures.

---

## 5. Building a Custom UI

TeaAgent is not tied to the built-in REPL or TUI. You can build any UI (web, Electron, Slack bot, VS Code extension) on top of `run_chat_agent` or `AgentRunner`.

### Pattern A: streaming web API

```python
# app.py (FastAPI)
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from teaagent import run_chat_agent, ChatAgentConfig, PermissionMode
from pathlib import Path
import json

app = FastAPI()

@app.post("/chat")
async def chat(body: dict):
    chunks = []

    def on_chunk(text: str) -> None:
        chunks.append(text)

    config = ChatAgentConfig(
        root=Path("."),
        permission_mode=PermissionMode.READ_ONLY,
        stream=True,
        on_chunk=on_chunk,
        stream_text_only=True,
    )

    async def generate():
        result = run_chat_agent(body["message"], config=config)
        for chunk in chunks:
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield f"data: {json.dumps({'done': True, 'cost': result.cost_cents})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

### Pattern B: embedding AgentRunner directly

```python
from teaagent import AgentRunner, AuditLogger, RunBudget
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.workspace_tools import build_workspace_tool_registry
from teaagent.runner import Decision, FinalAnswer, ToolRequest
from pathlib import Path

class MyUI:
    def __init__(self, root: Path):
        self.registry = build_workspace_tool_registry(root)
        self.audit = AuditLogger(path=root / ".teaagent" / "audit.jsonl")
        self.runner = AgentRunner(
            registry=self.registry,
            audit=self.audit,
            budget=RunBudget(max_iterations=20),
            approval_policy=ApprovalPolicy(
                permission_mode=PermissionMode.PROMPT,
                approval_handler=self._approve,  # your UI's approval callback
            ),
        )

    def _approve(self, tool_name: str, arguments: dict, call_id: str) -> bool:
        # Hook your UI's approval dialog here
        return self._show_approval_dialog(tool_name, arguments)

    def run(self, task: str, decide_fn) -> None:
        result = self.runner.run(task=task, decide=decide_fn)
        self._display_result(result)
```

### Pattern C: VS Code / ACP extension

The MCP server surface exposes all registered tools over HTTP. Start it and connect any MCP client:

```bash
teaagent mcp serve --http --port 7330 --root .
```

The extension in `vscode/` demonstrates how to boot this server from an IDE extension context. See `tests/test_vscode_extension_mcp_boot_flow.py` for the acceptance contract.

---

## 6. Middleware and Hooks

Hooks intercept tool calls at 8 lifecycle points without modifying `AgentRunner` or `ChatAgent`.

See [Middleware and Hooks guide](../modules/hooks/spec.md) for the complete reference. Key integration patterns:

### Logging every tool call

```python
from teaagent.hooks import HookRegistry

hook_reg = HookRegistry()

def audit_pre(tool_name: str, arguments: dict) -> dict | None:
    print(f"[pre]  {tool_name}: {list(arguments.keys())}")
    return None  # no modification

def audit_post(tool_name: str, arguments: dict, result: dict) -> dict | None:
    print(f"[post] {tool_name}: ok={result.get('ok', '?')}")
    return None

hook_reg.register_pre_hook(audit_pre)
hook_reg.register_post_hook(audit_post)

config = ChatAgentConfig(root=Path("."), hook_registry=hook_reg)
```

### Auto-format on every file write

```python
from teaagent.hooks import format_check_hook, HookRegistry
from pathlib import Path

hook_reg = HookRegistry()
hook_reg.register_post_hook(format_check_hook(root=Path(".")))
```

### Run tests after every write

```python
from teaagent.hooks import run_tests_hook, HookRegistry
from pathlib import Path

hook_reg = HookRegistry()
hook_reg.register_post_hook(run_tests_hook(root=Path("."), command=["pytest", "-x", "-q"]))
```

---

## 7. Telemetry and Observability Integration

See the dedicated [metrics and telemetry section](../audit-events.md) and [run evidence guide](../run-evidence-and-audit-guide.md).

Quick OpenTelemetry wiring:

```python
from teaagent.telemetry import TelemetryConfig, configure_telemetry, configure_metrics

configure_telemetry(TelemetryConfig(
    service_name="my-teaagent-deployment",
    otlp_endpoint="http://localhost:4317",
))
configure_metrics(otlp_endpoint="http://localhost:4317")
```

---

## See Also

- [Examples](examples/) — working code for each integration pattern
- [Architecture](../architecture.md) — component map
- [Specs](../specs/) — formal interface contracts
