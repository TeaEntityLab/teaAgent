# Dogfood Findings — Consolidated Adjudication List (2026-09-15)

> **Type:** agent-prepared consolidation of the 2026-09-15 dogfooding session.
> **Evidence boundary:** every item below was observed by exercising the real
> harness (fake provider, `TEAAGENT_RUN_ORIGIN=dogfood`). Nothing here is an
> owner verdict — `promotion_ready` stays `false`; each item needs owner
> adjudication. Source detail lives in `docs/roadmap-status.md` update lines
> 27–61 (2026-09-15).
> **Scope:** every CLI command, subcommand, interactive surface, MCP transport
> (stdio + HTTP + auth), write path, background lifecycle, and cockpit surface
> exercised headless. The only unexercised surface is the owner-driven TUI
> dogfood session (`m4-dogfood-2026-09-15.md`).

## Bugs fixed this session (3)

| # | Bug | Fix |
|---|---|---|
| F1 | `AgentRunner` built without `workspace_root` → approval shadow unreachable on `agent run` (only subagent launches emitted `h4_governance_shadow`) | `8fd7a461` pass `config.root` |
| F2 | `runs review` counted only `tool_call_started`; calls paused at the approval gate (`tool_call_pending_approval`) were invisible → `coverage 0.0` | `ec7656e3` count pending-approval as a call |
| F3 | CLI `approval approve` recorded `tool_call_approved` with no `authority_type`/`approved_by` → indistinguishable from JIT-prompt approvals | `2f144102` record `cli_approval`/`operator` |

## Safety-critical gaps (adjudicate first)

| # | Gap | Why it matters |
|---|---|---|
| G1 | **Deny presets are advisory-only at runtime.** `approval deny` registers a grant and `check`/`explain` report `decision: deny`, but `assert_allowed`→`check_preset`→`is_allowed` collapses `deny` and `prompt` to `False` — a matched deny grant never blocks (falls through to prompt or executes). | A documented safety control does nothing. |
| G2 | **`undo` can `reset --hard` + `clean -fd` on `main`.** `GitBranchSandbox.rollback()` assumes HEAD is on the sandbox branch; after a headless run `keep()` already restored `main`, so `undo` on a completed run wipes uncommitted work on `main`, then deletes the kept review branch. `undo --preview` also diffs `sandbox→original` where `original` has moved — shows all later commits, not just the run's. | Data-loss hazard on the primary rollback path. |
| G3 | **Sandbox-branch leak.** A headless `agent run` left HEAD on a `teaagent-sandbox-*` branch — the sandbox didn't restore `main` on completion (same family as G2). | Leaves the operator on a wrong branch. |
| G4 | **BG-001 §3.3 orphan derivation not implemented.** SIGKILLed background process shows `alive:false`, `exit_code:0`, `stopped_at` — no `orphaned` marker; the §6 exit-code fallback makes a kill indistinguishable from a clean exit. | Orphaned background runs are invisible. |
| G5 | **Pending-approval parity gap.** `control.approval.pending_count` (limit=100) reports 3, but `pending_approvals.queue_depth`, `approval pending`, and `approval next` (all limit=20) report 0 — the 3 pending runs are older than the 20 most recent. | The dedicated "what awaits my approval" surface actively misleads. |

## Other gaps (adjudicate)

