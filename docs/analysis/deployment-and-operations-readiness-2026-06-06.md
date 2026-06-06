---
type: analysis
audience: ops, sre, platform-engineering
status: complete
date: 2026-06-06
analyst: Claude Sonnet 4.6
evidence_basis: source code + docs (HEAD ad5e2d7)
---

# Deployment and Operations Readiness — teaAgent

> **One-line verdict:** teaAgent has unusually thorough ops *documentation* for a 0.1.0-alpha project, but most of that documentation describes manual workflows, shell-script workarounds, and aspirational deployment modes that are either untested in CI or explicitly excluded from coverage. An ops team that reads the docs and expects automated, monitored, HA production operations will be disappointed. An ops team that treats this as a single-instance developer tool with careful manual governance will find it workable.

---

## 1. Installation Assessment

### Mechanism
Standard Python package via `pip install teaagent`. Extras-based optional feature groups:

| Extra | Purpose | Required for |
|-------|---------|-------------|
| `tui` | `prompt-toolkit` | Interactive TUI |
| `code-analysis` | tree-sitter | AST code inspection |
| `graphqlite` | graphqlite + pysqlite3 | Code-index queries |
| `telemetry` | OpenTelemetry SDK | OTLP metrics/traces |
| `config` | `tomli` | TOML config on Python <3.11 |
| `oauth` / `audit-encryption` | `cryptography` | OAuth + audit HMAC |

`pyproject.toml:dependencies` is empty — the bare `pip install teaagent` installs **zero** runtime dependencies. Every functional component is opt-in. This is clean for library authors; it's a footgun for ops teams who install the base package and then discover TUI or audit encryption is missing at runtime.

### First-time install path
```bash
pip install "teaagent[tui,code-analysis,graphqlite,telemetry]"
teaagent setup --root . --provider claude --permission-mode prompt
teaagent doctor all
```

`teaagent doctor all` verifies provider reachability, config validity, git sandbox, and env order. This is good: a binary go/no-go check at the end of install.

### Documentation quality
`docs/ops/deployment-guide.md` is thorough — system requirements, install variants, workspace init, first-run checklist. A competent engineer can follow it without assistance.

### Gaps
- No published Docker image; users must build from the inline `Dockerfile` snippet in the deployment guide.
- No `brew install` / `winget` / `snap` distribution.
- No `pip install teaagent[all]` meta-extra; users must know which extras they need.
- `TOML config requires the config extra on Python <3.11` is documented but is a non-obvious failure mode (silent fallback to JSON parser failure rather than a clear error).
- macOS/Homebrew PEP 668 venv requirement is mentioned in `README.md` but not `deployment-guide.md`.

**Rating: 6/10.** Documented and functional for engineers; fragile for non-technical operators.

---

## 2. Configuration Audit

### Knob count
From `docs/ops/configuration-reference.md`, the full configuration surface is large:

| Category | Count |
|----------|-------|
| Core config keys (JSON/TOML) | 8 |
| Permission modes | 5 |
| LLM providers | 14 |
| Env vars (operational) | ~10 |
| Env vars (security/auth) | ~8 |
| Env vars (network/TLS) | 5 |
| Env vars (cost/budget) | 2 |
| Multi-sig quorum keys | 9 |
| Audit logging settings | 6 |

**Total configurable surface: ~65+ distinct settings.** Most have documented defaults; some do not.

### Priority hierarchy
5-level merge: CLI flags → env vars → workspace config → user config → hardcoded defaults. This is well-documented and standard. The actual merge logic is not immediately visible in a single source file — verify behavior empirically for edge cases.

### Sensible defaults
- `permission_mode: "prompt"` — correct; safe-first default.
- `max_iterations: 10`, `max_tool_calls: 10` — conservative, documented. Observed in `.teaagent/config.json` at HEAD.
- `code_analysis_enabled: false` — correct; requires optional extra.

