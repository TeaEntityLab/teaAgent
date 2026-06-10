# WDG-001: Diagnose Full-Suite SIGXCPU Truncation

**Priority:** P0  
**Status:** Fixed  
**Sprint:** 2026-06-10 → 2026-06-17  
**Primary files:** `pyproject.toml`, `tests/conftest.py`, CI workflow logs, new `docs/analysis/suite-truncation-root-cause-2026-06-*.md`

## Problem

Two full-suite attempts on 2026-06-10 were killed by SIGXCPU (exit 152) at
~50% progress with zero failures observed. Exit code was masked by a pipe in
one run. The "4758 tests pass" roadmap claim is therefore unverifiable at HEAD
in constrained environments.

## Scope

1. Reproduce on Python 3.12 with `faulthandler` and `pytest --timeout` enabled.
2. Capture last-collected test, duration, and whether kill is OS CPU limit vs
   pytest internal timeout.
3. Document root cause in a dated analysis note linked from roadmap and
   work-direction INDEX.
4. If harness-side: fix pipe exit-code propagation (finding from reasoning ledger).
5. If environment-side: document minimum CPU budget for full tier.

## Acceptance criteria

- Dated root-cause note with reproduction commands and environment matrix.
- Clean full-suite summary on Python 3.12 in unconstrained environment **or**
  explicit WDG-002 tier split documenting full tier as nightly-only.
- Roadmap/test-count claims cite run date + commit per WDB-004 intent.

## Verification

```bash
PYTHONFAULTHANDLER=1 python -m pytest -q 2>&1 | tee /tmp/full-suite.log
# Document exit code, last test, SIGXCPU vs other
python -m pytest -m smoke -q  # after WDG-002 markers exist
```

## Risks

- May be unfixable in Cursor/sandbox environments — tiering (WDG-002) is the
  acceptable outcome.

## Do not

- Disable tests to force green full suite.
- Quote undated test counts in roadmap after this ticket.
