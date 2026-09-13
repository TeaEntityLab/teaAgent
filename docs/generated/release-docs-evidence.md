# Release Documentation Evidence Bundle (Generated)

**Generated:** 2026-09-13T14:59:50+00:00
**Git commit:** `c2d9b5c88c260825b30d89a9f1e3e00ab20f447e` on `main`
**Working tree dirty:** yes

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
- Needs attention: **6** (>90 days)
- Stale by owner surface:
  - `cli`: 1
  - `docs`: 1
  - `governance`: 1
  - `project`: 1
  - `security`: 1
  - `verification`: 1

## Roadmap Excerpt

- `H0` Claim and risk hygiene: **Complete** (confidence High, next gate H1)
- `H1` Daily operator loop: **Complete** (confidence High, next gate H2)
- `H2` Multi-surface continuity: **On Hold — M2 foundation complete** (confidence Medium, next gate Owner-validated continuity need)
- `H4` Durable owner/agent operations: **On Hold — shadow wiring exists; ADR-0031 evidence packet prepared 2026-08-27, refreshed 2026-08-31 and re-verified 2026-09-12 over the closed decision window 2026-08-13→2026-09-11 (`prepare_h4_evidence.py --since 2026-08-13 --until 2026-09-11`: 0 observed / 0 reachable runs, verdict `unexercised`; `promotion_ready=false` is a hardcoded literal, not a metric); H4 demo `scripts/exercise_h4_shadow_demo.py` exercisable (2 synthetic candidates, must not launder into C1) and guarded (`tests/test_h4_shadow_demo.py`); 2026-09-12 expiry-day state: no dogfood session booked, zero new runs and zero new friction entries since review, so promotion is unreachable — the decision due today is the owner's: extend only with a dated dogfood session booked, else revert (default)** (confidence Low, next gate Owner decision on ADR-0031 today 2026-09-12 (extend-with-booked-session or revert); EFX live-proof closure remains pending owner authorization)
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
