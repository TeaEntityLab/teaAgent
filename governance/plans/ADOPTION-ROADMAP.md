# Layer A — Adoption Roadmap: Governed Agentic Engineering → teaagent

> **Scope:** A risk-scaled roadmap to wire the [framework](../framework/GOVERNED-AGENTIC-ENGINEERING.md)
> into teaagent as real tooling/CI — not file-level steps, direction first. Companion to the file-level
> [SURF-010 executable plan](SURF-010-EXECUTABLE-PLAN.md).
>
> **Why → What → Done.**
> **Why:** the repo had no spec/permission/feedback layer (T0 files all missing) yet ships L3-class
> changes (e.g. SURF-010 auto-grants tool permissions on resume). **What:** a minimal enforceable
> governance core that scales with risk. **Done:** L3 changes cannot merge without spec + closed P0
> test matrix + permission binding, and the gate is enforced by CI, not prose.

## Guiding constraint — scale governance with risk (framework §4)

| Level | teaagent examples | Governance applied |
|---|---|---|
| **L1** | typo, log message, docstring, CSS-equivalent cosmetic | task brief + existing tests. No spec, no mutation. |
| **L2** | new CLI flag, new workspace tool, data transform, non-security TUI command | mini spec (`templates/SPEC.template.md`) + test matrix + CI. Mutation optional. |
| **L3** | approval/permission flow, resume/trust inputs, run-store schema/migration, sandbox, deploy/release, MCP scope, anything touching `ergonomics/approval_store`, `pending_approval`, `permission` modes | full: 4-layer spec + permission binding + P0 matrix + state-machine assertions + mutation (nightly). Human gate + rollback mandatory. |

> The whole point of §4 is to **not** over-invest. Most of teaagent's day-to-day is L1/L2. The heavy
> machinery exists to protect the handful of L3 trust boundaries.

## Current state (verified 2026-06-09 @ HEAD `c37e181`)

- T0 five files: **all missing** before this work.
- CI exists: `.github/workflows/{ci,security,nightly-smoke,release}.yml`.
- Static analysis already present: **bandit** (security), **mypy**, **ruff**, **coverage**.
- Test runner: **pytest** (`pytest-xdist`, `pytest-random-order`, `pytest-cov`, `pytest-benchmark`).
- Mutation testing: **none**.
- MCP spec-serving surface: **none yet** → Zero-Trust Spec Registry (§5) is **deferred, not built**.

## Phases

### A1 · Minimal enforceable core (one-time, this commit)
**Goal:** land the T0 skeleton and make `AGENT_RULES.md` an *environment* constraint, not advice.

- Land `governance/` with: `AGENT_RULES.md`, `LOCAL_FEEDBACK.md`, `DONE_CHECKLIST.md`,
  `templates/SPEC.template.md`, `templates/TEST_MATRIX.template.md`, the framework doc, and this roadmap.
- **Test-weakening gate — DONE 2026-06-09:** `scripts/check_test_assertion_regression.py` AST-counts
  assertions per `test_*` function in the base vs the change and **fails** when an existing test is
  deleted or loses assertions. Wired into **pre-commit** (`check-test-assertion-regression`, diffs vs
  HEAD) and **CI** (`lint` job, diffs vs PR base / `github.event.before`). Override:
  `ALLOW_TEST_WEAKENING=1` or an `Allow-test-weakening: <reason>` commit trailer — the practical form of
  the framework's "test files effectively read-only" (T3 / CV-5). Evidence basis: RHB env-hardening cut
  exploit rate 5.7pp (−87.7%); ImpossibleBench: read-only tests drive cheating ≈0. Covered by
  `tests/test_check_test_assertion_regression.py` (8 cases) and verified end-to-end (real weakening
  flagged; override downgrades to warning).
- **Acceptance:** the five governance entry-points exist and are linked from `governance/README.md`,
  **and** the test-weakening gate is enforced in both pre-commit and CI. ✅

### A2 · Permission binding for L3 paths — DONE 2026-06-09
**Goal:** make CV-8 concrete where it matters in *this* repo.

- Permission-binding specs (Allowed / Forbidden / Requires Human Review) now exist for both trust
  modules: `resume_preparation.py` → [`specs/SURF-010-resume-parity.md`](../specs/SURF-010-resume-parity.md);
  `ergonomics/_approval_state.py` (public `approval_store`) →
  [`specs/approval-store-permission-binding.md`](../specs/approval-store-permission-binding.md).
- Each Forbidden rule is **bound to a guard test** that already enforces it (the approval store's were
  pre-existing — DS-12, token-exactness; SURF-010's are the P0 tests added in the prior pass).
- Made structural via `tests/test_governance_permission_binding.py`: an L3 trust module must have a
  spec declaring Forbidden + Requires-Human-Review, and **every guard test a spec cites must exist**
  (this caught a missing-citation drift on first run).
- **Acceptance — met:** every grant/escalation module has a spec-linked Forbidden list and ≥1 guard
  test asserting a Forbidden behavior is blocked. ✅
- _Follow-up (not blocking): annotate the module docstrings with a one-line pointer to their spec._

### A3 · Mutation gate for L3 only (nightly)
**Goal:** verify the *tests themselves* catch regressions on the trust boundary — without taxing the
whole tree.

- Introduce `mutmut` (or `cosmic-ray`) as a **nightly** job (extend `nightly-smoke.yml`), **scoped to
  the permission/approval/resume modules only**. Mutating the full tree is explicitly out of scope.
- Add **spec mutation** (T5) as a manual checklist item per L3 spec — not automation yet.
- **Acceptance:** a deliberately-injected logic mutation in `resume_preparation.py`
  (e.g. flip the digest-match condition) is caught by the existing P0 tests in the nightly run.

### A4 · (Deferred) Zero-Trust Spec Registry
Explicitly **not** justified until teaagent exposes specs over MCP. When/if that surface appears, apply
framework §5 items 1–10 (scope binding, ticket-bound access, read receipts, deny-by-default, capability
attestation per *Breaking the Protocol* / ATTESTMCP). Documented here so the decision is on record, not
forgotten.

## Sequencing decision
Per the planning discussion: do **Layer B steps 1–3 first** (concrete, likely to surface a real
permission-test gap today), then return to A1's CI hardening (A2/A3). Rationale: find the bug before
building the scaffolding around it.

## Falsifiability (when this roadmap is wrong)
- If, with read-only tests + mutation + state-machine assertions in place, L3 modules' defect rate is
  **not** measurably below pre-framework baseline → the tactical layer adds cost without value; cut it.
- If A3's nightly mutation run produces mostly equivalent-mutant noise and no real signal → descope to
  manual spec-mutation only.
- If maintaining specs costs more reviewer time than the bugs they prevent → drop to L3-only specs.
