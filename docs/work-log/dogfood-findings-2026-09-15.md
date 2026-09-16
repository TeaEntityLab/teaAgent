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
| G34 | **`consensus` is non-functional end-to-end: peers write to disk but the engine reads in-memory.** `consensus peers add/activate` persist to `root/.teaagent/peers.json` (`_consensus.py:36,65`), but `consensus status`/`request`/`vote`/`wait`/`cancel`/`history` all build the engine via `_consensus_engine_from_args` (`_consensus.py:297-304`) which constructs `PeerRegistry(storage_path=None)` → in-memory, always empty. After `peers add` + `activate`, `consensus status` still reports `Active peers: 0` and `consensus request` fails `No active peers available`. The whole consensus flow can never see a registered peer. |
| G35 | **`mcp serve` dies on an unknown `tools/call` instead of returning a JSON-RPC error.** Calling `tools/call` with an unregistered tool name raises `Unexpected error: "tool 'X' is not registered"` and kills the server — no JSON-RPC error frame is emitted, the connection just drops. A valid `tools/call` (`workspace_read_file`) works. The server should return a JSON-RPC `-32601`/`-32602` error and stay alive. |
| G36 | **`agent automation add` crashes on an unsupported schedule string.** A cron-style schedule (`*/5 * * * *`) raises `Unexpected error: unsupported schedule; use 'every 30m', 'every 2h', or 'daily HH:MM'` rc=1 — a user-input validation error surfaced as an uncaught crash instead of a clean `{"status":"error"}` like sibling subcommands. |
| G37 | **`agent automation` lookup is by `automation_id` only — the `name` is stored but never usable.** `automation add myauto` succeeds and `list` shows `name: "myauto"`, but `run`/`pause`/`resume`/`delete`/`show` all report `automation 'myauto' not found`. Only the hex `automation_id` (`68b44cd4…`) works. The name is a write-only field — the CLI's own UX implies name-based lookup but never implements it. |
| G38 | **`init`/`setup` crash on EOF when stdin is not a TTY.** Both prompt `Select provider … [gpt]:` via `input()`; with no TTY (piped/headless) `input()` raises `EOFError` → `Unexpected error: EOF when reading a line` rc=1. They should detect non-interactive stdin and either use the default or print a clean "requires a TTY" error. |

## Denial candidate (owner adjudication)

| # | Candidate |
|---|---|
| D1 | 1 `subagent_launch` denial in the H4 shadow receipts — needs owner verdict (false-positive classification is owner-only per ADR-0031 exit criterion 1). |


## H4 evidence produced (B2 complete)

- `prepare_h4_evidence.py --since 2026-08-13 --until 2026-09-15`: **9 observed** `h4_governance_shadow` events (8 `approval` + 1 `subagent_launch`), 21 reachable runs, 7,779 total, verdict `needs_review` (up from `unexercised`/0).
- `build_h4_decision_packet.py`: **4/5 criteria `prepared`** (false-positive window, coverage, perf SLO, rollback); only criterion 4 (human sign-off) `human_required`. `promotion_ready: false`.

## What remains owner-only

- ADR-0031 sign-off (criterion 4) — the packet is prepared, not passed: 4/5 `prepared` means agent preparation, and criterion 1 still needs the owner D1 verdict plus a real production window.
- The owner-driven TUI dogfood session (`m4-dogfood-2026-09-15.md`) — the one surface agents can't drive.
- ~~Adjudication of G23–G38~~ — **done**: owner adjudicated "Yes for all" on 2026-09-16 and every prescribed fix has landed (see "Landed behavior" table). G1–G22 adjudicated 2026-09-15 and implemented (G11/G12/G13 owner-declined; G34 held for ADR-0043 review). **D1 stays deferred** — owner verdict only.

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

## Owner adjudication triage for G23–G38 (agent-proposed, 2026-09-16)

Same contract as the G1–G22 triage above: proposals only, the owner assigns
the gate, nothing here is scheduled. `friction-driven` is not proposed — no
owner friction-log entry cites these. Reasoning, acceptance criteria, and
counterarguments: `docs/reviews/roadmap-rethink-2026-09-16.md` §3.5 and §5.
Uncaught-crash rows cite the operating rule that tool/CLI errors must be
actionable and classified (AGENTS.md, Tool Governance).