### Dangerous misconfiguration states
| Setting | Bad value | Risk |
|---------|-----------|------|
| `permission_mode` | `danger-full-access` | Unrestricted tool execution |
| `multi_sig.allow_dev_signatures` | `true` | Bypasses cryptographic verification; documented as **never in production** |
| `TEAAGENT_ALLOW_DEV_SIGNATURES` | `1` | Same risk via env |
| `max_iterations` | Very high (e.g., 1000) | Runaway loop → cost spike |
| Missing `TEAAGENT_DAILY_COST_CAP_CENTS` | (not set) | Unlimited spend; no hard ceiling |

None of these bad states produce a startup error. `teaagent doctor all` does not check for `allow_dev_signatures` or missing cost cap. An operator could run in production with `danger-full-access` and no cost cap and receive no warning.

### Missing validation
- No schema validation of `config.json` at startup (discovered at runtime when a key is read).
- No lint command that checks the config file for dangerous combinations.
- `TEAAGENT_DAILY_COST_CAP_CENTS=0` semantics are "no spend allowed" — this is documented in code (`budget.py`) but not in the configuration reference.

**Rating: 5/10.** Comprehensive coverage; too many silent footguns; no config lint gate.

---

## 3. Deployment Patterns

### Pattern inventory and test status

| Pattern | Documentation | CI coverage | Assessment |
|---------|-------------|-------------|-----------|
| Developer workstation (interactive TUI) | Thorough | Yes (unit + acceptance) | **Well-tested** |
| One-shot CLI (`teaagent run`) | Thorough | Yes (acceptance P0/P1) | **Well-tested** |
| CI/headless (env var injection) | Thorough | Yes (CI workflow itself) | **Well-tested** |
| MCP server (`teaagent mcp serve`) | Documented | Partial (unit tests) | Aspirational |
| Automation webhook server | Documented | Partial (unit tests) | Aspirational |
| Docker one-shot | Inline Dockerfile snippet | `continue-on-error: true` | **Advisory only** |
| Docker daemon | Security-hardening doc | Not tested in CI | **Untested** |
| systemd unit | Operations manual | Not tested in CI | **Untested** |
| Kubernetes | Not documented | Not tested | **Not supported** |
| Multi-workspace gateway | Documented | Not verified at HEAD | Aspirational |
| OpenCode scheduler | cloud-deployment.md | Not in CI | External dependency |

The `docker-smoke` job in `.github/workflows/ci.yml` is marked `continue-on-error: true`, meaning Docker-based deployment is explicitly non-blocking. A Docker image build failure does not break the CI green state.

There are no Kubernetes manifests, Helm charts, or Terraform modules. The security-hardening doc mentions systemd unit configuration; there is no tested service file in the repo.

### Server mode maturity
`teaagent mcp serve` and `teaagent automation serve` are documented as production patterns but their CI test coverage is in unit tests, not integration tests against a live HTTP server. The MCP HTTP server advertises SSE streaming and `Mcp-Session-Id` protocol; session teardown behavior under process restart is undocumented.

**Rating: 4/10.** Developer-workstation and CI one-shot patterns are solid. Every "server" mode is aspirational.

---

## 4. Persistence Strategy

### Data inventory

| Data | Location | Criticality | Recovery if lost |
|------|---------|-------------|-----------------|
| Workspace config | `.teaagent/config.json` | High | Re-run `teaagent setup` |
| Global audit log | `.teaagent/audit.jsonl` | Critical | Restore from backup; partial loss from webhook sink |
| Per-run replay logs | `.teaagent/runs/<id>.jsonl` | High | Restore from backup |
| Session state | `.teaagent/sessions/` | Medium | Lost; resume from last checkpoint |
| Undo checkpoints | `.teaagent/undo/` | Medium | Lost; manual git revert |
| Plans | `.teaagent/plans/` | Low | Recreate manually |
| Pending approvals | `.teaagent/pending_approvals/` | Medium | Requests must be re-queued |
| MCP trust policies | `.teaagent/mcp-trust.json` | High | Re-configure |
| Workspace registry | `~/.teaagent/workspace_registry.json` | Low | Rebuild with `teaagent init` |
| Per-run HMAC keys | `~/.teaagent/run-keys/` | **Critical** | Unrecoverable; HMAC verification fails permanently |
| Relay tokens | `~/.teaagent/relay-tokens.json` | High | Re-authenticate |
| GraphQLite code index | `.teaagent/*.db` | Derived | Rebuild with `teaagent agent card --rebuild-index` |