| # | Gap |
|---|---|
| G6 | `approval preset strict` is a no-op — its deny entries lack `path_glob`/`command_prefix`, so they're skipped; "deny all destructive tools" applies nothing. |
| G7 | Empty RBAC role store — `.teaagent/roles/` + `role-assignments/` empty → `check_action_permission` denies every `subagent_launch` ("no role with permission `start_workflow`"); harmless in shadow, blocks enforcement. |
| G8 | `subagent_launch` allow path unreachable by design — `assignee` always falls back to `parent_run_id` (fresh per run), so no role can ever match. |
| G9 | Approval-shadow observation bias — `evaluate_approval_policy_shadow` only fires inside `handle_approval_request` (prompt mode + destructive); `allow`/`workspace-write`/`read-only` runs emit no shadow → H4 evidence biased to prompt mode, blind where enforcement matters. |
| G10 | `attach --resume` can't resume non-default-provider runs — no `--provider` flag, resumes with configured default → credential error. `agent resume <provider>` works. |
| G11 | `mcp trust` silent-discard footgun — wrong/missing `TEAAGENT_MCP_TRUST_KEY` reads the encrypted policy as empty and overwrites it, wiping trust grants with no error. |
| G12 | `--approve-call-id` deprecated and ignored but still accepted — a stale flag silently does nothing. |
| G13 | `doctor all` `ok:False` counts unconfigured optional providers as failure — an operator can't tell "no providers configured" from "something broken". (Docs frame it as a readiness gate — may be intended.) |
| G14 | ANP dead surface — `agent run` ANP path is a stub. |
| G15 | **No CLI reject/cancel for a queued pending approval** (refined). `tool_call_denied` IS emitted (`teaagent/runner/_approval_manager.py:134`) when `approval_handler` returns `False` (interactive decline), and `pending_approval_for_run` clears on it — the deny lifecycle is fully built. Missing is only a **CLI command** to deny a *queued/headless* pending approval: `approval` exposes `approve` but no `deny`/`reject` for an already-paused run. A small, well-scoped `feat:` — `approval deny <call_id>` recording `tool_call_denied`. |
| G16 | **Pending-approval durability asymmetry — no expiry on main path.** The subagent approval queue auto-times-out (`pending_request_timeout_seconds: 3600`), but the main `tool_call_pending_approval`/`run_paused` path has no expiry — `pending_approval_for_run` clears only on approve/deny/complete/fail, so a paused run that never resumes stays pending forever. With G15 (no reject), a declined-but-unactionable approval lingers indefinitely. |
| G17 | **TUI cockpit tabs unreachable — dead code.** `CockpitScreenRenderer`/`CockpitDataManager`/`CockpitTab` (WORKFLOWS/APPROVALS/COSTS/MEMORY/BACKGROUND) are defined and re-exported from `teaagent.tui` but nothing instantiates them — no command/keybinding/render path reaches the tabbed screens. `core.py` refreshes `build_control_cockpit` data but never renders the tabbed UI. The spec's §3.1 "TUI tabs" half of cockpit acceptance can't be exercised. |
| G18 | **Dead-code gate blind spot — TUI excluded + opt-in.** `check_dead_code.py` runs `vulture teaagent/ --exclude teaagent/tui/` — it excludes the TUI directory, so the dead-code gate has a blind spot exactly where the cockpit dead code (G17) lives. It's also not in `.pre-commit-config.yaml` and vulture isn't installed by default — the gate is opt-in and currently a no-op. |
| G19 | **TUI APPROVALS tab semantic conflation.** The dead TUI cockpit renders correctly (all 5 tabs work when called directly — refines G17: functional, just unwired), but the APPROVALS tab's "Pending Approvals (21)" counts **memory-quarantine entries** (`review_state in [pending, quarantined]`), not `tool_call_pending_approval` queue entries (3 real). Same label, different meaning — an operator sees memory-review items labeled as approvals. |
| G20 | **TUI WORKFLOWS tab conflation — runs labeled active workflows.** "Active Workflows (20 total)" lists `run_id`s with `status='completed'` (from `RunStore.list_runs`) — shows runs (not workflows) and completed (not active). Same mislabeling pattern as G19: the TUI cockpit tabs systematically label contents that don't match. |
| G21 | **Approval queue has no single source of truth — three divergent sources.** `control-plane serve` `/api/jit/diff` `pending` comes from `jit_server.get_pending_requests()` (in-memory JIT server), a *third* approval source distinct from the `tool_call_pending_approval` audit events. Three surfaces, three sources: cockpit `queue_depth` (audit, limit=20), `approval pending`/`next` (audit, limit=20), control-plane JIT (in-memory) — none agreeing; the JIT surface can't see the 3 audit-pending approvals at all. |
| G22 | **Audit-integrity gap — `git_sandbox_resolved` + `session_suspended` events orphaned to stale `pending-*.jsonl` temp files, lost from real run logs.** `run.py:576` `store.logger_for_result(result, audit)` promotes `pending-<uuid>.jsonl` → `<run_id>.jsonl` and unlinks the temp, but `run.py:615` `resolve_git_sandbox_after_run` then writes `git_sandbox_resolved` to the same `audit` (path still the deleted temp) → recreates `pending-<uuid>.jsonl` with only the resolved event, never promoted. `resume.py:117` `store.audit_logger()` (run_id=None) writes `session_suspended` to a pending temp that is never promoted. Measured: 115 `git_sandbox_resolved` + 30 `session_suspended` events orphaned (absent from the real run `.jsonl`); 9 crash-orphan runs whose only audit trail is an unindexed pending temp. The sandbox-resolution and suspension lifecycle events are silently dropped from the audit trail. |
| G23 | **`init --provider fake` prompts for `FAKE_API_KEY` and crashes on non-TTY stdin.** `_misc.py:316-319` calls `getpass.getpass(f'Enter {env_var}…')` unconditionally whenever `--api-key` is omitted — even for `fake`, whose `PROVIDER_CONFIGS['fake'].api_key_env` is `'FAKE_API_KEY'` but which needs no key. On `</dev/null`/piped stdin `getpass` raises EOFError → generic `Unexpected error: ` (empty message) + rc=1, leaving an empty `.teaagent/`. First-run UX dead-ends on the one provider meant for headless smoke. |
| G24 | **`init`/`setup` never surface the workspace-write plan gate.** `init --permission-mode workspace-write` writes a config whose first `agent run` then fails `Error [PLAN_GATE]` (rc=2) — `_require_plan_gate` auto-enables `require_plan` for `workspace-write` (`_agent/config.py:159-161`), but `init`'s `next_steps` and `setup`'s output never mention `plan`/`--from-plan`/`--skip-plan-check`. A fresh operator following the printed next-steps hits an unexplained hard gate. |
| G25 | **`release evidence` (default `release`/`full` profiles) runs `pre-commit run -a` + full acceptance tier with no progress output and 900s timeouts** (`release_evidence.py:651-667`). On this tree it exceeds 60–90s silently; `--profile counts-only` returns in ~6s. A read-only-looking command that actually runs the whole gate suite, with no indication it's doing so. |
| G26 | **Scratchpad object injected into run-list arrays.** `runs list`, `session list`, and `agent status` append `{'scratchpad_last_goal': ...}` as an extra element inside the run array (`_agent/runs.py:224`, `_ergonomics/session.py:138`, `agent_status.py:31`). Consumers iterating the array get a non-run entry with no `run_id`/`status` — a schema-breaking output bug. |
| G27 | **`mcp trust allow`/`deny` crash on missing `TEAAGENT_MCP_TRUST_KEY`.** With the env var unset, both raise through the generic `Unexpected error:` handler (empty message, rc=1) instead of a clean classified error. Distinct from G11 (which is the *wrong*-key silent-discard); this is the *missing*-key path. |
| G28 | **`audit verify` with no args fails on a nonexistent default.** Bare `teaagent audit verify` targets `.teaagent/audit.jsonl` which doesn't exist (per-run logs live under `.teaagent/runs/`), so it errors and only then tells you to pass `<run_id>` or `--path`. The default should either verify all run logs or require the arg up front. |
| G29 | **`init`/`setup` never gitignore `.teaagent/`, so the auto-enabled git sandbox fails on the first run in a git repo.** `init` writes `.teaagent/config.json`+`config.toml` but no `.gitignore` entry; nothing in `teaagent/` writes one (workspace tools only *read* it). On a fresh git workspace the first `agent run` prints `Git sandbox initialization failed: Worktree is dirty` because `.teaagent/` runtime files are untracked — the safe-sandbox feature silently disables itself exactly when a new user needs it. |
| G30 | **The `fake` provider fails its own connectivity check, so `agent preflight`/`plan`/`daily` return `ready:False`/rc=2 offline.** `check_provider_connectivity` (`preflight.py:93-100`) treats `fake` as remote and does a real `socket.getaddrinfo('fake.example.com')`, which fails offline; `is_local_provider` (`_config.py:126-136`) only matches `localhost`/`127.0.0.1` base_urls. The provider built for offline dogfooding/smoke can't pass its own readiness gate. |
| G31 | **`--background` drops the plan flags, so a workspace-write background run always dies on PLAN_GATE.** `build_agent_run_command` (`ergonomics/background_run.py:463-536`) rebuilds the worker argv but never forwards `--skip-plan-check`, `--from-plan`, or `--require-plan`. The foreground run accepts `--skip-plan-check`, but the detached worker re-runs without it and exits `Error [PLAN_GATE]` — `background list` then shows `alive:false` with no run produced. `--background` is unusable in `workspace-write` mode. |
| G32 | **`memory failures auto-invalidate` crashes on `str / str`.** `MemoryAutoInvalidationConfig.from_workspace_config` (`failure_card.py:249`) does `root / '.teaagent'` on the raw `args.root` string — unlike `FailureCardStorage.__init__` which wraps `Path(root)`. Any `memory failures auto-invalidate` invocation raises `TypeError: unsupported operand type(s) for /: 'str' and 'str'` → generic `Unexpected error` rc=1. |
| G33 | **`skill candidate install` raises uncaught on a missing candidate.** `skill candidate install nonexistent` → `Unexpected error: skill candidate 'nonexistent' not found` rc=1, while sibling subcommands (`show`/`eval`/`review`) return a clean `{"status":"error","message":"...not found"}`. Inconsistent error contract on the same not-found path. |

