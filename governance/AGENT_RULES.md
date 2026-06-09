# AGENT_RULES.md — Environment Hardening (T3 / CV-5 / CV-8)

> These are **environment constraints**, not moral suggestions. The framework's evidence (RHB:
> env-hardening −87.7% exploit rate; ImpossibleBench: read-only tests → cheating ≈0) is the reason
> these belong in structure, not prose. Where a rule cannot yet be machine-enforced in teaagent, it is
> marked **(enforce: manual)** until CI catches up (see Adoption Roadmap A1).

## Allowed (no review needed)
- Add new tests, fixtures, and helpers.
- Refactor low-risk internal functions whose behavior is covered by existing passing tests.
- Update docs/specs to **reflect** the implemented behavior (not to retroactively justify a defect).
- L1 cosmetic changes (logging, docstrings, formatting) under existing test coverage.

## Forbidden (reject the change)
- Delete or weaken an existing test assertion to make a failing test pass. **(enforced: pre-commit +
  CI `check-test-assertion-regression`; override only via `ALLOW_TEST_WEAKENING=1` /
  `Allow-test-weakening:` trailer with human review)**
- Skip / disable type checking (`# type: ignore` without justification), ruff, or bandit.
- `mock` away a *real* error to produce a green light.
- Modify a security/permission policy as a side effect of an unrelated change.
- Auto-grant a tool permission outside the digest-verified path (see SURF-010 spec Forbidden list).
- Direct `deploy` / `release` / publish without the human gate.
- Commit secrets, tokens, or credentials.

## Requires Human Review (stop and ask)
- **authentication / authorization** changes.
- **payment / billing** changes.
- **permission / approval** flows — including `ergonomics/approval_store.py`,
  `integration/resume_preparation.py`, `pending_approval` handling, permission modes.
- **migration** / run-store schema changes.
- **production config**, deploy, release, MCP scope grants.
- **Modifying a test specifically to make a failing test pass** (vs. legitimately updating a test
  because the spec changed — the diff must show *which* applies).
- Anything where an agent would **act on behalf of a user's account**.

## How to use
1. Classify the change L1 / L2 / L3 (Adoption Roadmap §4 table).
2. If it touches anything in **Requires Human Review**, it is L3 — stop and get sign-off before merge.
3. If a step is **Forbidden**, do not find a clever workaround; surface it to the human instead.

_Anti-regression: any new auto-grant / permission-escalation path MUST add itself to the Forbidden or
Requires-Human-Review list above in the same change._
