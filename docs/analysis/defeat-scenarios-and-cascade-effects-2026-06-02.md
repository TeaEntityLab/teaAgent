# Defeat Scenarios & Cascade Effects
# teaagent — 2026-06-02

**Why.** Bugs become dangerous at different rates depending on how they fail, how loudly,
and what they break downstream. This document maps every open defect through seven lenses
(user-facing failure, internal state, defeat paths, cascade effects, silent failures,
data-corruption risk, integration gaps) and ends with a prioritised decision matrix.

**Scope.** All items with status `OPEN` or `OPEN(test)` in
`daily-driver-findings-status-ledger-2026-06-01.md`, plus the UXD contract-drift items from
`daily-driver-ux-contract-drift-2026-06-01.md`. Items confirmed FIXED are omitted.

**Source abbreviations.** CG = code-grounded finding; AG = agent-mode audit; UXD = UX
contract drift. Code references are anchored to HEAD as of the ledger date.

---

## Part 1 — Per-Defect Defeat Analysis

---

### DS-01 · CG-11 — TUI `/cost` and budget bar always show $0.00

**Ticket:** TICKET-12 (stop-gap: 1 line). **Severity:** P1.

**User-facing failure.**
The user runs one or more expensive tasks in `teaagent tui`. `/cost` and the budget display
always show `$0.00`. The user cannot judge cumulative spend and may trigger substantially
more work than intended, assuming the session has been cheap.

**Internal state — root cause.**
`TeaAgentTUI._session_cost_cents` is initialised to `0.0`
(`tui/__init__.py:186`) and is never written. `_run_agent_task` reads
`result.cost_cents` only to pass it to the run-summary formatter (`:938`); there is no `+=`
anywhere in the file (`grep '_session_cost_cents *+=' tui/__init__.py` → no matches). The
REPL fixed this via the controller (`chat_session_controller.py:168`), but the TUI was
never migrated.

**Defeat paths.**
- Any session that executes at least one task triggers this. There is no threshold or
  special action required.
- A long session with many tool calls magnifies the gap between displayed cost and real
  spend.
- A user who sets `--max-estimated-cost-cents` trusts the budget bar to warn them at 80 %
  and 90 % thresholds — those warnings never fire because the accumulator never rises.

**Cascade effects.**
1. *Budget-guard bypass:* The budget check in `runner/_core.py:142` uses the per-run cap
   passed at run start (`max_estimated_cost_cents`), not the session accumulator. The
   per-run cap does still fire. However, if the user interprets `$0.00` as proof that the
   session is cheap and repeatedly bumps the per-run cap, the session accumulator gives no
   cumulative anchor, enabling unbounded multi-run spend.
2. *CG-12 as amplifier:* Every new controller feature (e.g., a future cost ceiling or
   cost-based throttling) will automatically bypass the TUI for the same reason CG-11
   persists — CG-12 is the structural precondition for any TUI cost bug.
3. *CG-16 (test) masks this:* The passing test suite gives no CI signal. Any refactor that
   accidentally breaks even the display layer won't be caught.

**Silent failure?** Yes. There is no error, no log warning, no indication the counter is
wrong. The display looks correct (it shows a formatted dollar value); only the value is
wrong.

**Data-corruption risk.** Low for the session. High for the user's mental model and
budgeting. No session state is corrupted; only the displayed accounting is wrong. If a
future feature uses `_session_cost_cents` for rate-limiting or soft caps, it would inherit
the zero silently.

**Integration gap (TUI ↔ controller).** This is a direct symptom of CG-12: the REPL and
TUI are on different execution paths, so any fix to the controller does not reach the TUI.

---

### DS-02 · CG-12 — TUI never adopted `ChatSessionController`

> **STATUS: Fixed 2026-06-05** — `tui/__init__.py:996` calls `controller.execute_task()`; controller initialized lazily at `:889`. Cost, undo, and task execution all route through `ChatSessionController`. Tests: `test_tui_uses_chat_session_controller_for_cost_tracking()`, `test_tui_handle_undo_calls_controller_first()` in `tests/test_tui.py`.

**Ticket:** TICKET-12. **Severity:** P1 (root cause, structural).

