# Daily-Driver Execution Readiness
# 2026-06-01

**Status: ✅ COMPLETE** - All tickets implemented and shipped (2026-05-31 session)

**Purpose.** Make the backlog *actually executable* by a developer (or an agent) without
re-deriving context, and risk-check the design specs themselves before they are built.
Three parts: (1) dev/test mechanics, (2) per-ticket Definition-of-Done + implementation
pointers, (3) the **spec-level risk register** (risks introduced *by* building the
specs — not previously assessed).

---

## Part 1 — Dev & verification mechanics (verified from `pyproject.toml`)

- **Python:** `requires-python = ">=3.10"`.
- **Tests:** `pytest` with `testpaths = ["tests"]`. Run a single new test e.g.
  `pytest tests/path/test_chat_repl_displays_answer.py -q`.
- **Lint/type:** `ruff` (`[tool.ruff]`) and `mypy` are configured; run before commit.
- **Docs/acceptance regen:** `scripts/build_acceptance_status.py`, `scripts/build_docs.py`
  (recent commits emphasize *deterministic* doc/test verification — keep it deterministic).
- **No Makefile** — invoke tools directly.
- **Manual smoke:** `teaagent chat` and `teaagent tui` (use injected `input_fn`/`output_fn`
  in tests; real TTY for the smoke). The `verify` and `run` skills can drive the app.

**Definition of "done" for any ticket:** new test(s) green · `ruff` clean · `mypy`
clean · manual smoke shows corrected behavior · no acceptance regression.

---

## Part 2 — Per-ticket execution sheets (P0/P1)

### ✅ TICKET-1 / P0-1 — CG-01 (REPL result handling)
- **File:** `teaagent/cli/_handlers/chat_repl.py` ~`:816-827`.
- **Exact change:** replace `if result != 0:` with branching on `result.status`; on
  `'completed'` print `result.final_answer.content`; else print
  `result.error_message`. Append `{task, result, cost_cents: result.cost_cents}` to
  `session_context['observations']`.
- **Reference impl:** the initial-task path at `:557-570` and TUI `:859-861` already do
  this correctly — mirror them.
- **DoD checklist:** [ ] success prints answer, no "Task failed" [ ] failure prints real
  error [ ] observation appended [ ] `test_chat_repl_displays_answer` green.

### ✅ TICKET-2 / P0-2 — CG-02 (destructive undo)
- **File:** `chat_repl.py:418` and fallback `:789-799`.
- **Exact change:** remove both `git checkout -- .` calls. Route `/undo` to the run's
  `UndoJournal` (see TUI `:779-782`); if nothing recoverable, print "nothing to undo".
- **DoD checklist:** [ ] manual edit to A preserved when undoing a run that touched B
  [ ] no-checkpoint case is a byte-identical no-op [ ] `git checkout -- .` removed
  [ ] `test_chat_repl_undo_scope` green.

### ✅ TICKET-3 / P1-1 — CG-03 (real cost)
- **Files:** `chat_repl.py:563,825` (remove `+= 10`); `tui/__init__.py:_run_agent_task`
  (increment `self._session_cost_cents += result.cost_cents`).
- **DoD:** [ ] stub cost `137¢` → `/cost` shows `$1.37` [ ] sums across tasks
  [ ] tokens shown [ ] parity REPL/TUI [ ] `test_session_cost_real` green. **DQ-5** (source label).

### ✅ TICKET-3b / CG-09 + CG-10 — `/background` honesty + audit (NEW from second pass)
- **File:** `chat_repl.py::suspend_to_background` (`:32-151`), caller `:640-658`; TUI
  `_handle_background` `:717-720`.
- **Exact change:** (a) do not leave the user on a new branch — either restore HEAD or
  state the switch explicitly; (b) align the printed messages with reality (no
  background execution unless wired to `agent run --detach`); (c) emit a real audit
  event via `AuditLogger` for the suspension.
- **DoD:** [ ] no silent branch switch [ ] messages match behavior [ ] suspension
  emits an audit-chain event [ ] `test_background_audited_and_honest` green. **DQ-1.**

### ✅ TICKET-5 / P1-3 — CG-05 (shared controller) — DO EARLY
- **Sequencing note (from second pass):** CG-05 is the root cause that keeps spawning
  bugs (CG-09 is fresh proof). Recommend doing P0-1/P0-2 directly, then P1-3 *before*
  P1-1/P1-2/CG-09 so those land once in the shared `ChatSessionController`.
