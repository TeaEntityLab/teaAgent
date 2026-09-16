# Risk Report — Dogfood Gap Fixes G23–G38 (2026-09-16)

> Satisfies review-system.md §4.2 in solo mode for the first-run, plan-gate,
> MCP-protocol, and CLI error-contract changes below. Owner adjudicated the
> agent-proposed triage in one batch ("Yes for all", 2026-09-16); the triage
> and its provenance tags are in `docs/work-log/dogfood-findings-2026-09-15.md`
> §"Owner adjudication triage for G23–G38"; reasoning and acceptance criteria
> in `docs/reviews/roadmap-rethink-2026-09-16.md` §5.

## Scope

First-run CLI (`cli/_handlers/_misc.py` init/setup, `llm/_config.py`,
`llm/_types.py`, `preflight.py`), background worker argv
(`ergonomics/background_run.py`), run-list output
(`cli/_handlers/_agent/runs.py`, `_ergonomics/session.py`, `agent_status.py`),
MCP server error containment (`mcp_server.py`) and `mcp trust` handler,
memory auto-invalidation loader (`memory/failure_card.py`), skill candidate
install handler, automation CLI (`add` validation, name lookup), `audit
verify` default contract, and `release evidence` progress output.

Not in scope: G34 (consensus, held under ADR-0043), D1 (owner verdict),
G11–G13 (owner: not selected), any sandbox (`teaagent/sandbox/`), approval,
policy, audit-chain, or runner-core code. No high-risk path from
`scripts/high_risk_paths.yaml` is touched; this report exists because G29
and G31 change behavior adjacent to the sandbox and plan gates.

## Risk assessment per change

| Change | Risk | Mitigation |
|---|---|---|
| G29 `init`/`setup` append `.teaagent/` to `.gitignore` in git repos | Writes to a user-owned file; a scripted `init` could modify `.gitignore` unexpectedly. | Append-only, never rewrites lines, skipped when an entry already covers `.teaagent/`, opt-out `--no-gitignore`, TTY confirmation, result reported in the init output. Not a git repo → no-op. The alternative (making the sandbox ignore untracked runtime files) would risk committing runtime state into sandbox branches — rejected. |
| G31 worker inherits `--from-plan`/`--require-plan`/`--skip-plan-check` | Forwarding `--skip-plan-check` means a foreground bypass now also bypasses in the background worker. | That is the documented foreground contract; the worker previously failed closed on `PLAN_GATE` for *every* workspace-write background run, including valid plans. No new bypass is introduced; the flags are forwarded only when the operator passed them. |
| G23/G38 non-interactive `init`/`setup` fail fast without a provider; no key prompt for `fake` | Scripts that relied on the interactive default (`gpt`) now get a classified error. | Owner chose "never silently select a credentialed provider"; the error names the flag to pass. Interactive behavior unchanged. |
| G30 `fake` marked no-network | `preflight`/`plan`/`daily` report ready for `fake` offline. | `fake` never makes network calls; other providers unchanged. |
| G35 MCP unknown-tool → JSON-RPC `-32602`, session survives | A malformed client request no longer ends the session. | Only the unknown-tool/invalid-params class is contained; tool execution errors keep the `isError` result contract; unexpected exceptions still surface. |
| G26 scratchpad pseudo-entry removed from run arrays | Consumers that read the pseudo-entry lose it from JSON. | Top-level JSON type per command preserved; scratchpad hint retained on the human rendering / sibling key per the family's existing branch. |
| G24 plan-gate next steps, G25 progress on stderr, G27/G32/G33/G36 classified errors, G28 `audit verify` argument required up front, G37 automation name lookup | Ergonomics and error-contract changes only. | No gate weakened; stdout JSON unchanged for G25; legacy `.teaagent/audit.jsonl` path still verified for G28; ambiguous automation names error instead of guessing for G37. |

## Reversibility

All changes are in-repo code; rollback is `git revert` of the batch commit. The
only user-visible file write outside `.teaagent/` is the append-only
`.gitignore` line (G29), removable by deleting the line.

## Verification

- Focused pytest across the seven new `tests/test_dogfood_*_g*.py` files plus
  the touched families (`test_cli`, `test_mcp_server`, `test_mcp_trust`,
  `test_automations`, `test_preflight*`, `test_wizard`, first-run/first-session
  acceptance flows, background parity flows): 180 passed. Every new regression
  was observed failing on the pre-change code by its slice.
- Integrated scratch journey (`/tmp`, `TEAAGENT_RUN_ORIGIN=dogfood`, deleted
  after): headless `init` without `--provider` → classified error, directory
  left with only `.git`; `init --provider fake </dev/null` → `gitignore: added`,
  no prompt, scaffold-commit next step; after committing the scaffold,
  `agent preflight fake …` → `ready: true`; `agent run fake …` → `Safe git
  sandbox auto-enabled`, completed, `git status --porcelain` empty; `runs list`
  → every element has `run_id`; bare `audit verify` → classified error rc=1;
  MCP stdio: unknown `tools/call` → `-32602`, next valid call `isError: false`.
- File-scoped `ruff format --check`, `ruff check`, mypy clean on all 19 changed
  source files; `check_god_modules.py` OK; complexity ratchet 58/99.
- Pre-commit hooks on commit; `verify_docs.sh` on the final tree.
- Not exercised live: `release evidence` default-profile progress (runs the
  full gate suite for minutes; unit-proven with a stubbed runner).

## Human Review

Owner adjudicated G23–G38 in one batch (2026-09-16). D1 remains deferred;
ADR-0031 review 2026-09-29; EFX live proof still owner-gated.