**User-facing failure.**
Any behaviour fixed in the controller — result display, real cost, surgical undo,
suspension honesty — is silently absent from `teaagent tui`. The TUI appears functional
(it runs tasks and shows output) but delivers a qualitatively different and inferior
experience compared to the REPL, with no indication that it is operating on a diverged
code path.

**Internal state — root cause.**
`chat_session_controller.py` docstring (`lines 3-5`) states it "unifies the execution
logic between CLI and TUI surfaces." In practice, `tui/__init__.py:890` calls
`run_chat_agent` directly, bypassing the controller entirely. Every fix that was
CG-01…CG-10 was applied to the controller; the TUI receives none of them.

**Defeat paths.**
- Opening `teaagent tui` is sufficient. Every task executed there runs on the un-fixed
  path.
- A developer adding a new controller feature and assuming parity is achieved will
  unknowingly leave the TUI on old behaviour.

**Cascade effects.**
CG-11, CG-15, and any future correctness fix are downstream of CG-12. If CG-12 is not
fixed, every future improvement to the controller silently diverges the TUI further. This
is a compounding debt: the longer CG-12 remains open, the larger the migration surface.

**Silent failure?** Yes. The TUI doesn't crash or warn; it simply runs on old logic.

**Data-corruption risk.** Indirect. The TUI's undo path (CG-15) is git-stash-based with a
broader blast radius — an undo in the TUI can restore files the user manually edited after
the checkpoint, which is data loss (not corruption of the store, but loss of the user's
work).

**Integration gap.** This IS the integration gap — the controller/TUI boundary is the
primary structural fault line in the codebase.

---

### DS-03 · CG-13 — Controller silently swallows real errors as "mock detection"

**Ticket:** TICKET-13. **Severity:** P2.

**User-facing failure.**
User completes a task. A save error occurs in `store.logger_for_result(...)` or
`undo_journal.save_to(...)`. The user sees a clean success message. The run is not
persisted to the store, and/or the undo journal is not written. If the user then types
`/undo`, there is nothing to undo — the journal was lost silently. The user assumes the
task ran cleanly and may continue to build on state that was never recorded.

**Internal state — root cause.**
`chat_session_controller.py:143-159` wraps both persistence calls in
`except (AttributeError, TypeError): pass` with comments attributing them to test mocks.
In production, a genuine `AttributeError` or `TypeError` in the store or undo-journal
save path is caught by the same clause and discarded — no log entry, no exception, no
user-visible error.

**Defeat paths.**
- A store path permission error that manifests as `AttributeError` (e.g., a None returned
  by a store method call on a corrupted `.teaagent/` directory).
- A `TypeError` in JSON serialisation of a novel `RunResult` field.
- An OS error that propagates as an attribute miss on the result object.
- Any test-time regression where a real `AttributeError` is introduced in the persistence
  path — it will be invisible in CI too.

**Cascade effects.**
1. *Undo journal silently missing:* the CG-02 fix (surgical undo) becomes a no-op for
   any run where the save is swallowed. `/undo` will fall back to checkpoint restore
   (REPL) or git-stash restore (TUI), both of which have wider blast radii.
2. *Run not in store:* `teaagent agent interactive-review <run_id>` and
   `teaagent resume <run_id>` will fail with "no such run" — indistinguishable from a
   run that never happened.
3. *Audit gap:* if `logger_for_result` fails and is swallowed, the run's result event is
   never written to the audit log. The audit chain appears to have a gap. This could mask
   an incident post-facto.

**Silent failure?** Yes — by design, the except clause suppresses all output. This is the
worst class: a silent failure that masquerades as success.

**Data-corruption risk.** Medium. No bytes are corrupted, but the audit trail has phantom
gaps and the undo journal may be absent for runs that appeared to succeed. This is a
recoverability corruption — the tools exist but the data they need is gone.

**Integration gap.** Test-time mock leakage into the production path. The guard was
written for test convenience and promotes a design where the production path and the test
path are conflated.

---

### DS-04 · CG-14 — Redundant `audit_trail` JSON field on suspension

**Ticket:** TICKET-15. **Severity:** P3.

**User-facing failure.**
A developer or operator inspecting the suspension JSON (`suspension-{id}.json`) sees an
`audit_trail` dict (`:89-93`) and may conclude the real governance record is in that JSON
field. The actual governance event is in the RunStore audit log (CG-10 fix). The JSON
field is a stale snapshot that stopped being meaningful when the real `audit.record` call
was added.

