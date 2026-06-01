# TeaAgent Operations Documentation

This directory contains all operations, deployment, and runbook documentation for teaagent.

---

## Documents

| Document | Description |
|----------|-------------|
| [Deployment Guide](deployment-guide.md) | System requirements, installation, workspace initialization, first-run checklist, deployment patterns |
| [Configuration Reference](configuration-reference.md) | All environment variables, config file schema, permission modes, provider settings, multi-sig quorum |
| [Operations Manual](operations-manual.md) | Startup/shutdown procedures, daily operations, log aggregation, maintenance tasks |
| [Runbooks](runbooks.md) | Step-by-step incident procedures for emergency pause, cost breach, audit corruption, timeouts, disk full, and more |
| [Troubleshooting Guide](troubleshooting.md) | Diagnostics and fixes for cost tracking wrong, undo failures, TUI frozen, agent crashes, provider unreachable |
| [Monitoring and Alerting](monitoring-and-alerting.md) | Metrics to track, alert thresholds, OpenTelemetry setup, Grafana queries, SLOs |
| [Backup and Recovery](backup-and-recovery.md) | Backup strategy, audit log shipping, disaster recovery procedures, RTO/RPO targets |
| [Performance Tuning](performance-tuning.md) | Capacity planning, model selection, context optimization, local providers, profiling |
| [Security Hardening](security-hardening.md) | Deployment checklist, secret management, audit log protection, network isolation, multi-sig |

---

## Quick Reference

### First-time setup

```bash
pip install "teaagent[tui,code-analysis]"
cd /path/to/project
teaagent setup
export ANTHROPIC_API_KEY="sk-ant-..."
teaagent doctor all
```

### Key file locations

| Path | Purpose |
|------|---------|
| `.teaagent/config.json` | Workspace configuration |
| `.teaagent/audit.jsonl` | Immutable audit trail |
| `.teaagent/runs/` | Per-run replay logs |
| `~/.teaagent/tui_state.json` | TUI state (user home) |

### Emergency stop

```bash
teaagent automation pause --all
# or: kill -TERM $(pgrep -f teaagent)
```

### Undo last agent action

```bash
teaagent agent undo --last
```

### Health check

```bash
teaagent doctor all
teaagent audit verify
teaagent model smoke
```

---

## Runbook Index

| ID | Scenario | Severity |
|----|----------|----------|
| [RB-01](runbooks.md#rb-01-emergency-pause--resume) | Emergency pause / resume | Any |
| [RB-02](runbooks.md#rb-02-cost-limit-breach) | Cost limit breach | High |
| [RB-03](runbooks.md#rb-03-audit-log-corruption-detected) | Audit log corruption | Critical |
| [RB-04](runbooks.md#rb-04-agent-timeout) | Agent timeout / hung | Medium |
| [RB-05](runbooks.md#rb-05-approval-backlog) | Approval backlog | Medium |
| [RB-06](runbooks.md#rb-06-disk-full) | Disk full | High |
| [RB-07](runbooks.md#rb-07-undo--rollback-agent-changes) | Undo / rollback changes | Any |
| [RB-08](runbooks.md#rb-08-llm-provider-outage) | LLM provider outage | High |
| [RB-09](runbooks.md#rb-09-mcp-trust-policy-failure) | MCP trust policy failure | Medium |

---

## See Also

- [User Guide](../tui-daily-driver-guide.md) — day-to-day usage for developers
- [TUI Chat Reference](../tui-chat-reference.md) — TUI keyboard shortcuts and commands
- [Agent Mode Operator Guide](../agent-mode-operator-guide.md) — operator-level agent configuration
- [Permission and Approval Playbook](../permission-and-approval-playbook.md) — approval policy patterns
- [Operator Trust Model](../operator-trust-model.md) — trust model and security boundaries
