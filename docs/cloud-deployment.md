---
type: documentation
audience: operator, agent
status: draft
version: 1.0.0
last_audit: 2026-06-01
---
# Cloud / Background Deployment Guide

## Overview

TeaAgent supports three deployment models beyond the interactive CLI/TUI session:

| Model | Trigger | Persistence | Best for |
|-------|---------|-------------|----------|
| **CLI background run** | `teaagent agent run --background` | `.teaagent/runs/` JSONL | Long-running local tasks, cron |
| **MCP HTTP server** | `teaagent mcp serve --http` | In-process audit log | IDE integration, CI/CD pipelines |
| **OpenCode scheduler** | `opencode schedule` | OpenCode run store | Periodic audits, daily reviews |

This guide covers operational patterns, security hardening, and CI/CD integration.

## Deployment Models

### CLI Background Runs

Background runs fork the agent process without TUI attachment. Results are persisted to
the run store and can be inspected later.

```bash
# Start a background task
teaagent agent run gpt "run the full test suite and report failures" \
  --permission-mode read-only \
  --background \
  --root /path/to/repo

# List running and completed background tasks
teaagent agent runs --root /path/to/repo

# Check status (liveness via heartbeat audit events)
teaagent agent status <run_id> --root /path/to/repo

# Read results
teaagent agent show <run_id> --root /path/to/repo
```

Background runs emit heartbeat audit events at the interval set by `--heartbeat N`
(default: 30s). Observers can confirm liveness by polling `agent status`.

#### Background Run Store

Background metadata is managed by `BackgroundRunStore` and `UltraworkStore`:

```bash
# List background runs managed by the store
python3 -c "
from teaagent.ergonomics.background_run import BackgroundRunStore
store = BackgroundRunStore()
for r in store.list():
    print(r['background_id'], r['status'], r['command'])
"
```

### MCP HTTP Server Mode

Expose workspace tools over Streamable HTTP for remote clients:

```bash
# Serve on loopback (dev / local IDE)
teaagent mcp serve --http --port 7330 --auth-token "$MCP_TOKEN" --root /path/to/repo

# Serve on a specific interface (container / VM)
teaagent mcp serve --http --port 7330 --auth-token "$MCP_TOKEN" \
  --host 0.0.0.0 \
  --allowed-origin https://my-ide.internal \
  --root /path/to/repo
```

Transport details:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /mcp` | POST + JSON-RPC | Standard MCP request/response |
| `GET /mcp` | SSE stream | Server-push notifications |
| `DELETE /mcp` | DELETE | Session teardown |

`initialize` issues a `Mcp-Session-Id` header; every subsequent request must echo it.
`Mcp-Session-Id` is **not** a bearer credential — use `--auth-token` (Bearer header)
for authentication.

### Periodic / Scheduled Runs (OpenCode Scheduler)

Use `opencode schedule` for cron-like agent runs. This is the preferred path for recurring
tasks that need the full agent execution loop (tool calls, audit, budget enforcement).

#### Daily Code Review

```bash
# Schedule a daily code review against the latest commits
opencode schedule \
  --name "teaagent-daily-review" \
  --schedule "0 8 * * 1-5" \
  --prompt "Review all changes from the last 24 hours in /path/to/repo.
    Run: teaagent agent run gpt 'review all files changed in the last 24 hours for bugs,
    security issues, and style violations' --permission-mode read-only --root /path/to/repo"
```

#### Weekly Security Audit

```bash
opencode schedule \
  --name "teaagent-weekly-security" \
  --schedule "0 9 * * 1" \
  --prompt "Run a security audit:
    teaagent agent run claude 'audit the codebase for OWASP top-10 vulnerabilities:
    check for hardcoded secrets, SQL injection, XSS vectors, and insecure deserialization'
    --permission-mode read-only --root /path/to/repo"
```

#### Viewing Scheduled Runs

```bash
opencode schedule list
opencode job-logs teaagent-daily-review
```

### CI/CD Integration

#### GitHub Actions: Automated PR Review

```yaml
# .github/workflows/teaagent-pr-review.yml
name: TeaAgent PR Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install TeaAgent
        run: pip install -e .

      - name: Run TeaAgent PR review
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          MCP_TOKEN: ${{ secrets.TEAAGENT_MCP_TOKEN }}
        run: |
          teaagent agent run gpt \
            "Review this PR diff for bugs, security issues, and style violations. \
             Base: ${{ github.event.pull_request.base.sha }} \
             Head: ${{ github.event.pull_request.head.sha }}" \
            --permission-mode read-only \
            --root .
