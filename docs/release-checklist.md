# Release Checklist

Use before tagging a minor release or merging a federation/protocol ADR.

## Competitive landscape hygiene

1. Re-run [scripts/refresh_agent_readme_survey.md](../scripts/refresh_agent_readme_survey.md) against DeepWiki/upstream signals (Codex, Claude Code, OpenCode, OpenHands, Aider, LangGraph, CrewAI).
2. Update `Last reviewed: **YYYY-MM-DD**` in the survey artifact.
3. Sync [docs/backlog-priority.md](backlog-priority.md) and [docs/use-cases.md](use-cases.md) differentiator tables.
4. Regenerate coverage artifacts:
   - `python3 scripts/build_acceptance_status.py`
   - `python3 scripts/build_use_case_matrix.py`
   - `python3 scripts/render_use_case_dashboard.py`
5. Run `python3 scripts/validate_docs_consistency.py`.

## Provider and docs drift

- Confirm README/USAGE/architecture provider counts match `PROVIDER_CONFIGS`.
- Run `python3 -m pytest tests/acceptance/test_provider_matrix_consistency_flow.py -q`.

## Acceptance smoke

- `python3 -m pytest tests/acceptance --collect-only -q` matches `docs/acceptance.md` status count.
- Spot-check new acceptance flows referenced in the survey backlog table.