**Internal state — root cause.**
`chat_repl.py:89-93` predates CG-10. The field was the only audit record before CG-10
fixed it. After CG-10, it is vestigial but not removed.

**Defeat paths.**
- An operator writing an incident report reads the JSON field as authoritative — the
  timestamps may diverge if the suspension takes time to write.
- Tooling that parses suspension JSONs and extracts audit data will double-count or
  prefer the wrong source.

**Cascade effects.** Misleads forensic analysis. If combined with DS-07 (AG-01 errors),
the suspension JSON may be the only "record" an operator can find — and it's the stale
one.

**Silent failure?** Yes — no error, but the data is misleading.

**Data-corruption risk.** Low for runtime, medium for forensic accuracy.

**Integration gap.** Suspension JSON ↔ RunStore audit log: two records now exist for the
same event with different timestamps and fields. No reconciliation logic.

---

### DS-05 · CG-15 — TUI and REPL `/undo` use different mechanisms

> **STATUS: Fixed 2026-06-05** — `_handle_undo()` at `tui/__init__.py:860` now routes journal-first: calls `controller.undo_last_run()` (surgical UndoJournal restore); falls back to `_restore_checkpoint()` (git-stash) only when journal is empty. The write-only journal path is now fully consumed by the undo handler. Tests: `test_tui_undo_uses_journal()`, `test_tui_handle_undo_calls_controller_first()` in `tests/test_tui.py::TUITests`.

**Ticket:** TICKET-12. **Severity:** P2.

**User-facing failure.**
User switches between `teaagent chat` (REPL) and `teaagent tui`. In the REPL, `/undo`
restores only the files the last run touched. In the TUI, `/undo` calls
`_restore_checkpoint()` (`tui/__init__.py:641`) which pops the git-stash checkpoint —
restoring the entire working tree to the state at checkpoint creation, including any
manually edited files the user made between the checkpoint and the undo.

**Internal state — root cause.**
REPL `/undo` → `controller.undo_last_run()` → `UndoJournal.restore()` (surgical).
TUI `/undo` → `_restore_checkpoint()` → `git stash pop` (broad, checkpoint-scoped).
The REPL help text also still says "Undo all changes (using checkpoint)" (`chat_repl.py:168`),
describing the *old* REPL behaviour that was fixed in CG-02 — stale documentation.

**Defeat paths.**
- User makes a manual edit, then runs a task via TUI, then types `/undo` expecting only
  the task's edits to be reverted. git-stash pop reverts everything to the checkpoint
  time, including the manual edit.
- User with the REPL help text open assumes TUI and REPL undo are equivalent.

**Cascade effects.**
- Data loss of manual edits not covered by the journal. The loss is irreversible if the
  user didn't have an external backup.
- The journal written by the TUI (`undo_journal.save_to(...)`, `:925-926`) is never read
  during TUI `/undo` — it is a write-only path. The written journal is dead data.

**Silent failure?** Partial — the user sees "checkpoint restored" not "undo completed" but
may not recognise the difference in scope.

**Data-corruption risk.** High for user work. git-stash pop is irreversible once the
stash is applied; the manual edits before the checkpoint are gone.

**Integration gap.** TUI undo path ↔ REPL undo path: same command word, different
implementation, different scope, different reversibility guarantees. The journal written
by the TUI `_run_agent_task` is never consumed by the TUI undo handler.

---

### DS-06 · CG-16 — Cost test injects state, masks CG-11 (test integrity)

**Ticket:** TICKET-14. **Severity:** P1 (test integrity).

**User-facing failure.**
No direct user-facing failure — but the CI test suite reports green on the TUI cost path
while CG-11 is live. Developers are misled into believing TUI cost is tested and correct.
Any further work on TUI cost display (e.g., adding currency conversion, adding a cost
alert) will be built on a foundation the suite cannot detect as broken.

**Internal state — root cause.**
`tests/test_tui.py:1140-1145` sets `tui._session_cost_cents = 123.0` directly, then
asserts the display shows `$1.23`. It verifies the formatter only — never the accumulation
path. The test passes whether or not `_run_agent_task` actually increments the counter.