## Denial candidate (owner adjudication)

| # | Candidate |
|---|---|
| D1 | 1 `subagent_launch` denial in the H4 shadow receipts — needs owner verdict (false-positive classification is owner-only per ADR-0031 exit criterion 1). |


## H4 evidence produced (B2 complete)

- `prepare_h4_evidence.py --since 2026-08-13 --until 2026-09-15`: **9 observed** `h4_governance_shadow` events (8 `approval` + 1 `subagent_launch`), 21 reachable runs, 7,779 total, verdict `needs_review` (up from `unexercised`/0).
- `build_h4_decision_packet.py`: **4/5 criteria `prepared`** (false-positive window, coverage, perf SLO, rollback); only criterion 4 (human sign-off) `human_required`. `promotion_ready: false`.

## What remains owner-only

- ADR-0031 sign-off (criterion 4) — the packet is ready.
- The owner-driven TUI dogfood session (`m4-dogfood-2026-09-15.md`) — the one surface agents can't drive.
- Adjudication of G1–G33 + D1 — each is a `feat:`/design change or a verdict, not a dogfooding step.

## Owner adjudication triage (agent-proposed, 2026-09-15)

Proposed DR-006 provenance per gap so adjudication is a sign-off, not an
analysis session. These are proposals — the owner assigns the gate.
`friction-driven` is not proposed anywhere: no friction-log entries exist to
cite. Nothing here is scheduled by this table.