| # | Proposed provenance | Owner decision needed | Suggested disposition |
|---|---|---|---|
| G23 | `owner-override` (first-run ergonomics; `friction-driven` if the owner logs it) | Should `init --provider fake` skip the API-key prompt, and should non-TTY stdin fail before any config is written? | Skip the key prompt for providers that need none; fail fast with a classified error when stdin is non-interactive and a required value is missing; never silently select a credentialed provider |
| G24 | `owner-override` (ergonomics) | Should `init`/`setup` next-steps explain the workspace-write plan gate? | Print the `plan` → `--from-plan` path in next-steps; do not recommend `--skip-plan-check` as the default |
| G25 | `owner-override` (ergonomics; low) | Should the default `release evidence` profile announce/progress its expensive gates? | Progress output for the pre-commit + acceptance tiers; no gate weakened or skipped |
| G26 | `governance-gap` (run-list/receipt output contract) | Is the scratchpad entry part of the run-array schema? | Move `scratchpad_last_goal` out of the run array in `runs list`, `session list`, `agent status`; pin with an output-contract test |
| G27 | `governance-gap` (classified-error rule; distinct from owner-rejected G11 wrong-key semantics) | Should a missing `TEAAGENT_MCP_TRUST_KEY` be a classified CLI error? | Classified error naming the env var; G11 silent-discard semantics untouched |
| G28 | `governance-gap` (audit surface contract) | Should bare `audit verify` require `<run_id>`/`--path`, or verify every run log under `.teaagent/runs/`? | Decide the contract first; either require the argument up front or add a bounded all-runs mode; never report success over a nonexistent default |
| G29 | `governance-gap` (git sandbox is the undo/rollback safety boundary and silently self-disables) | Should `init`/`setup` add `.teaagent/` to `.gitignore` in git repos, or should untracked runtime files stop counting as a dirty worktree? | Explicit, non-destructive `.gitignore` offer during init (never auto-stash or discard), or sandbox-neutral treatment of `.teaagent/`; risk review before code |
| G30 | `owner-override` (offline smoke-provider correctness) | Should `fake` be classified no-network for connectivity checks? | Mark `fake` as needing no network so `preflight`/`plan`/`daily` pass offline; no DNS lookup for it |
| G31 | `governance-gap` (plan gate is an approval-class gate the background worker must honor) | Should the worker inherit the foreground plan flags verbatim? | Forward `--from-plan`/`--require-plan`/`--skip-plan-check` in `build_agent_run_command`; pin with a workspace-write background run that produces a run; no blanket bypass |
| G32 | `governance-gap` (classified-error rule; uncaught `TypeError`) | — | Wrap the root in `Path()` inside `from_workspace_config` (matching `FailureCardStorage`); regression test with a string root |
| G33 | `governance-gap` (classified-error rule; inconsistent not-found contract) | — | Return the sibling `{"status":"error","message":...}` shape from `skill candidate install` |
| G34 | `legacy-competitive` (ADR-0043 quarantine; disposition evidence only) | Does this defect change the 2026-12-09 delete-vs-promote disposition? | No repair in a routine batch; carry as evidence into the ADR-0043 expiry review |
| G35 | `governance-gap` (classified-error rule; server availability under invalid input) | Should an unknown-tool `tools/call` return the implemented MCP error frame and keep serving? | Catch the unregistered-tool error in `_call_tool`, return the contract-appropriate JSON-RPC error, stay alive; test an invalid call followed by a valid call on one connection |
| G36 | `governance-gap` (classified-error rule; user input) | — | Validate the schedule in `automation add`, return `{"status":"error"}`, persist nothing; no cron support implied |
| G37 | `owner-override` (ergonomics proposal — `automation run --help` requires `automation_id`, so not a demonstrated contract defect) | Is name lookup wanted, and what happens on duplicate names? | If wanted: resolve unique names to IDs, error on ambiguity, keep ID behavior unchanged |
| G38 | `owner-override` (first-run ergonomics; overlaps G23) | On non-TTY stdin, should `init`/`setup` use documented defaults or fail with "requires a TTY"? | Detect non-interactive stdin and fail fast with a classified error unless every required value comes from flags; document the flag path |

D1 stays deferred (owner verdict). Its receipt is orphan-sourced
(`pending-1061f13779524cb9b8763a9a2d130e7d.jsonl`, parent run `b15ffcfb…`);
see the 2026-09-15 erratum in `roadmap-status.md` before classifying.