### Audit log design
The audit log is an append-only JSONL file with per-event HMAC-SHA256 chaining and hash continuity. The implementation (`teaagent/schema_migration.py`, implied by `backup-and-recovery.md`) is sound:

- WAL-mode SQLite for the migration store (prevents corruption on crash).
- HMAC chain broken at event level; `teaagent audit verify` detects tampering.
- Sensitive values auto-redacted (API keys, JWTs, GitHub tokens, Bearer tokens).

### Critical gap: HMAC key backup
`~/.teaagent/run-keys/<run_id>.key` files are **created per run** and required for HMAC verification. They live in the user's home directory, not in the workspace. The backup documentation correctly flags this as Critical — but an ops team running the standard workspace backup script (`rsync .teaagent/`) will miss them because they are in `~/.teaagent/`, not `.teaagent/`. This is an easy miss.

### No native replication
There is no built-in database replication, WAL streaming, or distributed consensus. All persistence is single-host, single-file. For high-availability, the recommended approach is: continuous audit log shipping via webhook + S3 sync, and manual DR procedures. This is documented but requires external tooling.

### Backup strategy quality
`docs/ops/backup-and-recovery.md` covers:
- Daily rsync script with 30-day retention.
- Continuous audit log shipping (webhook, Filebeat, S3 sync).
- Git-based config backup.
- Monthly restore verification script.
- RTO/RPO targets (RPO ≤24h without continuous shipping, RPO ~seconds with webhook).

The documentation is thorough. The actual backup is user-implemented — there is no `teaagent backup` command.

**Rating: 6/10.** Sound HMAC audit design; good docs; no native backup tooling; run-key location is a real ops trap.

---

## 5. Operational Burden Estimate

### Routine tasks and frequency

| Task | Frequency | Command | Automated? |
|------|-----------|---------|-----------|
| Monitor approval queue | Continuous | `teaagent approval pending` | No — manual or cron |
| Cost report review | Daily | `teaagent cost cost_report --period today` | Cron script only |
| Audit log pruning | Weekly/monthly | `teaagent audit prune --older-than 90d` | Cron only |
| Per-run log pruning | Weekly | `find .teaagent/runs/ -mtime +30 -delete` | Cron only |
| Session cleanup | Weekly | `find .teaagent/sessions/ -mtime +7 -delete` | Cron only |
| Provider health check | Every 5min | `teaagent model smoke` | Cron only |
| Audit integrity verify | Daily | `teaagent audit verify` | Cron only |
| Backup verification | Monthly | Manual script | No |

### Approval queue is a blocking dependency
In `prompt` permission mode (the safe default), every destructive tool call enters an approval queue. If no human is watching (`teaagent approval pending`), the agent task stalls indefinitely. There is no configurable timeout-to-deny, no escalation, and no notification channel built into the CLI. The ops team must build the paging system themselves.

### No built-in metrics server
There is no Prometheus exporter, no `/metrics` endpoint, no StatsD sink. All observability flows through:
1. JSONL audit log grep/parse.
2. OpenTelemetry OTLP (requires `telemetry` extra + external collector).
3. Webhook events (requires `TEAAGENT_AUTOMATION_WEBHOOK_URL`).

The monitoring-and-alerting doc provides correct LogQL/OTLP guidance, but setting it up is a non-trivial ops project (deploy OTel collector → configure Grafana → write alert rules). Until that is done, monitoring is `grep '"cost_usd"' .teaagent/audit.jsonl`.

### Disk growth
The audit log (`audit.jsonl`) grows without bound. With 10 tool calls per run and 20 runs/day, it accumulates rapidly. The `teaagent audit prune` command exists but is not run automatically. No disk-space alert is built in; the monitoring doc suggests `df -h .teaagent/` via cron.

