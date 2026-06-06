# Release Documentation Evidence Bundle (Generated)

**Generated:** 2026-06-06T04:14:55+00:00
**Git commit:** `b0b3054f49231598c378d031dc0feef03e87bd32` on `main`
**Working tree dirty:** yes

Regenerate: `python3 scripts/build_release_docs_evidence_bundle.py`

## Reproduce Commands

- `python3 scripts/build_release_docs_evidence_bundle.py`
- `python3 scripts/validate_docs_consistency.py`
- `python3 scripts/report_docs_aging.py`

## Documentation Freshness

- Current-truth docs scanned: **17**
- Needs attention: **0** (>90 days)
- All scanned current-truth docs are fresh.

## Roadmap Excerpt

- `H0` Claim and risk hygiene: **In Progress** (confidence Medium, next gate DOCOPT-012 generalized guarded-claim registry)
- `H1` Daily operator loop: **In Progress** (confidence High, next gate M1 complete)
- `H2` Multi-surface continuity: **Pending** (confidence Medium, next gate M2 complete)
- `H3` Ecosystem trust: **Pending** (confidence Medium, next gate M3 complete)
- `H4` Durable team operations: **Pending** (confidence Low, next gate M4 complete)
- `H5` Quality and eval loop: **Pending** (confidence Low, next gate M5 complete)
- `M0` (1-2 weeks): **Medium** (next gate `validate_docs_consistency.py`, `refresh_competitive_docs.py --check`, `teaagent tool lint --root .` pass)
- `M1` (2-6 weeks): **High** (next gate CLI/TUI cockpit parity acceptance, run evidence summary acceptance, guided recovery acceptance)
- `M2` (4-10 weeks): **Medium** (next gate Long-session context guard acceptance, scope budget acceptance, plan revision acceptance)
- `M3` (8-14 weeks): **Medium** (next gate Extension activation explain acceptance, MCP trust onboarding acceptance, subagent review/merge acceptance)

## Open Residual Risks

| ID | Category | Priority | Description |
| --- | --- | --- | --- |
| SEC-05 | Budget | P2 | Cost accounting reads `context['_cost_cents']` written by the LLM adapter — injectable by malicious adapter or prompt... |
| SEC-09 | Multi-sig | P2 | Multi-sig approval hash uses 1-hour time bucket (`int(time.time()/3600)`); captured signature replayable for up to 59... |
| SEC-11 | Undo | P2 | `UndoJournal._PATH_WRITE_TOOLS` covers file tools only; `workspace_run_shell_mutate` not tracked — UI shows "undo ava... |
| SEC-12 | Audit | P2 | `os.fsync()` failure caught and silenced; audit degrades to in-memory only with no operator notification; disk-full a... |
| SEC-13 | Testing | P1 | Critical security paths (cost tracking, audit HMAC, approval denial) mocked out in tests — bugs live undetected (conf... |
| SEC-14 | Permission | P3 | `preapproved_call_ids` deprecated but still functional — old integrations or adversarial callers can pre-approve arbi... |
| SEC-15 | Multi-sig | P2 | `TEAAGENT_ALLOW_DEV_SIGNATURES=1` accepts SHA-256 of `(message+pubkey)` as valid signature; no runtime guard prevents... |
| SEC-16 | Code Quality | QW | Dead code at `budget_monitor.py:104-119` after early return — maintenance hazard that could accidentally activate on ... |
| DS-04 | Audit | P3 | Stale `audit_trail` dict in suspension JSON predates CG-10 fix; forensic tooling may prefer the stale copy over the r... |
| SC-01 | Dependencies | P2 | Two alpha packages in production lock (`opentelemetry-exporter-gcp-logging==1.12.0a0`, `opentelemetry-resourcedetecto... |
| SC-02 | Dependencies | P1 | `anthropic` SDK and `pyyaml` imported at runtime but undeclared in `pyproject.toml` — silent `ImportError` on install... |
| SC-03 | Dependencies | P2 | `aiohttp` and `mcp` SDK in lock as orphans — not declared, not imported in core; add 22 transitive packages to attack... |