## Owner decisions (2026-09-16) — G23–G38

Owner adjudicated the G23–G38 triage in one batch: **"Yes for all"** — every
proposed provenance and suggested disposition above is adopted as written
(9 `governance-gap`, 6 `owner-override`, G34 `legacy-competitive` held). D1
stays deferred. Risk record: `docs/reviews/dogfood-g23-g38-2026-09-16-risk.md`.

Implemented 2026-09-16 (seven parallel slices, integrator-reviewed; each
finding has a `# test-type: behavior` regression that failed pre-change):

| # | Landed behavior | Proof |
|---|---|---|
| G23 | `init --provider fake` never prompts for a key (`ProviderConfig.requires_api_key=False`); non-TTY key-requiring providers proceed with `api_key_note` instead of crashing | `tests/test_dogfood_first_run_g23_g38.py`; scratch `init --provider fake </dev/null` → `ok: true`, no prompt |
| G24 | `workspace-write` `next_steps` add `agent plan …` → `agent run … --from-plan …`; never `--skip-plan-check` | same file |
| G29 | `init`/`setup` append `.teaagent/` to `.gitignore` in git repos (`--no-gitignore` opt-out; `gitignore: added\|present\|skipped\|not-a-git-repo`); first next step tells the user to commit the scaffold because the sandbox refuses an untracked-file worktree | scratch: `gitignore: added`; after committing the scaffold, `agent run fake` prints `Safe git sandbox auto-enabled`, completes, `git status --porcelain` empty |
| G30 | `fake` is `requires_network=False`: connectivity + loopback-bind checks skipped, no DNS | `check_provider_connectivity('fake')` with sockets patched to raise → ready; scratch preflight `ready: true` |
| G38 | non-TTY `init`/`setup` without `--provider` → `{"ok": false, "message": "provider is required in non-interactive mode; pass --provider <name> …"}` rc=1 before any write | scratch: rc=1, directory contains only `.git` |
| G31 | worker argv forwards `--from-plan`/`--require-plan`/`--skip-plan-check` (and `--allow-external-plan`); `--from-plan` without a positional task no longer crashes the parent | `tests/test_dogfood_background_plan_g31.py`; scratch workspace-write background run produced a `run_id`, log has no `PLAN_GATE` |
| G26 | scratchpad pseudo-entry removed from `runs list` / `session list` / legacy `agent_status.py` arrays; hint printed only in human/TTY output | `tests/test_dogfood_run_list_schema_g26.py`; scratch `runs list` → every element has `run_id` |
| G35 | unknown `tools/call` → JSON-RPC `-32602` (`tool 'X' is not registered`), session keeps serving; catch narrowed to the registry lookup | `tests/test_dogfood_mcp_errors_g27_g35.py`; scratch: 3 frames, second `error.code -32602`, third `isError false` |
| G27 | `mcp trust allow/deny` without `TEAAGENT_MCP_TRUST_KEY` → `{"ok": false, "error": "TEAAGENT_MCP_TRUST_KEY is not set; …"}` rc=1; wrong-key (G11) semantics untouched | same file |
| G32 | `MemoryAutoInvalidationConfig.from_workspace_config` wraps `Path(root)` | `tests/test_dogfood_memory_skill_errors_g32_g33.py`; scratch `memory failures auto-invalidate` → `status: ok` |
| G33 | `skill candidate install <missing>` → `{"status": "error", "message": "… not found"}` rc=1 | same file |
| G36 | `automation add` validates the schedule before persisting → classified error, nothing written | `tests/test_dogfood_automation_cli_g36_g37.py` |
| G37 | `show/pause/resume/delete/run` accept an id or a unique name; ambiguous → `ambiguous automation name 'x': ids …` | same file; `--help` says `Automation id or unique name` |
| G28 | bare `audit verify` without a legacy `.teaagent/audit.jsonl` → classified error naming `.teaagent/runs/` and the `<run_id> \| --path` usage, before any verification | `tests/test_dogfood_audit_release_g25_g28.py`; scratch rc=1 |
| G25 | `release evidence` (release/full) prints `[release evidence] running: … / done in …` on stderr around the two 900 s gates; stdout unchanged; counts-only silent | same file (subprocess stubbed; live run deliberately not exercised) |
| G34 | held — no change | ADR-0043 expiry review 2026-12-09 carries this defect as disposition evidence |

