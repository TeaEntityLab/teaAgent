# Trust and Audit Whitepaper

> **Last reviewed:** 2026-06-06
> **Audience:** Security reviewers, compliance leads, platform operators
> **Companion:** [Security Whitepaper (enterprise draft)](../security-whitepaper.md) — NIST mapping detail

TeaAgent is a **local-first governed agent harness**. It is not a hosted IDE
agent, not a cloud delegation service, and not a model provider. Its job is to
make tool use **inspectable, bounded, and recoverable** on your machine or CI
runner.

## What we guarantee (when configured correctly)

| Guarantee | Meaning | Verify |
| --- | --- | --- |
| Permission gates | Destructive tools are blocked or require explicit approval per mode. | `teaagent approval list --root .` |
| Append-only audit | Each run writes JSONL events under `.teaagent/runs/`. | `teaagent audit show <run_id> --root .` |
| Hash chain integrity | Events are linked; tampering is detectable. | `teaagent audit verify --root .` |
| Redacted payloads | Secrets in audit payloads are redacted by default (L2+). | `teaagent audit tail <run_id> --human --root .` |
| Hard budgets | Iterations, tool calls, and estimated cost can hard-stop a run. | Run with `--max-estimated-cost-cents N` |
| Undo / rollback | Path writes can be undone; git sandbox can roll back branches. | `teaagent agent undo --last --root .` |
| Run receipt | Human-readable summary of goal, tools, cost, latency, audit health. | `teaagent agent runs show <run_id> --receipt --root .` |

## Non-goals (explicit)

TeaAgent does **not** guarantee:

- **SOC 2 / ISO certification** — architecture supports evidence collection; certification is an organizational process.
- **Provider-side privacy** — model providers retain data per their account terms.
- **Encryption at rest for audit logs by default** — treat `.teaagent/` as sensitive; use OS permissions and disk encryption.
- **Multi-tenant SaaS isolation today** — local CLI and workspace-scoped storage are the supported deployment shape.
- **Automatic malware detection in plugins** — plugins are supply-chain inputs; governance lint blocks schema/annotation errors, not malicious code review.
- **Perfect prompt-injection immunity** — untrusted content is labeled; operators must scope tools and approvals. See [prompt-injection trust boundaries](prompt-injection-trust-boundaries.md).

## Failure behavior

### Audit disk write failure

| Mode | Behavior |
| --- | --- |
| Default | Run continues in memory; `_disk_write_error` events recorded; cooldown suppresses further disk writes. |
| `TEAAGENT_COMPLIANCE_MODE=1` | Run stops with `AuditDurabilityError` — fail closed for regulated workflows. |

```bash
export TEAAGENT_COMPLIANCE_MODE=1
teaagent run "task" --permission-mode read-only --root .
# Disk failure → run aborts (see tests/test_ws3_compliance_audit.py)
```

### Strict audit chain verification

Legacy logs without chain metadata remain readable. New runs use chained events.
Strict verification can reject mixed or tampered logs:

```bash
export TEAAGENT_STRICT_AUDIT_CHAIN=1
teaagent audit verify --root .
```

### Approval and subagent queues

Destructive subagent tools use durable file-backed queues (default) or a remote
backend stub. Pending items expose queue depth and age:

```bash
teaagent approval pending --root .
teaagent approval subagents list --human --root .
```

## Verification commands (operator checklist)

Run after setup or before claiming governance in production:

```bash
# Workspace readiness
teaagent doctor config-lint --root .

# Audit chain on existing runs
teaagent audit verify --root .

# Compliance bundle export (signed digest)
teaagent audit export --audit-log <run_id> --output /tmp/bundle.json --root .

# Observability on a completed run
teaagent audit tail <run_id> --human --limit 20 --root .

# Cost / audit health on receipt (after any run)
teaagent agent runs show <run_id> --receipt --root .
```

Automated regression:

```bash
python3 -m pytest tests/test_ws3_compliance_audit.py tests/test_ws3_strict_audit_chain.py -q
python3 -m pytest tests/test_ws4_observability.py -q
```

## Trust boundaries summary

```
User task → Harness (TeaAgent) → ToolRegistry + ApprovalPolicy → Workspace tools
                ↓
         AuditLogger (JSONL + chain)
                ↓
         Run receipt / compliance export
```

- **Trusted:** harness code you install, workspace config you write, grants you approve.
- **Untrusted until reviewed:** remote MCP servers, third-party plugins, pasted user content in prompts.
- **External:** LLM provider APIs (data handling = provider terms).

## Related documents

- [Integration contracts](integration-contracts.md) — WS5 run/event/approval/storage boundaries
- [Cost state taxonomy](cost-state-taxonomy.md) — receipt cost labels
- [Permission and approval playbook](../permission-and-approval-playbook.md)
- [Audit events reference](../audit-events.md)
