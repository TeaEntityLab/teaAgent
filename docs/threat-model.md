# TeaAgent Threat Model

Last updated: 2026-05-28

This document maps threats to mitigations and verification. It complements [tool-authoring.md](tool-authoring.md) and [architecture.md](architecture.md).

| Threat | Impact | Mitigation (current) | Verification | Gap / notes |
|--------|--------|----------------------|--------------|-------------|
| Prompt injection causing destructive tools | High | Permission modes; `ApprovalPolicy`; policy-as-code deny rules | `test_policy_as_code_flow.py`, `tests/policy/test_permission_matrix.py` | Model may still *request* bad tools; harness blocks execution |
| Mislabelled tool annotations (`read_only` on write tool) | High | `teaagent tool lint`; runtime policy on destructive flag | `tests/test_tranche_b_governance.py` | Plugin handlers not sandboxed by default — trust boundary |
| Path traversal / symlink escape | High | Workspace path resolution; protected paths | `test_contract_policy.py`, `test_protected_paths_flow.py` | Fuzz coverage ongoing |
| Shell mutation in workspace-write mode | High | `ApprovalPolicy` blocks non-file destructive tools in workspace-write | `tests/policy/test_permission_matrix.py` | Dangerous flag lists in shell classifier — maintain with tests |
| Secret leakage in audit logs | Medium | Audit redaction keys and truncation | `test_audit_chain_integrity_flow.py` | Over-redaction reduces debuggability — export tiers future work |
| Audit log tampering | Medium | Hash chain (`audit verify`); fsync | `test_audit_chain_integrity_flow.py` | Local-only unless signed export |
| Plugin supply-chain execution | High | Plugin verify/install gates; entry-point audit | `test_plugin_install_security_flow.py` | Capability manifest formalization in progress |
| MCP server tool explosion / exfiltration | High | MCP tool filter hook; HTTP auth for remote MCP | `test_remote_mcp_consumption_flow.py` | MCP trust CLI planned (Phase 5) |
| Memory poisoning / failure-card bias | Medium | Failure cards; warning injection | `test_memory_auto_curation_flow.py` | TTL/confidence schema not yet enforced |
| Subagent privilege escalation | High | Subagent defs; lineage; isolation modes | `test_subagent_lineage_flow.py`, worktree/container isolation flows | Tournament approval lineage — Foundation |
| Parallel branch contamination | Medium | Git sandbox branches; worktree isolation | `test_subagent_worktree_isolation_flow.py` | Main-branch write blocked in tournament — verify per release |
| Provider response schema drift | Low | JSON schema for model decisions | `test_live_provider_conformance_flow.py` | Provider-specific quirks remain |
| Unbounded run cost | Medium | `RunBudget`; iteration/tool/cost caps | `test_p0_harness.py`, `test_p0_slo_flow.py` | User must configure caps |

## Trust Boundaries

```text
Trusted:   TeaAgent harness (Runner, Policy, Audit, built-in workspace tools)
Reviewed:  Project plugins, MCP servers, skills (manifest + human enable)
Untrusted: Model output, external MCP payloads, arbitrary plugin handlers
```

## Operator Checklist (High-Risk Repos)

1. Start with `--permission-mode read-only`.
2. Run `teaagent tool lint` after adding plugins.
3. Use `--require-plan` + `--from-plan` for writes.
4. Never use `danger-full-access` outside an isolated sandbox.
5. Review `teaagent runs export <run_id>` after each autonomous edit session.