Residuals recorded, not fixed: `ultrawork start` (deprecated) hand-rolls an
`agent run` argv without plan flags — left deferred; the command is deprecated
and points users at `agent run`, so forwarding plan flags there is scope creep.
The legacy unimported `cli/_handlers/agent_automation.py` was deleted in
`4f69f71f` (it carried the pre-fix G36/G37 code paths as a grep-trap).
The remaining residuals are now closed (2026-09-17): `automation
promote`/`status` route through `_resolve_automation_selector` like their
G37 siblings; `setup` has the `--no-gitignore` opt-out `init` already had;
and the NUL-byte `--api-key` crash is fixed in `fd5be772` — the key is
validated before any config write, so `init` returns a classified
`{"ok": false}` with no partial `.teaagent/`; the wizard's
`resolve_api_key` raises a `ValueError` its caller converts to a warning.
H4 evidence is unchanged by this batch (fake-provider probes make no
governed tool calls). `promotion_ready` stays `false`.

Follow-up hardening (same day, reviewer advisories): `mcp trust revoke` now
carries the same missing-key guard as allow/deny (the G27 twin, fixed rather
than listed); `handle_mcp_request` contains any unexpected exception in one
request as JSON-RPC `-32603` and keeps serving (stdio and HTTP), on top of the
precise `-32602` for unknown tools; the `init`/`setup` gitignore step reports
`error: <reason>` instead of raising when `.gitignore` cannot be read or
written, and EOF at its `[Y/n]` prompt counts as `skipped` — init still
completes with config written. Live re-check: `init`/`setup` with and without
`--provider`, on a git repo and a plain directory, all headless — classified
error and no files left when the provider is missing; `gitignore: added` /
`not-a-git-repo` otherwise; no `Unexpected error` on any path.

Twin sweep, 2026-09-16 (G38 crash class): the five `doctor … --wizard` flows
(`mcp`/`project`/`providers`/`aigateway`/`model`, the last reachable straight
from `init`'s `next_steps`) called bare `input()`/`getpass` and hit the same
`EOFError → "Unexpected error"` dead end on exhausted (`</dev/null`) stdin. A
shared `guard_wizard_eof` decorator
(`teaagent/cli/_handlers/_doctor/_wizard_io.py`) now catches the `EOFError` and
returns a classified `{"ok": false, "error": "… needs interactive input …"}`
(rc 1); provided/piped answers still work, so the existing wizard tests that
mock `input`/`getpass` keep passing. (First cut used an `isatty` pre-guard;
the full suite showed it wrongly blocked the mocked/piped path, so it was
replaced with the EOF catch — same lesson as the TUI setup fix below.)
Regression `tests/test_dogfood_doctor_wizard_tty_g38_twin.py` (5 wizards + the
decorator). Gate `governance-gap` (AGENTS.md: tool/CLI errors must be
actionable and classified).

Twin sweep, 2026-09-17 (path-probe crash class): Python 3.12's
`Path.is_file()`/`exists()` re-raise `OSError` for `ENAMETOOLONG`/`EACCES`
(only the `ENOENT` family is swallowed), so user-derived paths — an over-long
`run_id`, an explicit `--config`, `suspension-<run_id>.json`, the default
audit log, `--ssh-key-file` — reached the generic `Unexpected error` handler
instead of a classified not-found. Fixes: `RunStore.run_exists`/`undo_exists`
safe probes with every `run_id`/`undo_path` call site routed through them
(`10b99b62`, `2d9a8224`); `_is_accessible_file` for config resolution plus a
guarded explicit-`--config` read that warns and falls back to defaults
(`6f35272b`, `7e7e489e`); suspension/audit-log probes guarded (`7e7e489e`);
`--ssh-key-file` classified (`d91c2530`). Regression
`tests/test_run_store.py::test_pathological_run_id_is_graceful_not_a_crash`
(`37a2db10`) feeds `'x'*1000` through the store probes and the
`agent show`/`resume`/`undo`/`replay steps` surfaces — exit 1, "not found",
no "Unexpected error". Gate `governance-gap` (same classified-error rule as
the G38 twin). Full suite 6752 passed / 0 failed.