**Defeat paths.**
- Every CI run. The test is always green regardless of the live bug.
- A developer adds a real accumulation test and is surprised it fails — discovering CG-11
  via a new test that was supposed to be redundant.

**Cascade effects.**
- False confidence in the TUI test suite extends to adjacent tests. If the cost test
  is "green and trusted," developers may not think to add accumulation tests for other
  TUI state (e.g., observation count, compaction count).

**Silent failure?** Yes — the test is designed to appear thorough while being structurally
hollow.

**Data-corruption risk.** None direct. Corrupts developer confidence in the test suite.

**Integration gap.** Test layer ↔ runtime layer: the test never exercises the real
execution path, so the test suite and the runtime are effectively decoupled for this
feature.

---

### DS-07 · CG-17 — Parity test never instantiates TUI (test integrity)

**Ticket:** TICKET-12b. **Severity:** P1 (test integrity).

**User-facing failure.**
`test_chat_surface_parity` (`tests/test_cli_chat.py:483-552`) is supposed to verify that
REPL and TUI produce identical results for the same task. In practice, it never
instantiates the TUI; it exercises the REPL twice or patches the TUI path. CG-12 (the
structural divergence) can stay open indefinitely with no CI signal.

**Internal state — root cause.**
The test uses mock objects or calls the REPL handler for both "surfaces." The TUI class is
never constructed, so divergence between `_run_agent_task` and `controller.execute_task`
is never exercised.

**Defeat paths.**
- Any developer who reads "parity test passes" as confirmation that REPL/TUI behave
  identically.
- A new controller fix applied to both surfaces — the parity test stays green whether or
  not the TUI path was actually updated.

**Cascade effects.**
- Structural: CG-12, CG-11, CG-15 are all masked. The parity test is the guard that
  should catch them; its hollowness means the structural fault has no CI detector.

**Silent failure?** Yes — the test is actively misleading.

**Data-corruption risk.** None direct.

**Integration gap.** The test itself is the integration gap detector that is broken.

---

### DS-08 · AG-01 — `teaagent resume <repl-id>` always errors

**Ticket:** TICKET-16. **Severity:** P1.

**User-facing failure.**
User suspends a REPL session with `/background`. The REPL prints:
```
[TeaAgent] To resume: teaagent resume {run_id}
```
User runs the command. They receive:
```json
{"status": "error", "message": "run '{run_id}' has no run_started task"}
```
There is no fallback and no explanation. The user cannot resume their session; the
printed instruction is broken.

**Internal state — root cause.**
`agent_resume_command` calls `store.task_for_run(run_id)` (`_agent.py:217`). `task_for_run`
scans the run's audit events for a `run_started` event (`run_store.py:143-149`) and raises
`ValueError` if none exists. REPL suspension emits only `session_suspended` (not
`run_started`) because the suspension happens between runs, not during one. The two halves
were written independently with incompatible event schemas.

**Defeat paths.**
- Any user who uses `/background` in the REPL and follows the printed instruction.
  The failure is deterministic — every REPL-originated suspension triggers it.
- A user who tries with a different `run_id` (from a completed agent run) might succeed
  for that id, which could cause them to think they did something wrong with the
  suspension id.

**Cascade effects.**
1. *Trust erosion:* the system tells the user to run a command, the command errors. The
   CG-09/10 honesty fix is partially undone by this — suspension is honest at suspend
   time, but the printed follow-up is a lie.
2. *AG-04 amplifier:* three commands are printed; two of the three fail or mislead (AG-01,
   AG-02). The one that works (`interactive-review`) is listed third and is read-only.
3. *Saved context is wasted:* the suspension file saved observations and config
   (`chat_repl.py:77-94`) but those are never consumed by any working path (AG-03).

**Silent failure?** No — it errors loudly. But the error message ("no run_started task")
is opaque; the user cannot diagnose it without reading the source.

**Data-corruption risk.** None to state — the suspension file is written correctly. The
risk is user data loss: work context (10 observations, config) is stranded in
`suspension-{id}.json` with no working path to load it.

**Integration gap.** REPL suspension ↔ agent resume: incompatible event schemas. The
REPL writes `session_suspended`; `agent_resume_command` expects `run_started`. The
suspension JSON and the RunStore use separate storage with no bridge.

---

### DS-09 · AG-02 — `agent run --background <id>` silently runs the id as a literal task