| # | Proposed provenance | Owner decision needed | Suggested disposition |
|---|---|---|---|
| G1 | `governance-gap` | Should a matched deny grant block in every mode? | Fix `check_preset` to distinguish `deny` from no-preset; P0 |
| G2 | `governance-gap` | Should `undo` refuse when HEAD is not on the sandbox branch? | Guard `rollback()` on a current-branch check; P0 |
| G3 | `governance-gap` | Should headless runs always restore the original branch? | Restore-on-complete in `keep()`/run `finally`; P0 |
| G4 | `governance-gap` | What is the §3.3 orphan-marker contract? | Emit `orphaned` when pid dies without a clean exit record |
| G5 | `governance-gap` | Should all pending-approval surfaces share one unbounded query? | Single source: drop `limit=20` or paginate |
| G6 | `governance-gap` | Should `preset strict` apply scoped denies, or be removed? | Give preset deny entries scope, or drop the preset |
| G7 | `governance-gap` | What is the intended default RBAC role set? | Ship a default role or document empty-store semantics |
| G8 | `governance-gap` | Should `assignee` resolve to `operator_id`? | Design decision, then wire the allow path |
| G9 | `governance-gap` | Should the shadow observe all modes, not just prompt? | Design decision; affects H4 evidence validity |
| G10 | `governance-gap` | — | `attach --resume` inherits the run's recorded provider; small fix |
| G11 | `governance-gap` | Should an undecryptable trust policy fail closed? | Error on decrypt failure instead of reading as empty |
| G12 | `governance-gap` | — | Remove or hard-error on `--approve-call-id` |
| G13 | `governance-gap` | Is `ok:False`-on-unconfigured intended? | Split `configured` vs `unconfigured` in `doctor all` output |
| G14 | `legacy-competitive` | Wire the ANP path or quarantine/delete it? | ADR-0043-style disposition |
| G15 | `governance-gap` | — | Add `approval deny <call_id>` for paused runs (deny mechanism already exists) |
| G16 | `governance-gap` | Should paused runs expire? | Add expiry or document the no-expiry intent |
| G17 | `owner-override` | Wire the TUI cockpit tabs or delete them? | Decision gates G19/G20 |
| G18 | `governance-gap` | — | Include `teaagent/tui/` in vulture + wire the gate into pre-commit |
| G19 | `governance-gap` | (moot if G17 deletes) | Point APPROVALS tab at `tool_call_pending_approval` |
| G20 | `governance-gap` | (moot if G17 deletes) | Point WORKFLOWS/COSTS tabs at real workflow data or relabel |
| G21 | `governance-gap` | Which approval source is canonical? | Single source of truth for pending approvals |
| G22 | `governance-gap` | — | Order audit promotion after sandbox resolution; promote the suspend logger |
| D1 | owner verdict | True or false positive? | ADR-0031 criterion-1 input |

