# Compliance Checklist

This document defines the gates that must pass for a release or a deployment to be considered compliant. It is the operational companion to the [Release Process](release-process.md).

---

## Release compliance gates

### Gate 1 — Automated CI (all must be green)

| Check | Job | Command |
|---|---|---|
| Lint (ruff + mypy + format) | `lint` | `ruff check . && ruff format --check . && mypy teaagent/` |
| Unit tests ≥ 75% coverage (3.10–3.12) | `test` | `pytest --cov-fail-under=75` |
| Telemetry tests | `test-telemetry` | `pytest tests/test_telemetry.py` |
| Governance fuzz | `governance-gate` | `pytest tests/test_governance_fuzz.py` |
| Approval queue integration | `governance-gate` | `pytest tests/test_tranche_bc_governance.py tests/test_subagent_approval_queue_integration.py` |
| Security selftest | `governance-gate` | `teaagent selftest --root .` |
| Tool lint | `governance-gate` | `teaagent tool lint --root .` |
| Permission matrix | `governance-gate` | `pytest tests/policy/test_permission_matrix.py` |
| Phase 4–5 acceptance | `governance-gate` | `pytest tests/acceptance/test_consensus_flow.py tests/acceptance/test_sandbox_enhancement_flow.py` |
| Adversarial governance | `governance-gate` | `pytest tests/test_governance_adversarial_runtime.py` |
| Acceptance P0 | `acceptance-p0` | `python3 scripts/run_acceptance_tier.py --tier p0` |
| Acceptance P1 | `acceptance-p1` | `python3 scripts/run_acceptance_tier.py --tier p1` |
| Acceptance all (main only) | `acceptance-all` | `python3 scripts/run_acceptance_tier.py --tier all` |
| Package build + twine check | `package` | `python -m build && twine check dist/*` |
| Dependency CVE scan (base) | `pip-audit` | `uv export --format requirements-txt --no-dev --no-emit-project --frozen -o /tmp/teaagent-base-requirements.txt && pip-audit -r /tmp/teaagent-base-requirements.txt` |
| Dependency CVE scan (dev/lockfile weekly) | `pip-audit` | `uv export --format requirements-txt --no-emit-project --frozen -o /tmp/teaagent-dev-requirements.txt && pip-audit -r /tmp/teaagent-dev-requirements.txt` |
| Dependency CVE scan (optional extras) | `optional-extra-pip-audit` | `uv export --format requirements-txt --extra <extra> --no-dev --no-emit-project --frozen -o /tmp/teaagent-<extra>-requirements.txt && pip-audit -r /tmp/teaagent-<extra>-requirements.txt` |
| CodeQL Python | `codeql` | GitHub-managed |
| Docs consistency | `use-case-matrix` | `python3 scripts/validate_docs_consistency.py` |

**Decision: if any gate fails, do not proceed to tagging.**

### Gate 2 — Manual pre-release checks (maintainer)

- [ ] `docs/acceptance.md` count matches `pytest tests/acceptance --collect-only -q` output.
- [ ] `CHANGELOG.md` `## Unreleased` entries are moved to a versioned section with today's date.
- [ ] `pyproject.toml` `version` matches the intended tag.
- [ ] No entry in `## Unreleased` is a `### Breaking` change without a migration note.
- [ ] Dependabot alerts: zero open alerts with a CVSS score ≥ 7.0. Lower-severity open alerts are acknowledged.
- [ ] `pip-audit` shows zero CVEs in the base export.
- [ ] Dev/lockfile and optional-extra audit findings are reviewed according to
      [Dependency Audit Policy](../security/dependency-audit-policy.md).
- [ ] For MAJOR releases: the ADR that describes the breaking change is in `docs/adr/` and its status is **Accepted**.

### Gate 3 — Security review (security fixes and major releases)

Required when: the release includes a `### Security` changelog entry, or it is a MAJOR release.