> **STATUS: Fixed 2026-06-05** — `agent run --background <id>` now validates the task arg against known run IDs and suspension IDs before dispatching to the LLM. Known IDs are rejected with a clear error directing the user to `agent resume` or `agent interactive-review`. Test: `test_agent_run_background_rejects_known_run_or_suspension_id()` in `tests/test_cli_chat.py:167`.

**Ticket:** TICKET-16. **Severity:** P1.

**User-facing failure.**
User, after reading the suspension output, tries the second printed command:
```
teaagent agent run --background {run_id}
```
The command starts a new detached run whose task is the literal UUID string (e.g.,
`"a3f9c12b"`). No error is shown. The user may wait for output or check the run store
and find a completed run whose task was a nonsense string. The suspended session is never
resumed.

**Internal state — root cause.**
`agent_run_task` routes `args.background` to `_start_background_run` (`_agent.py:145-146`).
The `task` positional arg (`nargs='?'`) consumes the run_id as the literal task string.
There is no guard that detects a UUID-shaped task and warns that the user may have meant
`agent resume`.

**Defeat paths.**
- Any user who uses the second printed command from `/background`. The failure is
  deterministic.
- An automated script that wraps `/background` output and retries with the wrong command.

**Cascade effects.**
1. *A new run is created in the store* with the UUID as its task. If the store is searched
   later for this run_id, two entries appear — the suspension record and the bogus new run.
2. *The bogus run costs money:* it invokes the LLM with a nonsense task. In a high-cost
   model, this is a real spend with zero value.
3. *Audit trail confusion:* the audit log now has a `run_started` event for a run whose
   task is a UUID. Post-incident review is harder.

**Silent failure?** Yes — the wrong thing happens with no error. This is the most
dangerous failure class: wrong-but-confident.

**Data-corruption risk.** Medium — the RunStore now has an orphan run record. No byte
corruption, but the logical integrity of "runs correspond to real user tasks" is violated.

**Integration gap.** `--background` flag semantics ↔ positional `task` arg: the parser
allows the same slot to be used for two incompatible purposes with no disambiguation.

---

### DS-10 · AG-03 — Saved observations from suspension are never rehydrated

**Ticket:** TICKET-16. **Severity:** P2.

**User-facing failure.**
After `/background`, the user runs `teaagent agent interactive-review {run_id}` (the one
command that works). They can view and accept/reject diffs. However, none of the context
from the suspended session (the last 10 observations, the config, the targeted files) is
available in the new run. The continuation is context-blind relative to the suspended work.

**Internal state — root cause.**
`suspend_to_background` saves `suspension-{id}.json` with observations and config
(`chat_repl.py:77-94`). `agent_resume_command` reads observations from `RunStore` or a
SQLite checkpoint (`_agent.py:239-244`), not from the JSON. `_load_suspension_data`
(`_agent.py:1057`) reads the JSON for `interactive-review`, but this path is review-only
— it doesn't feed the observations into a new execution run. The two halves were built
independently.

**Defeat paths.**
- Every REPL suspension that is followed by any form of resume.
- A long session with many observations is suspended — none of that context is available
  in the continuation, so the agent will repeat or contradict prior work.

**Cascade effects.**
- An agent resumed without context may re-propose changes already accepted, re-open
  files already closed, or contradict decisions already made. This produces inconsistent
  output that undermines the user's trust in the agent's coherence.
- The suspension JSON file is never cleaned up by any successful path — if `interactive-review`
  succeeds and the user moves on, the file remains, potentially accumulating over time.

**Silent failure?** Yes — the resume appears to work, but the agent has no memory of the
suspended session.

**Data-corruption risk.** None to files. Logical corruption of session continuity.

**Integration gap.** REPL suspension storage (JSON) ↔ agent resume storage (RunStore +
SQLite checkpoint): two storage systems with no bridge for the suspension case.

---

### DS-11 · UXD-001 — `teaagent chat <task>` silently drops the initial task

**Ticket:** Not yet ticketed. **Severity:** P1.

**User-facing failure.**
User runs `teaagent chat "refactor the auth module"`. The chat REPL opens and shows the
prompt. The task is silently discarded. The user waits for work to begin, or types a
command and is confused about why their initial instruction was ignored.