### Day-to-day burden estimate
For a team running teaAgent in CI-only mode: **low burden** (~15 min/week). For a team running it as an interactive server (MCP serve + automation serve): **medium-high burden** (~2-4 hrs/week) until proper monitoring and auto-pruning are configured.

**Rating: 4/10.** Everything that matters requires either manual action or a cron script. No auto-scaling, no self-healing, no built-in alerting.

---

## 6. Upgrade Safety Analysis

### Upgrade path
```bash
pip install --upgrade teaagent
teaagent doctor migration       # dry-run: shows pending schema migrations
teaagent doctor migration --apply   # applies pending migrations
teaagent doctor all             # verifies health post-upgrade
```

### Migration framework (verified in source)
`teaagent/schema_migration.py` implements:
- Versioned `SchemaMigration` dataclass (integer version, SQL).
- `SQLiteMigrationStore` with WAL mode, threading lock, TOCTOU-safe re-read under lock.
- `MigrationRunner.apply_pending()` with dry-run mode and WAL checkpoint post-apply.
- Automatic WAL cleanup after migration.

This is solid engineering for SQLite schema evolution.

### What the migration framework does NOT cover
- JSONL audit log format changes: no migration path. If the event schema changes, old events remain in the old format. Parsers must handle both versions.
- `config.json` schema changes: no migration. If a key is renamed or removed, old configs silently ignore the unknown key or fail at read time.
- Permission mode values: if a mode is renamed (e.g., `prompt` → `interactive`), old configs break silently.

### Backward compatibility guarantees
The package is `Development Status :: 3 - Alpha` (`pyproject.toml:classifiers`). No backward-compatibility guarantee is stated anywhere in the documentation. The CHANGELOG.md exists but its content was not reviewed in detail for explicit compat policy.

### CI upgrade testing
There is no CI job that installs a prior version, upgrades to HEAD, and verifies continued operation. The migration is tested at the unit level only.

### Risk during upgrade
- Low risk for SQLite-backed components (migration framework handles it).
- **Medium risk** for JSONL audit log format changes (none currently identified at HEAD, but no safeguard exists).
- **Medium risk** for config schema drift (silent ignoring of unknown keys could mask misconfiguration).
- **High risk** if upgrading across a permission-mode rename or behavioral change — no deprecation window documented.

**Rating: 5/10.** SQLite migration story is good; everything else relies on no-breaking-change discipline that has no enforcement mechanism.

---

## 7. Monitoring and Alerting Requirements

### What exists at HEAD

| Signal | Mechanism | Setup required |
|--------|-----------|---------------|
| Cost by run | `teaagent cost cost_report` | None (built-in) |
| Run status/failures | `teaagent agent runs` | None (built-in) |
| Approval backlog | `teaagent approval pending` | None (built-in) |
| Audit chain integrity | `teaagent audit verify` | None (built-in) |
| Provider reachability | `teaagent model smoke` | None (built-in) |
| OTLP traces + metrics | `telemetry` extra + OTLP endpoint | Medium setup |
| Webhook event stream | `TEAAGENT_AUTOMATION_WEBHOOK_URL` | Medium setup |
| Loki/Grafana log queries | File tail → Loki | High setup |

### SLOs documented (monitoring-and-alerting.md)

| SLI | SLO |
|-----|-----|
| Run success rate | ≥ 95% over 7 days |
| Approval response time | ≤ 5 min p95 |
| Provider availability | ≥ 99% over 24 h |
| Audit log integrity | 100% |
| Cost within cap | 100% compliance |

These SLOs are documented but not automatically measured. There is no built-in SLO dashboard or error budget tracking.

### Critical gap: no Prometheus exporter
Ops teams running modern observability stacks (Prometheus + Grafana, Datadog, New Relic) cannot scrape teaAgent directly. The OTLP path works for OpenTelemetry-native stacks but requires running an OTel collector. This is a real gap for teams not already running OTel infrastructure.

