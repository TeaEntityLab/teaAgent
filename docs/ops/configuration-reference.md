# Configuration Reference

TeaAgent merges configuration from multiple sources in descending priority order:

1. **CLI flags** (highest)
2. **Environment variables** (`TEAAGENT_*`)
3. **Workspace config** (`.teaagent/config.json` or `.teaagent/config.toml`)
4. **User config** (`~/.teaagent/config.json`)
5. **Hardcoded defaults** (lowest)

---

## Config File Format

### JSON (`.teaagent/config.json`)

```json
{
  "permission_mode": "prompt",
  "provider": "claude",
  "model": "claude-3-5-sonnet-latest",
  "max_iterations": 10,
  "max_tool_calls": 10,
  "code_analysis_enabled": false,
  "skill_search_dirs": [],
  "skill_source_profile": "default",
  "profiles": {
    "ci": {
      "permission_mode": "workspace-write",
      "provider": "claude",
      "model": "claude-3-5-haiku-latest"
    },
    "review": {
      "permission_mode": "read-only",
      "provider": "gpt",
      "model": "gpt-4o"
    }
  },
  "multi_sig": {
    "enabled": false,
    "required_approvals": 2,
    "peer_agent_ids": [],
    "peer_public_keys": {},
    "peer_relay_urls": {},
    "local_relay_base_url": "",
    "timeout_seconds": 300,
    "high_risk_patterns": ["/prod", "/production"],
    "allow_dev_signatures": false
  }
}
```

### TOML (`.teaagent/config.toml`)

TOML format requires the `config` extra (`pip install "teaagent[config]"`) or Python 3.11+.

```toml
permission_mode = "prompt"
provider = "claude"
model = "claude-3-5-sonnet-latest"
max_iterations = 10
max_tool_calls = 10
code_analysis_enabled = false

[profiles.ci]
permission_mode = "workspace-write"
provider = "claude"
model = "claude-3-5-haiku-latest"

[multi_sig]
enabled = false
required_approvals = 2
timeout_seconds = 300
high_risk_patterns = ["/prod", "/production"]
```

---

## Core Settings

| Key | Env Override | Type | Default | Description |
|-----|-------------|------|---------|-------------|
| `permission_mode` | `TEAAGENT_PERMISSION_MODE` | string | `"prompt"` | Tool execution permission level |
| `provider` | `TEAAGENT_PROVIDER` | string | — | LLM provider name |
| `model` | `TEAAGENT_MODEL` | string | — | Specific model override |
| `max_iterations` | `TEAAGENT_MAX_ITERATIONS` | int | `10` | Max agent loop iterations |
| `max_tool_calls` | `TEAAGENT_MAX_TOOL_CALLS` | int | `10` | Max tool calls per iteration |
| `code_analysis_enabled` | `TEAAGENT_CODE_ANALYSIS_ENABLED` | bool | `false` | Enable tree-sitter code analysis |
| `skill_search_dirs` | `TEAAGENT_SKILL_SEARCH_DIRS` | list | `[]` | Extra skill discovery directories |
| `skill_source_profile` | `TEAAGENT_SKILL_SOURCE_PROFILE` | string | `"default"` | Skill source profile |

---

## Permission Modes

| Mode | Value | Description |
|------|-------|-------------|
| Read-only | `read-only` | Blocks all destructive tools; safe for auditing |
| Workspace write | `workspace-write` | File writes allowed; shell mutations blocked |
| Prompt | `prompt` | Asks user approval for destructive actions |
| Allow | `allow` | Allows destructive tools for the session |
| Full access | `danger-full-access` | Unrestricted; use only in trusted automation |

---

## LLM Provider Settings

### Supported Providers

| Provider ID | API Key Env | Default Model | Base URL Env |
|-------------|------------|---------------|-------------|
| `claude` | `ANTHROPIC_API_KEY` | `claude-3-5-sonnet-latest` | `ANTHROPIC_BASE_URL` |
| `gpt` | `OPENAI_API_KEY` | `gpt-4o-mini` | `OPENAI_BASE_URL` |
| `gemini` | `GEMINI_API_KEY` | `gemini-1.5-flash` | `GEMINI_BASE_URL` |
| `openrouter` | `OPENROUTER_API_KEY` | `openai/gpt-4o-mini` | `OPENROUTER_BASE_URL` |
| `mistral` | `MISTRAL_API_KEY` | `mistral-large-latest` | `MISTRAL_BASE_URL` |
| `deepseek` | `DEEPSEEK_API_KEY` | `deepseek-chat` | `DEEPSEEK_BASE_URL` |
| `grok` | `XAI_API_KEY` | `grok-3-latest` | `XAI_BASE_URL` |
| `ollama` | `OLLAMA_API_KEY` (default: `ollama`) | `llama3.2` | `OLLAMA_BASE_URL` (`http://localhost:11434/v1`) |
| `vllm` | `VLLM_API_KEY` (default: `vllm`) | `meta-llama/Llama-3.1-8B-Instruct` | `VLLM_BASE_URL` (`http://localhost:8000/v1`) |
| `opencodezen-go` | `OPENCODEZEN_API_KEY` | `deepseek-v4-flash` | `OPENCODEZEN_BASE_URL` |
| `opencodezen` | `OPENCODEZEN_API_KEY` | `deepseek-v4-flash-free` | `OPENCODEZEN_COMPAT_BASE_URL` |
| `workers-ai` | `CLOUDFLARE_API_TOKEN` | `@cf/meta/llama-3.1-8b-instruct` | `WORKERS_AI_BASE_URL` |
| `aigateway` | `CLOUDFLARE_API_TOKEN` | `openai/gpt-4o-mini` | `AIGATEWAY_BASE_URL` |

### OpenRouter Additional Variables