**Internal state — root cause.**
`chat_command` (`_chat.py:538`) calls `run_tui(...)` but passes no initial task argument.
`run_tui` has no `initial_task` parameter. The CLI parser accepts the task positionally
(`args.task`) but the `chat_command` handler never reads it. The REPL `run_chat_repl`
has an `initial_task` parameter (`chat_repl.py:186`) and a handler for it (`:1003-1026`),
but that path is unreachable from `chat_command`.

**Defeat paths.**
- Any user who reads the CLI help and tries `teaagent chat "my task"` — the most natural
  first-use pattern.
- Automated scripts that wrap `teaagent chat` and pass an initial task.

**Cascade effects.**
- First-use failure: a user's first interaction with the agent produces no output for their
  request. This is a high-trust-cost failure for new users.
- If the user types the task again at the REPL prompt, it works — but they don't know
  whether the CLI accepted the task and ran it already or dropped it.

**Silent failure?** Yes — no warning, no error, the task simply doesn't execute.

**Data-corruption risk.** None.

**Integration gap.** CLI parser ↔ `chat_command` handler: the parser accepts the task arg
but the handler never reads it. REPL initial_task support exists but is on an unreachable
code path from the CLI.

---

### DS-12 · UXD-005 — Missing path in path-scoped approval creates an implicit global grant

**Ticket:** Not yet ticketed. **Severity:** P1 (security).

**User-facing failure.**
User approves a tool call with a "path-scoped" approval but does not provide a specific
path. The approval is stored as a grant with no path globs, which matches all paths — a
de-facto global grant. The user believes they approved access to a specific directory; the
agent now has approved access to the entire workspace.

**Internal state — root cause.**
ApprovalManager creates an `ApprovalRule` when the user approves a call. If the path
argument is empty or None, the rule is created with no path restriction. The matching
logic then applies the approval to all subsequent calls of that type regardless of target
path. (Ref: `daily-driver-ux-contract-drift-2026-06-01.md`, UXD-005.)

**Defeat paths.**
- User at an approval prompt for a file-write tool hits Enter without specifying a path.
- A TUI approval dialog that pre-fills an empty path field and the user accepts it.
- An automated integration that approves calls without path arguments.

**Cascade effects.**
1. *Lateral write access:* the agent can write to any path in the workspace under the
   implicit approval, bypassing the intended scope restriction.
2. *Audit ambiguity:* the audit log records the approval as path-scoped, but post-facto
   review cannot distinguish an intentional global grant from an accidental empty-path
   grant.
3. *Permission-mode circumvention:* a user in `path-restricted` mode expects that
   approvals are always scoped. An empty-path approval silently expands to global scope,
   violating the permission mode's guarantee.

**Silent failure?** Yes — the grant looks like a path grant in the audit log. The expanded
scope is not surfaced.

**Data-corruption risk.** High — unintended write access to the workspace can modify or
delete files the user did not intend to expose.

**Integration gap.** Approval prompt ↔ ApprovalManager ↔ permission-mode contract: the
prompt accepts empty paths, the manager creates an unrestricted grant, and the
permission-mode contract says "path-scoped." Three layers disagree.

---

### DS-13 · UXD-007 — `0` cost cap has two incompatible meanings

**Ticket:** Not yet ticketed. **Severity:** P2.

**User-facing failure.**
User passes `--max-estimated-cost-cents 0` expecting to set a zero budget (no spend
allowed). The runtime interprets `0` as "no cap" (`runner/_core.py:142`, `<= 0` check).
The REPL default-fills `0` as `1000` (`chat_repl.py:255`: `config.max_estimated_cost_cents or 1000`).
The parser help may say "default: unlimited" while the REPL says "default: $10". No
spend is blocked; the session proceeds with no cap.

**Internal state — root cause.**
Three separate interpretations of `0`:
- `runner/_core.py:142`: `<= 0` → skip budget check (unlimited).
- `chat_repl.py:255`: `or 1000` → treat `0` as "use default $10."
- Parser default: `0` as the default sentinel for "user didn't set a cap."
All three are coherent in isolation, but a user setting `0` explicitly triggers the
"unlimited" path, which is the opposite of what the user intends.

**Defeat paths.**
- `teaagent chat --max-estimated-cost-cents 0` → unlimited spend.
- A config file with `max_estimated_cost_cents: 0` → unlimited spend.
- A script that resets the budget to `0` expecting to pause spending.

