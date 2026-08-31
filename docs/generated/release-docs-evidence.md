# Release Documentation Evidence Bundle (Generated)

**Generated:** 2026-08-31T05:28:46+00:00
**Git commit:** `70a15bc82c8abdab3cc09c79905305b76e60eec3` on `main`
**Working tree dirty:** no

Regenerate: `python3 scripts/build_release_docs_evidence_bundle.py`

## Reproduce Commands

- `python3 scripts/build_release_docs_evidence_bundle.py`
- `python3 scripts/validate_docs_consistency.py`
- `python3 scripts/report_docs_aging.py`

## Last Gate Run

- Overall gate status: **pass**
- `/opt/homebrew/opt/python@3.14/bin/python3.14 scripts/validate_docs_consistency.py` — **pass** (exit 0)
- `/opt/homebrew/opt/python@3.14/bin/python3.14 scripts/report_docs_aging.py --check` — **pass** (exit 0)

## Documentation Freshness

- Current-truth docs scanned: **17**
- Needs attention: **0** (>90 days)
- All scanned current-truth docs are fresh.

## Roadmap Excerpt

- `H0` Claim and risk hygiene: **Complete** (confidence High, next gate H1)
- `H1` Daily operator loop: **Complete** (confidence High, next gate H2)
- `H2` Multi-surface continuity: **On Hold — M2 foundation complete** (confidence Medium, next gate Owner-validated continuity need)
- `H4` Durable owner/agent operations: **On Hold — shadow wiring exists; ADR-0031 evidence packet prepared 2026-08-27, refreshed 2026-08-31 (same 0 shadow events, `promotion_ready=false`)** (confidence Low, next gate EFX live-proof closure + 2026-09-12 ADR-0031 owner review (promote/extend/revert))
- `H6` Owner packaging and local distribution: **On Hold — local proof exists; daily CLI unwired** (confidence Low, next gate Owner update friction + trust-boundary proof)
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