| Variable | Description |
|----------|-------------|
| `OPENROUTER_HTTP_REFERER` | HTTP Referer header for usage attribution |
| `OPENROUTER_APP_TITLE` | App title header for usage attribution |

### Cloudflare Additional Variables

| Variable | Description |
|----------|-------------|
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account ID |
| `CLOUDFLARE_GATEWAY_ID` | AI Gateway ID |

---

## Network and TLS Settings

| Variable | Description |
|----------|-------------|
| `TEAAGENT_TLS_CLIENT_CERT` | Path to PEM-encoded TLS client certificate (mTLS) |
| `TEAAGENT_TLS_CLIENT_KEY` | Path to PEM-encoded TLS client private key (mTLS) |
| `REQUESTS_CA_BUNDLE` | Path to CA bundle for SSL verification |
| `SSL_CERT_FILE` | Alternative SSL certificate file path |

---

## Cost and Budget Settings

| Variable | Description |
|----------|-------------|
| `TEAAGENT_DAILY_COST_CAP_CENTS` | Daily spend cap in US cents. Agent pauses when exceeded. |
| `TEAAGENT_HEARTBEAT` | Heartbeat interval in seconds for budget polling |

---

## Operational Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `TEAAGENT_INTERACTIVE` | `1` | Set to `0` to suppress interactive prompts (CI mode) |
| `TEAAGENT_NO_SUMMARY` | `0` | Set to `1` to suppress end-of-run summary output |
| `TEAAGENT_QUIET` | — | Suppress non-essential output |
| `TEAAGENT_WORKER_ID` | — | Worker identifier for multi-worker deployments |
| `TEAAGENT_SANDBOX` | — | Sandbox mode selection |
| `TEAAGENT_CONTEXT_PROFILE` | — | Context profile for prompt injection |
| `TEAAGENT_PLUGINS_STRICT` | — | Enable strict plugin validation (fail on unknown plugins) |
| `TEAAGENT_STRICT_LOCAL` | — | Require all tool calls to be local-only |
| `TEAAGENT_WORKERS_AI_FORCE_JSON_OBJECT` | — | Set to `1` to force JSON object output for Workers AI |

---

## Security and Authentication Settings

| Variable | Description |
|----------|-------------|
| `TEAAGENT_MCP_TRUST_KEY` | Encryption key for MCP trust policies. Required when MCP trust is enabled. |
| `TEAAGENT_FEDERATED_SIGNATURE_TOKEN` | Token for federated signature verification |
| `TEAAGENT_RELAY_TOKEN_FILE` | Path to file containing relay authentication token |
| `TEAAGENT_RELAY_TOKEN` | Relay token value (alternative to file) |
| `TEAAGENT_SIGNATURE_RELAY_TOKEN` | Signature-specific relay token |
| `TEAAGENT_ALLOW_DEV_SIGNATURES` | Set to `1` to allow development signatures (never in production) |
| `TEAAGENT_APPROVAL_HMAC_KEY` | HMAC key for approval queue message signing |
| `GITHUB_TOKEN` or `GH_TOKEN` | GitHub API token for git operations |

---

## Automation and Webhook Settings

| Variable | Description |
|----------|-------------|
| `TEAAGENT_AUTOMATION_WEBHOOK_URL` | Webhook URL for automation delivery events |
| `TEAAGENT_AUTOMATION_WEBHOOK_SECRET` | HMAC secret for webhook payload authentication |

---

## Multi-Signature Quorum Configuration

Configure in `.teaagent/config.json` under the `multi_sig` key:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable multi-sig quorum for high-risk operations |
| `required_approvals` | int | `2` | Number of peer signatures required |
| `peer_agent_ids` | list[string] | `[]` | Agent IDs of authorized peers |
| `peer_public_keys` | dict[string, string] | `{}` | SSH public keys keyed by agent ID |
| `peer_relay_urls` | dict[string, string] | `{}` | Relay server URLs keyed by agent ID |
| `local_relay_base_url` | string | `""` | URL of this agent's relay endpoint |
| `timeout_seconds` | int | `300` | Approval request timeout |
| `high_risk_patterns` | list[string] | `[]` | File/path patterns that trigger quorum |
| `allow_dev_signatures` | bool | `false` | Accept dev signatures (never enable in production) |

---

## Audit Logging Configuration

Audit logging is always on. Behavior is controlled programmatically:

| Setting | Default | Description |
|---------|---------|-------------|
| Audit level | L2 | L0=off, L1=minimal, L2=standard, L3=verbose |
| Max string length | 20,000 chars | Truncation limit for logged values |
| Directory permissions | `0o700` | `.teaagent/` directory mode |
| File permissions | `0o600` | Audit file mode |
| Disk error cooldown | 30 seconds | Wait before retrying after disk write failure |

Sensitive patterns automatically redacted from audit logs: `api_key`, `authorization`, `credential`, `password`, `secret`, `token`, JWT patterns, AWS keys, GitHub tokens, Bearer tokens.

---

## Workspace Environment File (teaagent.toml)

Optional per-workspace environment spec for reproducible tooling:

```toml
[env]
python_version = "3.12"
type = "uv"
packages = [
  "ruff>=0.4",
  "mypy>=1,<3",
  "pytest>=7"
]
linters = ["ruff", "mypy"]
tools = ["git", "pytest"]
```

Supported environment types: `uv`, `nix`, `docker`.

---

## Profile Selection

Activate a named profile with `--profile <name>` or `TEAAGENT_CONTEXT_PROFILE`:

```bash
teaagent run "run linter" --profile ci
```

Profiles inherit all base config values and override only specified keys.

---

## See Also

- [Deployment Guide](deployment-guide.md)
- [Security Hardening](security-hardening.md)
- [Operations Manual](operations-manual.md)
