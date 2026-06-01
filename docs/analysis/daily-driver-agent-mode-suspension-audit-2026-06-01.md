# Daily-Driver Agent-Mode & Suspend→Resume Audit
# 2026-06-01

**Why.** The first three passes focused on the chat REPL and TUI. The original review goal
explicitly included **agent mode**. This pass audits the non-interactive agent surface
and the suspend→resume round-trip the REPL advertises after the CG-09/CG-10 honesty fix.
Finding: the suspension *messaging at suspend time* is now honest, but **every follow-up
command the REPL prints is broken or misleading** — there is no working "continue this
session" path; only read-only review works.

**Method.** Traced `teaagent chat` `/background` → the three printed commands → their
handlers (`agent_resume_command`, `agent_run_task`, `interactive-review`) →
`RunStore.task_for_run`. All `file:line` re-anchored against current HEAD.

---

## 1. The advertised round-trip vs reality

After `/background`, the REPL prints three follow-up commands:

| Printed (chat_repl.py) | Handler | Reality |
|---|---|---|
| `teaagent resume {run_id}` (`:142`) | `agent_resume_command` (`_agent.py:214`) | **Errors** — see AG-01 |
| `teaagent agent run --background {run_id}` (`:662`) | `agent_run_task`→`_start_background_run` (`_agent.py:145`) | **Misleading** — starts a NEW run, id treated as the task (AG-02) |
| `teaagent agent interactive-review {run_id}` (`:143`) | `_load_suspension_data` (`_agent.py:1057`) | **Works**, but review-only (AG-03) |

## 2. Findings

### AG-01 — [P1] `teaagent resume <repl-suspension-id>` always fails
`agent_resume_command` reconstructs from `RunStore`:
`store.task_for_run(run_id)` (`_agent.py:217`). `task_for_run` scans the run's events for
a `run_started` event and **raises `ValueError` if none exists** (`run_store.py:143-149`).
But the REPL's `suspend_to_background` generates a fresh `uuid4()[:8]` (`chat_repl.py:56`)
and records **only** a `session_suspended` event (`:130`) — never `run_started`. So
`task_for_run` raises, `agent_resume_command` catches it (`_agent.py:218-220`), prints
`{'status':'error'}`, and returns 1. The command the REPL tells the user to run cannot
succeed for a REPL-originated suspension.

### AG-02 — [P1] `teaagent agent run --background <id>` runs the id as a literal task
`--background` means "run detached" (parser help, `_agent_parsers.py:286-289`);
`agent_run_task` routes `args.background` straight to `_start_background_run` (`:145-146`).
The `{run_id}` is consumed as the positional `task` (`nargs='?'`), so the command starts
an **unrelated new detached run whose task is the literal uuid string** — it does not
continue the suspended session. Worse than failing: it silently does the wrong thing.

### AG-03 — [P2] No working "continue session" path; saved context is dead
Only `interactive-review` consumes the suspension file, and it is **review-only** (accept/
edit/reject diffs). Meanwhile `suspend_to_background` carefully saves the last 10
observations and config into `suspension-<id>.json` (`chat_repl.py:77-94`), but **nothing
reads them back into a run** — `agent_resume_command` reads observations from `RunStore`/
checkpoint (`_agent.py:239-244`), not the JSON. The two halves were built independently.

### AG-04 — [P2] Three inconsistent commands undercut the CG-09/CG-10 honesty fix
The CG-09/10 fix made the suspend-time copy honest ("suspension checkpoint, not
background execution", `chat_repl.py:144`). But printing three different follow-up
commands — two of which are broken/misleading — reintroduces exactly the trust problem
CG-09/10 set out to fix. Honesty at suspend time is undone by dishonesty about resume.

## 3. What is solid in agent mode (verified, not findings)

- **Scoped approvals on resume:** `agent_resume_command` correctly refuses to auto-approve
  legacy pending calls without an argument digest, and uses digest-checked scoped
  approvals (`_agent.py:253-280`) — good governance.
- **Plan-before-write:** `_require_plan_gate` enforces plan-by-default in workspace-write
  mode (`_agent.py:304-329`), consistent with ADR 0023.
- **Auto-compact on resume:** large histories are truncated to the last 20 observations
  with a recorded `resume_compaction` marker (`_agent.py:245-252`) — honest about
  truncation.

These confirm the agent-mode *governance* is strong; the gap is specifically the
REPL→agent suspension handoff.

## 4. Recommendation → TICKET-16

**TICKET-16 — [P1] Make suspend→resume honest, then real.**
- **Now (honesty, XS):** in `suspend_to_background`, print only the command that works
  (`teaagent agent interactive-review {run_id}`); remove the `resume` and
  `agent run --background` hints until implemented (`chat_repl.py:142,662`).
- **Real feature (M):** make the round-trip work — at suspend, persist a `run_started`
  event + task + observations into `RunStore` keyed by the same `run_id` (or have
  `agent resume` fall back to `_load_suspension_data`), so `teaagent resume <id>` rehydrates
  the saved observations into a new run. Add `test_repl_suspend_resume_roundtrip`.
- **Guard AG-02:** when `--background` is given with a value that matches an existing
  suspension/run id, error with "did you mean `agent resume`?" rather than running the id
  as a task.

## 5. Cross-references
- Suspension fix it builds on: `daily-driver-findings-second-pass-2026-06-01.md` (CG-09/10).
- Backlog: add TICKET-16. Thought log: `daily-driver-third-pass-thought-log` (TP-OBS/AG).
- Code: `chat_repl.py:36-147`; `_agent.py:144,214,1057`; `run_store.py:143-160`.
