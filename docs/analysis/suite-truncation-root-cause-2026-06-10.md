# Suite Truncation Root Cause — 2026-06-10

> **Claim class:** Dated evidence (WDG-001).
> **Anchor:** `85109e4` on Python 3.12.8 (review package) and Python 3.14.4 (Cursor worker).
> **Finding ID:** ENG-R5 / WDG-001

---

## Symptom

Two full-suite `pytest` attempts on 2026-06-10 in a constrained Cursor worker
environment were killed at ~50% collection/execution progress. Observed exit code
**152** (`128 + 24` = **SIGXCPU**). No test failures were observed before the
kill. One run masked the exit code behind a shell pipe (`| tail`), hiding the
failure from the operator.

Subset tiers remained green:

| Tier | Result |
| --- | --- |
| H4/H5/H6 + tenant isolation (18 files) | 296 passed in 12.4 s |
| Acceptance + regression | 628 passed (+11 subtests) in 51.3 s |

---

## Root Cause

**Primary:** OS-level CPU-time limit in the constrained worker environment,
not a pytest failure or a single flaky test. SIGXCPU terminates the process
when cumulative CPU budget is exceeded; a ~5,400-test suite with coverage
(`pytest --cov`) exceeds that budget before completion.

**Secondary:** Monolithic CI/local default — one command runs the entire corpus
without a documented fast gate. Pre-commit already used an implicit smoke
subset; that split was not canonical in docs or CI until WDG-002.

**Tertiary:** Pipe masking — piping pytest to `tail` without `pipefail` can
report success when the upstream process is killed.

---

## Reproduction

```bash
# Unconstrained (expected: completes on CI ubuntu-latest with Python 3.12)
PYTHONFAULTHANDLER=1 python -m pytest -q

# Constrained worker (may SIGXCPU mid-run)
python -m pytest -q 2>&1 | tail -20   # avoid for diagnosis — use pipefail or tee

# Tiered substitutes (Sprint 1 gates)
python scripts/run_test_tier.py --tier smoke
python scripts/run_test_tier.py --tier acceptance
python scripts/run_test_tier.py --tier nightly
```

---

## Remediation (WDG-002)

| Tier | Command | Gates |
| --- | --- | --- |
| **smoke** | `python scripts/run_test_tier.py --tier smoke` | PR / pre-commit fast path |
| **acceptance** | `python scripts/run_acceptance_tier.py --tier all` | Main branch user workflows |
| **nightly** | `python scripts/run_test_tier.py --tier nightly` | Scheduled / release evidence |

Roadmap and docs must cite tier + run date + commit for test-count claims
(WDB-004 follow-up).

---

## Open Unknown

Whether the historical "4,758 tests pass" claim (2026-06-07 roadmap header) still
holds at HEAD on unconstrained CI was **not re-verified** in the constrained
environment. CI `test` job on `ubuntu-latest` Python 3.12 remains the authority
for full-count confirmation after WDG-002 smoke tier split.