```

#### GitLab CI: Automated Fix PR

```yaml
# .gitlab-ci.yml
teaagent-auto-fix:
  image: python:3.11
  stage: test
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
  script:
    - pip install -e .
    - |
      teaagent agent run gpt \
        "Fix all failing tests in this repository. \
         Run the test suite first, then apply minimal fixes." \
        --permission-mode workspace-write \
        --root .
    - |
      if ! git diff --quiet; then
        git config user.email "teaagent@ci.local"
        git config user.name "TeaAgent CI"
        git checkout -b auto-fix/$CI_PIPELINE_ID
        git add -A
        git commit -m "auto: fix failing tests"
        git push origin auto-fix/$CI_PIPELINE_ID \
          -o merge_request.create \
          -o merge_request.title="Auto-fix: failing tests"
      fi
  variables:
    OPENAI_API_KEY: $OPENAI_API_KEY
```

## Security Considerations

### MCP Auth Tokens

- Always use `--auth-token` in production. The token is validated via `Authorization: Bearer <token>`.
- Rotate tokens regularly. Store them in CI secrets, not in repository config.
- Use different tokens per environment (dev, staging, prod).

```bash
# Generate a strong random token
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Network Binding

| Environment | Binding | Rationale |
|-------------|---------|-----------|
| Dev / local IDE | `127.0.0.1` (default) | Loopback-only, no external exposure |
| Container / VM | `0.0.0.0` + `--allowed-origin` | Behind reverse proxy or firewall |
| Production | Reverse proxy (nginx, Caddy) | TLS termination, rate limiting, access logs |

Production reverse proxy example (nginx):

```nginx
server {
    listen 443 ssl;
    server_name teaagent.internal;

    ssl_certificate     /etc/ssl/teaagent.crt;
    ssl_certificate_key /etc/ssl/teaagent.key;

    location /mcp {
        proxy_pass http://127.0.0.1:7330;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400s;  # long-lived SSE
    }
}
```

### Audit Log Retention

- Run audit logs live under `.teaagent/runs/<run_id>.jsonl`.
- Archive completed runs periodically to prevent disk pressure.
- Use `teaagent agent show <run_id>` or direct JSONL reads for forensics.

```bash
# Archive runs older than 30 days
find .teaagent/runs -name '*.jsonl' -mtime +30 -exec gzip {} \;
```

### Provider Key Management

- Never commit provider keys to the repository.
- Use CI secrets for automated runs.
- Use `--write-env` with `teaagent setup` to persist project-local overrides.
- Prefer the lazy setup flow: `~/.teaagent/providers_env.zsh` sourced from shell profile.

## Examples

### GitHub Action: Automated PR Review

See the full workflow in [CI/CD Integration](#cicd-integration) above.

### Daily Security Audit via Cron

```bash
# Add to crontab (runs every weekday at 9 AM)
0 9 * * 1-5 cd /path/to/repo && \
  teaagent agent run gpt \
    "Audit all changes since yesterday for security issues: \
     hardcoded secrets, injection vectors, unsafe deserialization, \
     and missing input validation" \
    --permission-mode read-only \
    --root . \
    --background
```

### On-Demand Compliance Report

```bash
teaagent agent run claude \
  "Generate a SOC 2 compliance report for this codebase. \
   Check for: audit logging completeness, PII handling, \
   encryption at rest/in transit, access control patterns, \
   and dependency supply chain risks." \
  --permission-mode read-only \
  --root . \
  --context-profile deep
```

## Troubleshooting

### Background run appears stuck

```bash
# Check heartbeat events
teaagent agent status <run_id> --root .

# Inspect raw audit log
cat .teaagent/runs/<run_id>.jsonl | python3 -m json.tool | grep heartbeat

# If dead, resume from last checkpoint
teaagent agent resume gpt <run_id> --root .
```

### MCP HTTP server not reachable

```bash
# Verify binding
lsof -i :7330

# Test connectivity
curl -X POST http://127.0.0.1:7330/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1}'
```

### Scheduled run not firing

```bash
# List scheduled jobs
opencode schedule list

# Check job logs
opencode job-logs teaagent-daily-review

# Run immediately for testing
opencode schedule run teaagent-daily-review
```