- **DoD:** [ ] both surfaces drive one controller [ ] `test_chat_surface_parity` green
  [ ] CG-01/02/03/09 behavior identical across surfaces. **Human review required.**

### ✅ TICKET-6 / P1-4 — CG-06 (no clear-screen) — **DQ-3** (cheap vs full layout).
### ✅ TICKET-7 / P2-1 — CG-07/CG-08 (one undo vocabulary) — **DQ-6**.

---

## Part 3 — Spec-level risk register (risks introduced BY building the specs)

Previously unassessed. Each design spec, when implemented, carries its own risk.

| ID | Spec | Risk if built naively | Likelihood | Impact | Mitigation |
|----|------|-----------------------|:----------:|:------:|-----------|
| **SR-1** | provider-resilience | Auto-fallback **masks a real outage**, so operators don't notice a degraded provider | Med | Med | Surface `fallback_used` loudly in cockpit + evidence; alert, don't hide |
| **SR-2** | provider-resilience | Fallback to a model with broader default tools **widens risk** | Med | High | Hard invariant + `test_no_silent_downgrade`; carry permission profile unchanged |
| **SR-3** | mcp-trust | `revoke` mid-run **breaks a running automation** that depended on the tool | Med | Med | Revoke takes effect on *next* resolution; in-flight call completes or fails closed with a clear error |
| **SR-4** | mcp-trust | Token-expiry handling introduces a re-auth loop that **blocks unattended runs** | Med | Med | Background runs fail closed with an actionable status, not an infinite prompt |
| **SR-5** | automation-lifecycle | `transfer`/`expire` **drops audit lineage** → accountability hole | Low | High | Lineage-preservation is an acceptance test (`test_automation_transfer_preserves_lineage`) |
| **SR-6** | activation-explainability | Session-scoped `--disable-skill/hook` **abused to silence a safety hook** | Low | High | Disallow disabling security/approval hooks; log every disable to audit |
| **SR-7** | cockpit | Single `CockpitState` producer becomes a **performance hot path** (recomputed often) | Med | Low | Cache snapshot; cockpit reads, never recomputes per render |
| **SR-8** | repo-map benchmark | Gate is **flaky** across model/tooling updates → CI noise, gets ignored | Med | Med | Relative-to-baseline thresholds (DQ-REPO-3); nightly before release-gate |
| **SR-9** | run-evidence | Evidence bundle **trusted as proof while itself buggy** (e.g. miscounts files) | Med | Med | Derive only from undo-journal/audit (never narration); `tamper_suspected` flag |
| **SR-10** | ide-desktop | HTTP surface exposed beyond loopback **without auth** | Low | High | Loopback default + `test_http_surface_loopback_default`; warn on non-loopback |
| **SR-11** | evidence/cost | Building on CG-03's cost before P1-1 lands → **evidence shows fake economics** | High | Med | Gate SPEC-EVB economics on TICKET-3 (dependency already noted) |

---

## Pre-flight checklist (run before starting any phase)

- [ ] Re-anchor `file:line` refs against current HEAD (R-5).
- [ ] Confirm the relevant `RunResult`/`AuditLogger`/`UndoJournal` APIs unchanged.
- [ ] Decide the gating `DQ-#` for the phase (see open-decisions register).
- [ ] Write the test first (each ticket names it) — falsifiable before code.
- [ ] For P1-3 and TICKET-2/3b: schedule human review (data/governance surface).

## Recommended execution order (single source of truth)

1. **TICKET-1, TICKET-2** (P0, no refactor) → ship.
2. **TICKET-5** (shared controller) → unify.
3. **TICKET-3, TICKET-3b, TICKET-4, TICKET-6** fold into the controller.
4. **TICKET-7** (vocabulary) cleanup.
5. Spec-track (8–11 + the 3 final specs) as prioritized, each gated by its `SR-#`.

## Cross-references

- Findings: `daily-driver-code-grounded-ux-findings` + `daily-driver-findings-second-pass`.
- Backlog: `daily-driver-backlog-2026-06-01.md`. Decisions: `daily-driver-open-decisions`.
- Risk (product/execution): `daily-driver-risk-register-2026-06-01.md` (PR/ER); this doc
  adds the **SR-#** spec-level layer.
</content>