## Owner decisions (2026-09-15)

Owner adjudicated the full triage in one batch. These decisions authorize the
implementation below; each lands under the provenance tag proposed above.

| # | Decision |
|---|---|
| G1 | **Block in all modes** — a matched deny grant hard-blocks in prompt/allow/workspace-write/read-only. |
| G2+G3 | **Fix both** — `rollback()` refuses when HEAD isn't on the sandbox branch; runs restore the original branch on completion. |
| G4 | **Fixed in `1611e71b` — orphaned marker** — emit `orphaned` when a tracked pid dies without a clean exit record. |
| G5+G21 | **Unify on audit events, unbounded** — all pending-approval surfaces read `tool_call_pending_approval` from the audit log with no limit; control-plane JIT reads the same store. |
| G6 | **Fix strict preset** — preset deny entries get wildcard scope so "deny all destructive tools" applies. |
| G7+G8 | **Default role + operator_id assignee** — ship a default operator role with `start_workflow`; resolve `assignee` to `operator_id`. |
| G9 | **Observe all modes** — `evaluate_approval_policy_shadow` runs on every destructive call regardless of mode. |
| G10 | Fixed in `1611e71b` — `attach --resume` inherits the run's recorded provider. |
| G11 | **Not selected** — leave trust-key silent-discard as-is. |
| G12 | **Not selected** — leave `--approve-call-id` as-is. |
| G13 | **Not selected** — leave `doctor all` semantics as-is. |
| G14 | **Quarantine per ADR-0043** — mark ANP stub `legacy-competitive`/On Hold. |
| G15+G16 | **Deny CLI + expiry** — as decided: `approval reject <call_id>` records `tool_call_denied` and resumes the paused run without the call; `approval deny` reverted to grant-only. Paused approvals auto-deny after `TEAAGENT_PENDING_APPROVAL_TTL_SECONDS` (default 24h). (Implemented as `reject`, not `deny <call_id>`.) |
| G17 | **Delete the dead code** — remove `CockpitScreenRenderer`/`CockpitDataManager`/`CockpitTab`; moots G19/G20. |
| G18 | Fixed in `1611e71b` — include `teaagent/tui/` in vulture + wire the gate into pre-commit. |
| G22 | Fixed in `1611e71b` — order audit promotion after sandbox resolution; promote the suspend logger. |
| D1 | **Deferred** — needs more evidence before classifying. |
| ADR-0031 | **Extend, conditioned on G1–G5** — new close date; promotion only after the safety-critical fixes land and are re-dogfooded. |