### Alert rules (documented as shell scripts)
The monitoring doc provides four shell-script alert implementations:
1. Cost alert (15-min cron, Slack webhook).
2. Audit integrity check (daily cron, email).
3. Provider health check (5-min cron, log append).
4. Approval backlog alert (cron, stdout).

These are functional but require the ops team to:
- Set up cron on each host.
- Maintain alert scripts separately from the application.
- Integrate Slack/PagerDuty/email notifications themselves.

There is no `teaagent alerts configure` command or alert-rule export in a standard format (e.g., Prometheus alert YAML, Grafana alert JSON).

**Rating: 4/10.** Observable if you invest in OTel or Loki; opaque without it. No Prometheus scrape endpoint. Alert setup is DIY.

---

## 8. Critical Assessment

### Would ops teams want to run this?

**Short answer:** Not without significant investment in surrounding tooling.

**The three operational nightmares:**

**Nightmare 1 — The invisible approval queue.**
In `prompt` mode, agent tasks silently stall if no human is watching. There is no built-in notification. The first time a critical CI task goes quiet because an approval was pending for 8 hours, ops will learn this the hard way. Mitigation requires building a webhook handler or polling script before go-live.

**Nightmare 2 — The missed run-key backup.**
`~/.teaagent/run-keys/` is a per-user home-directory path that is not under the workspace root. Every ops checklist and backup script that says "rsync the workspace" will miss it. When HMAC verification fails on an audit during a compliance review, tracing back to a missing run-key that was never backed up will be painful.

**Nightmare 3 — Disk growth with no auto-pruning.**
The audit log is append-only and grows without bound. In a high-throughput deployment (many CI runs per day), `.teaagent/audit.jsonl` can fill a disk within weeks. `teaagent audit prune` requires manual or cron invocation; there is no disk-watermark-based auto-pruning.

### Hidden complexity
- **14 LLM providers** with provider-specific env vars. A misconfigured base URL or wrong API key env var silently uses defaults; `teaagent doctor all` catches provider reachability but not mismatches between intended and actual provider.
- **Multi-sig quorum** requires running relay servers per peer agent. If a relay is down, the quorum request hangs for `timeout_seconds` (default: 300s). No documented fallback to single-approval in relay-down scenarios.
- **`directory-snapshot` isolation** has no OS-level process isolation (`security-hardening.md` documents this explicitly). Ops teams who enable it believing they have sandbox protection will be wrong.
- **Coverage omit list** (`pyproject.toml:tool.coverage.run.omit`) excludes `tui/`, `validation/`, `workflow_engine.py`, `tls_server.py`, `webhook_sink.py`, `wasm_runtime.py`, `wasm_skill.py`, and several CLI handlers. These excluded modules overlap significantly with the deployment patterns ops teams would actually use.

### What training ops teams need
1. Python packaging and virtualenv fundamentals (extras model, PEP 668).
2. JSONL/audit log structure and `teaagent audit` commands.
3. Cost cap configuration and runaway-loop recognition.
4. Approval queue monitoring and escalation (must build their own notification path).
5. Backup verification procedure (run-key location is counterintuitive).
6. OTel or Loki stack setup if real monitoring is required.

---

## 9. Ops Readiness Score

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Installation | 6/10 | Clean pip install; zero runtime deps by default is a footgun; no Docker image published |
| Configuration | 5/10 | Comprehensive but 65+ knobs; silent dangerous states; no config lint gate |
| Deployment patterns | 4/10 | Dev/CI patterns solid; all server modes aspirational; Docker non-blocking in CI |
| Data persistence | 6/10 | Sound HMAC audit design; run-key location trap; no native backup tooling |
| Operational burden | 4/10 | Everything critical requires manual action or cron; no auto-pruning; no built-in alerting |
| Upgrade safety | 5/10 | SQLite migrations solid; JSONL format + config schema have no migration path or compat guarantee |
| Monitoring & alerting | 4/10 | Observable via OTel/Loki but not out-of-box; no Prometheus endpoint; DIY alert scripts |
| **Overall** | **4.9/10** | Alpha-quality dev tool with production-quality governance *docs*; production *operations* require significant investment |

