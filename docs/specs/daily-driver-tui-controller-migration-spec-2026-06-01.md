# TUI → ChatSessionController Migration Spec
# 2026-06-01

**Why.** CG-12 (third-pass audit) found the TUI never adopted `ChatSessionController`,
so the CG-01/02/03 fixes don't reach the always-on surface (CG-11 cost = $0.00, CG-15
undo divergence). This spec defines *how* to migrate `TeaAgentTUI._run_agent_task` onto
the controller **without regressing** the TUI's richer behavior — because a naive
"just call the controller" would break streaming output, run-summaries, and JSON mode.

**What.** A capability contract for `ChatSessionController` so one code path can serve
both surfaces, plus an ordered migration that keeps each step shippable and tested.

**Done.** TUI `_run_agent_task` produces its result/cost/undo via the controller; a
parity test asserts REPL and TUI agree on result handling, cost accumulation, and undo;
no double-printed answers; JSON mode and run-summaries preserved.

---

## 1. Capability gap (grounded)

`ChatSessionController.execute_task` today (`chat_session_controller.py:77-180`) accepts:
`task, config, adapter, audit, undo_journal, initial_observations, resumed_from`. It
**always** prints the answer via `output_fn` (`:162-165`) and returns `ExecutionResult`.

`TeaAgentTUI._run_agent_task` (`tui/__init__.py:842-970`) does materially more:

| Capability | Controller | TUI `_run_agent_task` | Migration implication |
|---|---|---|---|
| Streaming `on_chunk` | carried via `config` ✅ | sets `config.on_chunk` (`:903`) | OK — config-borne, no controller change |
| Approval handler | carried via `config` ✅ | `config.approval_handler` (`:905`) | OK — config-borne |
| Budget prompt handler | carried via `config` ✅ | `config.budget_prompt_handler` (`:906`) | OK — config-borne |
| `task_spec` (clarify) | **not forwarded** ❌ | builds + passes `task_spec` (`:864,918`) | **Add `task_spec` param to `execute_task`** |
| Model routing | none | `route_model(...)` (`:866-871`) | Keep in surface; pass resolved model in `config` |
| `run_summary` render | none (prints raw answer) | `summarize_run`+`format_run_summary` (`:932-960`) | Controller must **not force** answer output |
| JSON payload (non-chat) | none | `_print_json(payload)` (`:962-970`) | Surface renders; controller returns `RunResult` |
| Chat-session persistence | none | appends `ChatMessage`, saves (`:944-956`) | Keep in surface (post-run hook) |
| Progress sink | none | `audit.add_sink(self._progress_sink)` (`:877`) | Pass pre-wired `audit` into `execute_task` ✅ |

**Conclusion:** the only controller change required is (a) forward `task_spec`, and (b)
make answer output **optional** so the surface owns rendering. Everything else the TUI
needs already travels inside `config`/`audit`, both of which `execute_task` accepts.

## 2. Proposed controller changes (minimal, back-compat)

1. **Add `task_spec: Optional[str] = None`** to `execute_task`; forward to
   `run_chat_agent(..., task_spec=task_spec)`.
2. **Add `emit_answer: bool = True`** (or `render: Callable | None`). When `False`, skip
   the `:162-165` block and let the caller render from `ExecutionResult.run_result`. The
   REPL keeps `True` (no behavior change); the TUI passes `False` and renders its
   run-summary / JSON exactly as today.
3. **(Optional) Return cost/observation deltas** already present on `ExecutionResult` —
   no change needed; the TUI reads `result.cost_cents` and `session_state`.

These are additive, default-preserving — TICKET-1/3/3b REPL behavior is untouched.

## 3. Migration steps (each shippable)

1. **Stop-gap (independent, 1 line):** in `_run_agent_task`, after the run, add
   `self._session_cost_cents += result.cost_cents`. Closes CG-11 immediately even before
   the controller migration. Guard with TICKET-14's accumulation test.
2. **Controller grows** the two params in §2; REPL unchanged; add
   `test_controller_task_spec_forwarded` and `test_controller_emit_answer_false_silent`.
3. **TUI delegates the run:** replace the `run_chat_agent(...)` call (`:890-923`) with
   `self._controller.execute_task(task, config=cfg, adapter=adapter, audit=audit,
   undo_journal=undo_journal, task_spec=task_spec, initial_observations=...,
   resumed_from=..., emit_answer=False)`. Keep all post-run rendering (`:924-970`) as-is,
   reading from `result.run_result`. The TUI holds one `ChatSessionController` whose
   `session_state` is the source of truth for cost (drop the standalone
   `self._session_cost_cents`, or make it a property over `session_state`).
4. **TUI `/undo` delegates:** route `_handle_undo` to `controller.undo_last_run()`,
   keeping git-stash `_restore_checkpoint` only as an explicit `checkpoint restore`
   verb (closes CG-15 + aligns with TICKET-7's "one undo vocabulary").
5. **Parity test:** `test_chat_surface_parity` runs the same stub task through REPL and
   TUI controllers and asserts identical result-handling, cost accumulation, and undo.

## 4. Parity contract (the invariant after migration)

> For a given (task, config, adapter, audit), REPL and TUI MUST produce the same
> `RunResult.status`, the same `session_cost_cents` delta, and the same undo outcome.
> Surfaces may differ ONLY in *rendering* (TUI run-summary/JSON vs REPL plain text).

Encode as `test_chat_surface_parity`; treat a parity break as a release blocker.

## 5. Risks (migration-specific)

| ID | Risk | Mitigation |
|----|------|-----------|
| MR-1 | Double-printed answer (controller + TUI both emit) | `emit_answer=False` for TUI; covered by `test_controller_emit_answer_false_silent` |
| MR-2 | Dropping `self._session_cost_cents` breaks the display tests that inject it | Update CG-16 tests to drive accumulation, not injection (TICKET-14) |
| MR-3 | `task_spec`/clarify path regresses | `test_controller_task_spec_forwarded`; keep clarify in the surface, pass only the built spec |
| MR-4 | Progress sink / streaming lost in delegation | Pass the pre-wired `audit` (already supported); assert a chunk is emitted in a stream test |
| MR-5 | Hidden coupling via `session_state` shared mutable set | Controller owns one `SessionState`; surface reads, never mutates directly |

## 6. Cross-references
- Findings: `daily-driver-third-pass-postfix-audit-2026-06-01.md` (CG-11…CG-16).
- Tickets: TICKET-12 (this migration), TICKET-14 (tests), `daily-driver-backlog-2026-06-01.md`.
- Parity matrix: `daily-driver-surface-parity-matrix-2026-06-01.md`.
- Controller: `teaagent/chat_session_controller.py`. TUI: `teaagent/tui/__init__.py:842`.
