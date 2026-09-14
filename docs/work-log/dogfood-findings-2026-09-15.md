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
- Adjudication of G1–G14 + D1 — each is a `feat:`/design change or a verdict, not a dogfooding step.
