# Governance Index

This directory contains the authoritative standards and process documentation for TeaAgent. All documents are grounded in the actual project configuration (`pyproject.toml`, `ruff.toml`, `.github/workflows/`, `SECURITY.md`).

---

## Documents

| Document | Covers |
|---|---|
| [standards.md](standards.md) | Design principles, governance philosophy, code style, naming, type hints, docstrings, documentation standards, quality thresholds |
| [contributing.md](contributing.md) | Branch workflow, commit format, PR requirements, breaking-change process, RFC process |
| [code-review-checklist.md](code-review-checklist.md) | Item-by-item reviewer checklist: correctness, security, governance, quality, tests, docs |
| [security-standards.md](security-standards.md) | Credential handling, path confinement, shell safety, injection prevention, approval gating, MCP security, dependency auditing |
| [testing-standards.md](testing-standards.md) | Test layout, naming convention, coverage requirements, unit/integration/acceptance/property test rules, mocking rules |
| [release-process.md](release-process.md) | Versioning, changelog format, pre-release checklist, tag/publish procedure, hotfix process, deprecation policy |
| [compliance-checklist.md](compliance-checklist.md) | Release gates, deployment gates, sign-off requirements, audit trail access, data governance |
| [document-state-model.md](document-state-model.md) | Canonical states for findings, risks, issues, roadmap items, and archived docs |
| [risk-issue-roadmap-workflow.md](risk-issue-roadmap-workflow.md) | Pipeline from finding capture to ticketing, roadmap, verification, and supersession |
| [doc-taxonomy-and-ownership.md](doc-taxonomy-and-ownership.md) | Document types, source-of-truth rules, and default owner surfaces |
| [doc-maintenance-policy-2026-06-02.md](doc-maintenance-policy-2026-06-02.md) | Short entry point for keeping the daily-driver doc corpus useful |
| [evidence-to-principle-policy.md](evidence-to-principle-policy.md) | How to turn repository evidence into durable principles and roadmap rationale |
| [documentation-operating-model-2026-06-04.md](documentation-operating-model-2026-06-04.md) | Claim classes, evidence hierarchy, freshness windows, guarded claims, and documentation definition of done |

For the threat model and permission mode table, see [SECURITY.md](../../SECURITY.md).  
For architecture decisions, see [docs/adr/](../adr/).  
For the existing skill governance process, see [docs/skill-governance.md](../skill-governance.md).
For the curated documentation front door, see [docs/INDEX.md](../INDEX.md).

---

## Decision trees

### "I want to make a code change — what do I need?"

```
Does the change touch tool schemas, audit event shapes,
permission modes, or any protocol wire format?
│
├── Yes → Is it additive only (new field, new mode)?
│         ├── Yes → Still needs an ADR. Create one first.
│         └── No (removes or changes existing) → MAJOR bump + ADR + 2 reviewers.
│
└── No → Is it a bug fix?
          ├── Yes → PR with test, 1 reviewer, PATCH bump at release.
          └── No (new feature) → PR with test, 1 reviewer, MINOR bump at release.

In all cases: ruff + mypy + pytest must pass before merge.
```

---

### "I found a security issue — what do I do?"

```
Is it a vulnerability in TeaAgent's harness logic,
tool governance, sandbox escape, or auth bypass?
│
├── Yes → Do NOT open a public GitHub issue.
│         Report privately to maintainers (see SECURITY.md).
│         Fix branch: security/<slug> from main.
│         Requires 2 reviewer approvals before merge.
│         Add ### Security entry to CHANGELOG.md.
│
└── No (upstream dep, Python stdlib, OS, LLM provider)
      → Open a public issue referencing the upstream advisory.
        Add pip-audit constraint to pyproject.toml if actionable.
```

---

### "I want to release a new version — what must pass?"

```
1. All blocking CI jobs green on main
   (lint, test ×3, telemetry, governance-gate, acceptance p0/p1/all, package, pip-audit, codeql)

2. Manual checks
   ├── docs/acceptance.md count matches --collect-only
   ├── CHANGELOG.md ## Unreleased promoted to [VERSION] — DATE
   ├── pyproject.toml version updated
   └── Zero Dependabot alerts CVSS ≥ 7.0

3. Security changelog entry? → 2 reviewer approvals required.
   MAJOR bump? → ADR must be Accepted status.

4. git tag -s vX.Y.Z && git push --tags
   → release.yml builds, publishes to PyPI, attests provenance.

5. Post-publish
   ├── pip install teaagent==X.Y.Z succeeds
   ├── GitHub Release created with changelog body
   └── gh attestation verify passes
```

---

### "Should this go in a comment, a docstring, or nowhere?"

```
Is the WHY non-obvious?
(hidden constraint, subtle invariant, workaround for a specific bug,
 behaviour that would surprise a competent reader)
│
├── Yes → Write a short comment (1 line preferred, 2 max).
│         Do NOT reference the ticket, task, or caller.
│
└── No → Write nothing. The code names explain the what.
          If you feel the need to explain what the code does,
          rename the identifiers instead.

Is this a public class?
├── Yes → One-line docstring stating the invariant or purpose.
└── No → No docstring needed.
```

---

### "Which test layer should I use?"

```
Can the behaviour be verified with in-process objects and a tempdir?
│
├── Yes → Unit test in tests/test_*.py
│
└── No → Does it require a real database or real filesystem interaction
           across process boundaries?
           │
           ├── Yes → Integration test in tests/integration/
           │
           └── No → Does it correspond to a documented acceptance flow?
                     ├── Yes → Acceptance test in tests/acceptance/test_*_flow.py
                     │         (add row to docs/acceptance.md)
                     └── No → End-to-end in tests/e2e/

Security invariants (path confinement, classifier, approval gating)?
→ Property tests with @pytest.mark.parametrize, not example-only.

Regression for a fixed bug?
→ tests/regression/test_*.py with a comment naming the failure mode.
```

---

### "Do I need an ADR?"

```
Does the change affect any of these?
- Tool governance (registration, schema, destructive flag)
- Audit event shapes or audit level semantics
- Permission modes or approval gate contract
- MCP, ACP, A2A, or ANP wire formats
- OAuth or DPoP authentication behaviour
- Code Mode sandbox or execution backend
- Async-from-sync bridging pattern
- Concurrency model (locks, executor strategy)

├── Yes → ADR required. Create docs/adr/NNNN-short-title.md.
│         Status: Proposed → get review → Status: Accepted → implement.
│
└── No → No ADR needed. Standard PR review is sufficient.
```

---

## Ownership and sign-off

| Area | Who reviews |
|---|---|
| Harness core (`runner/`, `policy.py`, `audit.py`) | Any maintainer |
| Security (threat surface changes) | Two reviewers, at least one with security background |
| OAuth / MCP transport | Maintainer familiar with `docs/adr/0004-oauth-dpop.md` |
| Release tag | Maintainer only (requires GPG-signed tag) |
| ADR acceptance | Two maintainers |

There is no dedicated security team at this project stage. Security-sensitive PRs are flagged by the `security/` branch prefix and the `### Security` changelog tag, which triggers the two-reviewer requirement.
