# WDB-001: Import-Graph Wiring Validator

**Priority:** P0  
**Status:** Scheduled (Sprint 1)  
**Sprint:** 2026-06-10 → 2026-06-17  
**Depends on:** WDA-001 (label registry)  
**Primary files:** `scripts/validate_wiring.py` (new), `tests/test_validate_wiring.py` (new), `.github/workflows/*` or pre-commit config

## Problem

ENG-R2: There is no automated gate detecting modules that are implemented and
tested but unreachable from production entry points. Doc⇄reality drift recurs
every review cycle.

## Scope

1. New script walks import graph from entry points:
   - `teaagent/cli/__main__.py` and CLI handler tree
   - `teaagent/tui/`
   - `teaagent/runner/`
   - `teaagent/gateway/` (if present)
   - `scripts/` invoked by CI
2. Report `teaagent/*` modules unreachable from any entry point.
3. Allowlist only modules explicitly labeled `experimental — unwired` in
   docstring (parse first 40 lines) or listed in a checked-in allowlist file
   with expiry date.
4. Wire into CI and `validate_docs_consistency.py` or pre-commit.

## Acceptance criteria

- Fixture test: unlabeled island module → validator exit 1.
- HEAD after WDA-001 → validator exit 0.
- Documented run command in `docs/acceptance.md` or release checklist.

## Verification

```bash
python scripts/validate_wiring.py
python -m pytest tests/test_validate_wiring.py -q
python scripts/validate_docs_consistency.py --test-quality-mode off
```

## Risks

- Dynamic imports and `__getattr__` lazy loading may cause false positives —
   use static analysis with documented exceptions.
- Test-only imports must not count as "wired"; entry-point list is the contract.

## Do not

- Auto-delete unwired modules.
- Treat test imports as production wiring.