---

## 10. Recommendations for Production Hardening

### P0 — Before any production deployment

1. **Build and publish a Docker image.** Move the inline Dockerfile to a real `Dockerfile` at repo root, publish to a registry (GHCR or Docker Hub), and make the `docker-smoke` CI job blocking.

2. **Add a config lint gate.** Implement `teaagent config lint` that fails on: `danger-full-access` + no cost cap, `allow_dev_signatures=true`, unset `TEAAGENT_DAILY_COST_CAP_CENTS`. Run this in `governance-gate` CI.

3. **Fix the run-key backup gap.** Rename `~/.teaagent/run-keys/` to `.teaagent/run-keys/` (workspace-relative) OR add `teaagent backup` that automatically includes both directories and validates completeness.

4. **Build-in approval queue notification.** Add `TEAAGENT_APPROVAL_NOTIFY_URL` that fires a webhook when a new approval enters the queue. Without this, `prompt` mode is not safely deployable in automated or unattended contexts.

### P1 — Within 30 days of first production use

5. **Add auto-pruning.** Implement disk-watermark-based automatic pruning of run logs and old sessions. A `--max-disk-gb` flag on `teaagent mcp serve` / `teaagent automation serve` that self-manages growth.

6. **Add a Prometheus exporter.** Either a `/metrics` endpoint on the MCP/automation server or a standalone `teaagent metrics serve` command. This unblocks the most common ops monitoring stacks without requiring OTel.

7. **Publish a compatibility matrix.** For each minor version bump, document: which config keys changed, which JSONL event schemas changed, whether `teaagent doctor migration` is required. This is the single most important thing for safe upgrades.

8. **Add `teaagent approval timeout`** configuration. Allow operators to set a timeout after which a pending approval auto-denies (with audit log entry). This prevents indefinite stalls in automated pipelines.

### P2 — Before scaling beyond a single instance

9. **Add integration tests for server modes.** The MCP server and automation server need integration tests that spin up the HTTP listener and verify request/response against a real provider mock. These should be in CI and blocking.

10. **Document and test a supported upgrade path.** Add a CI job that installs the previous PyPI release, then upgrades to HEAD, runs `doctor migration --apply`, and verifies the test suite passes. This provides actual coverage for the upgrade story.

11. **Harden `directory-snapshot` visibility.** The documented warning log when `directory-snapshot` is selected should be promoted to a `teaagent doctor` check that actively fails if the selected isolation mode does not match the threat model (e.g., running as a server with `directory-snapshot`).

---

## Evidence Ledger

All findings above are traceable to the following sources:

| Finding | Source |
|---------|--------|
| Empty `dependencies` in pyproject.toml | `pyproject.toml:17` |
| Alpha classifier | `pyproject.toml:classifiers` |
| `docker-smoke: continue-on-error: true` | `.github/workflows/ci.yml:docker-smoke` |
| 65+ config knobs | `docs/ops/configuration-reference.md` |
| Run-keys in `~/.teaagent/run-keys/` | `docs/ops/backup-and-recovery.md:Audit HMAC Key Management` |
| Coverage omit list | `pyproject.toml:tool.coverage.run.omit` |
| Migration framework source | `teaagent/schema_migration.py` |
| SLOs documented | `docs/ops/monitoring-and-alerting.md:SLOs / SLIs` |
| Docker hardening flags | `docs/ops/security-hardening.md:docker — production isolation` |
| `allow_dev_signatures` warning | `docs/ops/security-hardening.md:Multi-Signature Quorum` |
| Approval queue management | `docs/ops/operations-manual.md:Daily Operations` |
| No Prometheus endpoint | `docs/ops/monitoring-and-alerting.md:What to Monitor` (absence) |

*Document generated from HEAD `ad5e2d7`, 2026-06-06.*
