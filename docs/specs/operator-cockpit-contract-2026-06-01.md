# Operator Cockpit Contract (CLI / TUI / Dashboard parity)
# 2026-06-01

**Fills:** Gap **F-ECO-010** — *"define an operator cockpit contract, then test
CLI/TUI/dashboard parity for the same run state."* The cockpit answers one question
across every surface: **"What is running, what is blocked, what changed, what is it
costing, what needs approval, what can be undone?"**

**Grounding.** The data already exists in three places that today render
*inconsistently*:
- `teaagent/daily.py::build_daily_brief` → readiness, recent runs, harness health,
  pending approvals, recommendations.
- `teaagent/tui/__init__.py::_print_state_panel` → provider/model/root/permission
  mode/destructive/chat, parallel experiments, last 3 runs, last 3 memories.
- `teaagent/ergonomics/run_summary.py::summarize_run` → per-run tools/files/cost/undo.

This contract defines the **single canonical cockpit model** all three must project
from, so parity is testable rather than hand-maintained (root cause: CG-05/CG-06).

---

## Cockpit model (the shared source of truth)

```
CockpitState
├── identity        provider, model, route_model, root, permission_mode, destructive
├── readiness       ready: bool, warnings: [str]          (from daily.build_readiness)
├── harness_health  healthy: bool, failures: [str]        (build_harness_health_report)
├── running         [{run_id, status, started_at, heartbeat_live}]
├── blocked         [{run_id, pending_approval: {tool, call_id, blast_radius}}]
├── budget          session_cost_usd, cap_usd, remaining_usd, tokens_in, tokens_out
├── last_run        run_summary (summarize_run output)
├── recoverable     [{run_id, files_changed_count, undo_command}]
└── memory          recent: [{id, content_preview}], pending_review_count
```

Every field maps to an existing producer; the contract is to **compute once** and
render per surface, not recompute per surface.

---

## Required fields by surface (parity matrix)

| Field | CLI `daily` | TUI panel | Dashboard | Notes |
|-------|:-----------:|:---------:|:---------:|-------|
| identity | ✓ | ✓ (`_prompt`) | ✓ | TUI already shows in prompt |
| readiness | ✓ | ⚠ partial | ✓ | TUI panel omits readiness warnings |
| harness_health | ✓ | ✗ | ✓ | **missing in TUI panel** |
| running | ⚠ (recent only) | ⚠ (last 3) | ✓ | neither distinguishes *running* from *done* |
| blocked (approvals) | ✓ (warnings) | ✗ | ✓ | **TUI panel hides pending approvals** |
| budget | ✓ | ✗ (fake, CG-03) | ✓ | must use real `cost_cents` (P1-1) |
| last_run summary | ✗ | ✗ | ✓ | CLI/TUI show JSON, not the formatted summary |
| recoverable | ✗ | ✗ | ⚠ | **no surface lists what is undoable** |
| memory | ✗ | ✓ (last 3) | ✓ | — |

**Legend:** ✓ present · ⚠ partial/inconsistent · ✗ absent.

The matrix shows the cockpit is *most* complete on CLI `daily` and *least* on the TUI
panel — yet the TUI panel is the always-on surface (and the one that clears the screen,
CG-06). That inversion is the core F-ECO-010 problem.

---

## Behavioral requirements

1. **Single computation.** `build_cockpit_state(root) -> CockpitState` is the only
   producer; CLI/TUI/dashboard are pure renderers. (Enables parity testing.)
2. **Never destroy context to show state.** The cockpit must render without a
   clear-screen (fixes CG-06); on a TTY it uses a fixed region, not `\033[2J`.
3. **Blocked is loud.** Pending approvals appear in every surface's cockpit — a blocked
   run is the single most actionable state.
4. **Recoverable is explicit.** Every surface can answer "what can I undo right now?"
   with the exact `undo_command` (already produced by `summarize_run`).
5. **Budget is real.** Cockpit budget reads `RunResult.cost_cents` accumulation, never
   placeholders (depends on hardening P1-1).

---

## Acceptance

- `test_cockpit_state_single_source`: CLI `daily`, TUI panel, and dashboard render from
  the same `CockpitState` instance → identical values for every field in the matrix.
- `test_cockpit_shows_blocked`: a run with a pending approval appears in `blocked` on
  all three surfaces.
- `test_cockpit_no_clear_screen`: TUI cockpit render emits no clear-screen sequence.
- `test_cockpit_recoverable_matches_undo_journal`: `recoverable` entries match the undo
  journals present under `.teaagent/undo/`.

## Dependencies & sequencing

- Depends on hardening **P1-3** (shared controller) for the budget/cost field and
  **P1-4** for the no-clear-screen requirement.
- Independent of MCP/cloud work; can ship for local CLI/TUI first, dashboard second.

## Non-goals

- Not a real-time streaming dashboard rewrite. The contract is about *parity and
  completeness of the same snapshot*, not new visualization.
</content>