- [ ] Two reviewers have approved the relevant commits (see [code-review-checklist.md](code-review-checklist.md)).
- [ ] The vulnerability was reported and fixed according to the disclosure process in `SECURITY.md`.
- [ ] The `### Security` changelog entry includes the affected component, the class of vulnerability, and the fix summary.
- [ ] If a CVE is assigned, it is referenced in the changelog.

### Gate 4 — Tag and publish

```bash
git tag -s v{VERSION} -m "Release v{VERSION}"
git push origin main --tags
```

The `release.yml` CI workflow handles:
- Wheel and sdist build
- `twine check`
- PyPI publish (OIDC, no stored API key)
- Build provenance attestation

After the workflow completes:
- [ ] PyPI release page is visible and `pip install teaagent=={VERSION}` succeeds.
- [ ] GitHub Release is created with the changelog section as the body.
- [ ] Build attestation is verifiable: `gh attestation verify dist/*.whl --repo TeaEntityLab/teaAgent`.

---

## Deployment compliance gates

For deployments of the MCP HTTP server or agent loop in a non-local environment:

### Network security

- [ ] Server is not bound to `0.0.0.0` without `--auth-token` or `--oauth-issuer`.
- [ ] TLS is terminated at a reverse proxy (nginx, Caddy, Cloudflare Tunnel) in front of the MCP HTTP server.
- [ ] `--allowed-origin` is set to the expected client origin(s).

### Secret management

- [ ] LLM API keys are injected via environment variables, not CLI flags.
- [ ] `--auth-token` / `--oauth-signing-key` (if used) are injected from a secrets manager, not hardcoded.

### Audit log retention

- [ ] Audit JSONL files have mode `0600` and are written to a path only accessible to the agent process user.
- [ ] Log rotation is configured externally (the harness does not self-rotate).
- [ ] Retention period is defined and documented (no default — operator must set this).

### Workspace isolation

- [ ] Each concurrent agent worker has its own `--root` workspace path.
- [ ] Cross-host NFS/SMB mounts are not used for workspace roots (advisory locks are local-only).

---

## Audit trail access and retention

| Who can access audit logs | Conditions |
|---|---|
| Agent process user | Always — logs are written by the process |
| Human operator | Read via `teaagent audit list` / `teaagent audit show` |
| Automated log aggregator | If configured by the operator; logs are plain JSONL |

Retention policy is **operator-defined**. The harness provides `teaagent audit prune` for manual lifecycle management. For production deployments, configure external log rotation (e.g. `logrotate`) targeting the audit directory.

Audit logs must not be deleted during an active incident or investigation. Operators are responsible for preserving logs for any regulatory or contractual retention period that applies to their deployment.

---

## Data governance

| Data category | Where stored | Retention | Deletion procedure |
|---|---|---|---|
| Audit events | `{workspace}/.teaagent/audit/*.jsonl` | Operator-defined | `teaagent audit prune` or direct file deletion |
| Agent run state | `{workspace}/.teaagent/runs/*.json` | Operator-defined | Direct file deletion |
| Memory catalog | `{workspace}/.teaagent/memory.jsonl` | Indefinite (user data) | Direct file deletion |
| OAuth client secrets | `{workspace}/.teaagent/oauth_store.db` (SQLite) | Until client revoked | `teaagent oauth revoke <client_id>` or DB deletion |
| Approval queue | `{workspace}/.teaagent/approval_queue.json` | Until run complete | Automatic on run completion |
| LLM request/response | Not persisted by default | N/A | N/A |

LLM API keys and tokens are never written to disk by the harness. If a deployment writes LLM responses to disk for evaluation or debugging, the operator is responsible for classifying and protecting that data.

---

## Sign-off summary

| Gate | Who signs off |
|---|---|
| All CI green | Automated (CI status on PR) |
| Docs / changelog / version | PR author + reviewer |
| Security review (if applicable) | Two reviewers with security background |
| Release tag | Maintainer (GPG-signed tag) |
| Post-publish verification | Maintainer (PyPI + attestation check) |