**Cascade effects.**
- Unbounded spend in a long session if the user believes `0` means "halt."
- Combined with CG-11 (TUI cost always $0.00), TUI users have no spend signal and no
  effective cap if they use `0`.

**Silent failure?** Yes — no warning, the session proceeds as if no cap was set.

**Data-corruption risk.** Wallet/billing risk. No data corruption.

**Integration gap.** Parser default ↔ runtime guard ↔ REPL default-fill: three locations
independently interpret the same sentinel with different semantics.

---

## Part 2 — Cross-Cutting Themes

### T-1 — Silent failures cluster in the TUI path

DS-01 (cost), DS-05 (undo scope), DS-09 (AG-02 wrong run), DS-11 (task drop) all affect
the TUI and all fail silently. The TUI surfaces the fewest error signals while having the
most divergence from the REPL.

### T-2 — Write-only data paths

The TUI writes an undo journal (`tui/__init__.py:925-926`) that no TUI code path reads.
The REPL writes a suspension JSON that no resume path reads. Both are write-only artifacts
created by effort that cannot be recovered. Every write-only path is a deferred data loss.

### T-3 — The suspend→resume chain has no working path

`/background` → advertised `resume` command (errors, AG-01) → advertised `--background`
command (wrong, AG-02) → `interactive-review` (works, read-only). There is no working
path that continues execution from a REPL suspension. The chain was built as two
independently designed halves that were never integrated.

### T-4 — Test integrity undermines defect detection

CG-16 and CG-17 are not just "bad tests" — they are active defect masks. With both in
place, a developer who runs the full test suite sees 104 green TUI tests and concludes the
TUI is well-tested. This is false assurance for exactly the paths where the bugs live.

### T-5 — Approval scope widening is a security boundary violation

DS-12 (UXD-005) is distinct from the other bugs because it can silently widen the attack
surface of an autonomous agent. In `prompt` permission mode, the user expects to
individually approve each sensitive action. An empty-path grant converts a fine-grained
approval into a session-wide blanket, which is structurally equivalent to switching to a
less restrictive permission mode without the user's knowledge.

---

## Part 3 — Decision Matrix

**Scoring.** Impact = user harm (1–5). Likelihood = probability a real user hits this in
a typical session (1–5). Trust = damage to user's trust in the agent (1–5, where 5 is
"user stops trusting the tool"). Fix cost = approximate size (XS/S/M). Cascade = number
of downstream bugs it enables.

| ID | Title | Sev | Impact | Likelihood | Trust | Fix cost | Cascade | Priority score |
|----|-------|:---:|:------:|:----------:|:-----:|:--------:|:-------:|:--------------:|
| DS-01 | TUI cost $0.00 | P1 | 3 | 5 | 3 | XS | 2 | **11** |
| DS-02 | TUI no controller | P1 | 4 | 5 | 4 | M | 5 | **18** |
| DS-03 | Controller swallows errors | P2 | 4 | 2 | 5 | S | 3 | **14** |
| DS-04 | Redundant audit_trail field | P3 | 1 | 2 | 2 | XS | 1 | **6** |
| DS-05 | TUI/REPL undo diverge | P2 | 5 | 3 | 4 | M | 2 | **14** |
| DS-06 | Cost test masks CG-11 | P1 | 2 | 5 | 2 | S | 3 | **12** |
| DS-07 | Parity test hollow | P1 | 3 | 5 | 3 | S | 4 | **15** |
| DS-08 | resume always errors | P1 | 3 | 4 | 5 | S | 3 | **15** |
| DS-09 | --background runs id as task | P1 | 4 | 4 | 5 | XS | 3 | **16** |
| DS-10 | Observations not rehydrated | P2 | 3 | 3 | 3 | M | 2 | **11** |
| DS-11 | Initial task silently dropped | P1 | 4 | 5 | 5 | S | 1 | **15** |
| DS-12 | Empty path → global grant | P1 | 5 | 2 | 5 | S | 3 | **15** |
| DS-13 | Zero cost cap = unlimited | P2 | 3 | 3 | 4 | S | 2 | **12** |

**Priority score = Impact + Likelihood + Trust.** Cascade and fix cost are tiebreakers.

