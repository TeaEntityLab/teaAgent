# Release Documentation Evidence Bundle (Generated)

**Generated:** 2026-06-21T15:33:34+00:00
**Git commit:** `0e8d393005b60c6b0c3b197a00ddc794b0475a13` on `main`
**Working tree dirty:** yes

Regenerate: `python3 scripts/build_release_docs_evidence_bundle.py`

## Reproduce Commands

- `python3 scripts/build_release_docs_evidence_bundle.py`
- `python3 scripts/validate_docs_consistency.py`
- `python3 scripts/report_docs_aging.py`

## Last Gate Run

- Overall gate status: **pass**
- `/Users/teee/dev/teaagent/.venv/bin/python3 scripts/validate_docs_consistency.py` — **pass** (exit 0)
- `/Users/teee/dev/teaagent/.venv/bin/python3 scripts/report_docs_aging.py --check` — **pass** (exit 0)

## Documentation Freshness

- Current-truth docs scanned: **17**
- Needs attention: **7** (>90 days)
- Stale by owner surface:
  - `architecture`: 1
  - `cli`: 1
  - `daily-driver`: 1
  - `docs`: 1
  - `governance`: 2
  - `project`: 1

## Roadmap Excerpt

- `H0` Claim and risk hygiene: **Complete** (confidence High, next gate H1)
- `H1` Daily operator loop: **Complete** (confidence High, next gate H2)
- `H2` Multi-surface continuity: **Partially fixed — M2 foundation wired** (confidence Medium, next gate WDA-002)
- `H3` Ecosystem trust: **Partially fixed — M3 tests pass** (confidence Medium, next gate WDC-002)
- `H4` Durable owner/agent operations: **Partially fixed — shadow wired** (confidence Low, next gate WDA-004)
- `H5` Quality and eval loop: **Partially fixed — release gate wired** (confidence Low, next gate WDA-005)
- `M0` (1-2 weeks): **High** (next gate All 3 checks pass: `validate_docs_consistency.py`, `refresh_competitive_docs.py --check`, `teaagent tool lint --root .`)
- `M1` (2-6 weeks): **High** (next gate CLI/TUI cockpit parity acceptance, run evidence summary acceptance, guided recovery acceptance)
- `M2` (4-10 weeks): **High** (next gate Long-session context guard acceptance, scope budget acceptance, plan revision acceptance)
- `M3` (8-14 weeks): **High** (next gate Extension activation explain acceptance, MCP trust onboarding acceptance, subagent review/merge acceptance)

## Open Residual Risks

No OPEN rows found in the risk register.

## OKF Catalogs

| Bundle | OKF version | Concepts | Manifest digest |
| --- | --- | --- | --- |
| `teaagent-current` | `0.1` | 15 | `6bc5a83b500a8936...` |
| `teaagent-reference` | `0.1` | 27 | `27a4e67dbe6acd13...` |
| `teaagent-history` | `0.1` | 15 | `45f2bab76514e3f8...` |