## Re-dogfood of selected G1/G6/G22 fixes (ADR-0031 G1–G5 condition, 2026-09-15, post-`1611e71b`)

- **G1 live**: with the strict preset applied, `approval check workspace_write_file --path /tmp/x.txt` returns `decision: deny` in both default and `--permission-mode allow`. Deny grants now block, not warn. (Probe grants revoked afterward.)
- **G6 live**: `approval preset strict` now applies 2 deny grants with `path_globs: ["*"]` (`grants_skipped: []`) — was a no-op.
- **G22 live**: a `--git-sandbox-auto-stash` dogfood run (`8cbc123639cf44aea59a191adab1d25d`) lands `git_sandbox_resolved` in the real run `.jsonl` (order: started → … → completed → resolved) with HEAD restored to `main`. A dirty-worktree run without auto-stash skips the sandbox lifecycle entirely — correct, not a regression.
- **154 `pending-*.jsonl` temps are pre-fix orphans** (newest 2026-09-14) — no new orphans from post-fix runs. Existing set is unindexed history, not new loss.
- H4 evidence unchanged (9 observed / 21 reachable): fake-provider runs make no tool calls, so no new shadow receipts. Re-dogfood proves the G1/G6/G22 fixes, not new H4 coverage — recorded honestly for the ADR-0031 condition.

## Re-dogfood of G2–G5 fixes (ADR-0031 box 7, 2026-09-16, post-`1611e71b` + `18d1feaa`)

All probes ran in throwaway scratch workspaces (`/tmp`, deleted after) — zero repo audit writes.

- **G2 live**: scratch git repo → `start()` → commit agent work → `keep()` (HEAD back on `main`) → `rollback()` returns `success=False` with `HEAD is on 'main', not the sandbox branch ... Refusing rollback`; `f.txt` intact, agent work preserved. The pre-fix `reset --hard` + `clean -fd` on `main` path is closed.
- **G3 live**: headless `agent run fake ... --git-sandbox` on a clean scratch repo (`.gitignore` covers `.teaagent/`, mirroring real repos) → branch created, run completes, HEAD restored to `main`, `git_sandbox_resolved` lands in the **real** run `.jsonl` (order: started → … → completed → resolved). Kept branch retained for review. (A dirty tree without auto-stash correctly skips the lifecycle — pre-existing, not a regression.)
- **G4 live**: `BackgroundRunStore.start([sleep 30])` + `update_run_id` → SIGKILL → `alive=False`, `exit_code=-9`, `orphaned=True` on both `get()` and `list()`. Clean-exit (`exit 0`) stays unmarked. Caveat: the marker derives on `get()`/`list()` reads via `_enrich_liveness` — a SIGKILLed `agent run --background` whose pid dies before backfilling `run_id` shows `orphaned` unset until a `run_id` exists (observed `run_id: null`, no marker); the unit path with `run_id` set marks correctly.
- **G5 live**: 25 pending runs in scratch → CLI `approval pending` `queue_depth: 25`, TUI `approvals pending` `queue_depth: 25`, shared snapshot `25`, cockpit `pending_count: 25`, `approval next` serves the newest. Post-`18d1feaa` all surfaces agree; the N>20 divergence is closed and pinned by `test_cli_and_tui_pending_queue_match_beyond_default_window` (`025c353e`).