### Recommended execution order

**Tier 1 — Do first (trust-critical + high likelihood)**

1. **DS-09 (AG-02)** — Remove the `--background {id}` hint from REPL suspend output.
   This is XS (one line deletion). The command is wrong and costs money silently.
2. **DS-08 (AG-01)** — Remove the `resume {id}` hint from REPL suspend output; print
   only the working `interactive-review` command. XS. Restores honesty at suspend time.
3. **DS-11 (UXD-001)** — Wire `args.task` through `chat_command` → `run_tui`. S. First-use
   failure on the most natural CLI pattern.
4. **DS-12 (UXD-005)** — Refuse path approval with no path (or default-fill the current
   directory and confirm). S. Security boundary.
5. **DS-02 (CG-12)** — Migrate TUI `_run_agent_task` to `ChatSessionController`. M.
   This collapses DS-01, DS-05, DS-06, DS-07 and is the structural fix.

**Tier 2 — Do while Tier 1 is in review**

6. **DS-06 (CG-16)** — Fix the cost test to exercise accumulation. S. Precondition for
   trusting any future TUI cost fix.
7. **DS-07 (CG-17)** — Rewrite parity test to instantiate TUI. S. Without this, DS-02
   can re-regress silently.
8. **DS-01 (CG-11)** — One-line stop-gap: `+= result.cost_cents` in `_run_agent_task`.
   XS. Ships immediately if DS-02 migration is delayed.

**Tier 3 — Important but not blocking daily use**

9. **DS-03 (CG-13)** — Replace mock-detection except with explicit None checks. S.
10. **DS-13 (UXD-007)** — Settle zero-cap semantics; add test. S.
11. **DS-05 (CG-15)** — Unified undo via controller migration (dependency on DS-02). M.
12. **DS-10 (AG-03)** — Rehydrate suspension observations into resume path. M.

**Tier 4 — Cleanup**

13. **DS-04 (CG-14)** — Remove stale `audit_trail` field. XS.

---

## Part 4 — Silent Failure Inventory

The following bugs produce no error, no log line, and no user-visible signal:

| Bug | What silently fails | How to detect today |
|-----|---------------------|---------------------|
| DS-01 (CG-11) | TUI cost accumulation | Check provider dashboard, compare to `/cost` |
| DS-03 (CG-13) | Undo journal + run persistence | `/undo` returns "nothing to undo" unexpectedly |
| DS-04 (CG-14) | Misleading audit JSON field | Read raw suspension JSON vs RunStore events |
| DS-09 (AG-02) | Wrong run started in background | Check `teaagent agent list` for UUID-task runs |
| DS-10 (AG-03) | Observations not loaded on resume | Agent repeats prior work or contradicts prior decisions |
| DS-11 (UXD-001) | Initial task dropped | No output after `teaagent chat "task"` |
| DS-12 (UXD-005) | Global grant from empty-path approval | Inspect approval store for rules with no path glob |
| DS-13 (UXD-007) | Zero cap treated as unlimited | No budget warning fires; check spend ex-post |

---

## Part 5 — Data Corruption Risk Summary

| Bug | Risk type | Severity | Reversible? |
|-----|-----------|:--------:|:-----------:|
| DS-05 (CG-15) | User work lost in TUI undo (git-stash pop wipes manual edits) | High | No |
| DS-12 (UXD-005) | Unintended write access corrupts files outside intended scope | High | Case-by-case |
| DS-03 (CG-13) | Undo journal absent; run not in store; audit gap | Medium | Partial |
| DS-09 (AG-02) | Orphan run in store; audit trail has bogus entry | Medium | Requires manual cleanup |
| DS-10 (AG-03) | Session context stranded; agent repeats prior destructive work | Medium | Depends on task |
| DS-13 (UXD-007) | Unintended unbounded spend | Medium | Billing only |
| DS-01 (CG-11) | No state corruption; only display wrong | Low | N/A |
| DS-04 (CG-14) | Audit record misleads forensic analysis | Low | Forensic only |

---

*Generated 2026-06-02. Cross-reference: `daily-driver-findings-status-ledger-2026-06-01.md`
(status authority), `daily-driver-backlog-2026-06-01.md` (tickets), `daily-driver-ux-contract-drift-2026-06-01.md` (UXD items).*
