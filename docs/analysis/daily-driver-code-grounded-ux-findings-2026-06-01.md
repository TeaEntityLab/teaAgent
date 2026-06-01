# Daily-Driver Code-Grounded UX Findings — TUI, Chat, Agent Modes
# 2026-06-01

**Why this doc exists.** The 2026-05-31 corpus
(`agent-market-ux-survey-2026-05-31.md`,
`agent-ecosystem-daily-use-gap-review-2026-05-31.md`) is strong, but states its own
residual risk: *"This review did not run full acceptance tests; it relied on existing
acceptance collection and docs."* Those are **doc-level** findings. This pass is
**code-level**: it reads the actual implementation of the three daily surfaces and
records defects that block the product's own stated goal — being a trustworthy daily
driver in TUI, TUI-chat, and agent modes.

**Method.** Direct read of `teaagent/tui/__init__.py`,
`teaagent/cli/_handlers/chat_repl.py`, `teaagent/chat_agent.py`,
`teaagent/runner/_core.py`. Every finding cites `file:line`. Severity uses the
project's existing P0/P1/P2 convention. Each finding is mapped to the baseline survey
theme it grounds (e.g. UX-F6) so the two docs reinforce rather than duplicate.

**Scope note.** Findings are about *operator-facing correctness and trust*, not style.
No code was changed in this pass. Fixes are specified in
`docs/plans/daily-driver-hardening-plan-2026-06-01.md`; residual risk is tracked in
`docs/analysis/daily-driver-risk-register-2026-06-01.md`.

---

## Summary table

| ID | Severity | Surface | One-line | Grounds survey theme |
|----|----------|---------|----------|----------------------|
| CG-01 | **P0** | `teaagent chat` REPL | Every interactive task reports failure and the answer is never shown | UX-F4, UX-F5 |
| CG-02 | **P0** | chat REPL `/undo` | Undo runs `git checkout -- .`, destroying *all* uncommitted work, not just agent edits | UX-F4 |
| CG-03 | **P1** | TUI + REPL | `/cost`, `/budget` display fabricated or always-zero spend despite real `cost_cents` being available | UX-F1, UX-F6 |
| CG-04 | **P1** | chat REPL | `/compact` and `/clear` operate on a context structure the loop never populates → no real effect | UX-F3 |
| CG-05 | **P1** | TUI + REPL | Two divergent chat implementations duplicate checkpoint/undo/effort logic with conflicting behavior | (maintainability → UX drift) |
| CG-06 | **P1** | TUI split-pane | Auto-enabled "split-pane" clears the screen every prompt, destroying scrollback/output | UX-F3 (rendering), Delta D-2 |
| CG-07 | **P2** | TUI | `compact` command is a hardcoded "not yet implemented" stub but advertised in help | UX-F3 |
| CG-08 | **P2** | TUI + REPL | Two undo systems (checkpoint vs `agent undo`) with overlapping names confuse recovery | UX-F4 |

---

## CG-01 — `teaagent chat` reports every task as failed and never prints the answer  [P0]

**Evidence.** `teaagent/chat_agent.py:374` —
`def run_chat_agent(*args, **kwargs) -> RunResult:` returns a `RunResult`
(carrying `.status`, `.final_answer`, `.cost_cents`).

The **initial-task** path handles it correctly:

```
chat_repl.py:557  result = run_chat_agent(task=task_with_warnings, ...)
chat_repl.py:560  if result.status != 'completed':
```

The **interactive loop** path does not:

```
chat_repl.py:816  result = run_chat_agent(task=task_with_warnings, ...)
chat_repl.py:820  if result != 0:
chat_repl.py:821      print(f'[TeaAgent] Task failed with exit code {result}')
```

A `RunResult` is never equal to the integer `0`, so the `result != 0` branch is
**always true**. Consequence, for *every* task typed into the REPL:

1. The user sees `Task failed with exit code <RunResult repr>` even on success.
2. `result.final_answer.content` is **never printed** — the REPL never displays the
   agent's answer at all. (Contrast the TUI, which prints `result.final_answer.content`
   at `tui/__init__.py:860`.)

**Why P0.** This is the primary chat surface's core loop. It fails the survey's
first-5-minutes test (UX-F5) and is a textbook UX-F4 "confident wrong report"
(claims failure on success). Per Delta D-3, this is exactly the 60-second
switching-trigger that drives defection narratives.

**Fix direction.** Treat the return as `RunResult`: branch on `result.status`, print
`result.final_answer.content` on success, and feed the result back into
`session_context` (see CG-04). Specified in the hardening plan as P0-1.

---

## CG-02 — chat REPL `/undo` destroys all uncommitted work  [P0]

**Evidence.** `chat_repl.py:783-801`. When the checkpoint stash is present, restore
does:

```
chat_repl.py:418  subprocess.run(['git', 'checkout', '--', '.'], cwd=config.root, ...)
chat_repl.py:424  subprocess.run(['git', 'stash', 'pop'], cwd=config.root, ...)
```

And when no checkpoint exists, the fallback (`chat_repl.py:789-799`) *also* runs
`git checkout -- .`. `git checkout -- .` reverts **every** tracked file in the
worktree to HEAD — including edits the human made by hand outside the agent, and edits
from a prior un-checkpointed task. The TUI's restore is surgical by comparison: it
reverts only the files captured in the stash (`tui/__init__.py:629-641`,
`git checkout HEAD -- <stashed_files>`).

**Why P0.** This is the irreversible-destruction failure the survey calls the single
least-tolerable agent behavior (UX-F4: "developers can tolerate errors if they are
reversible and visible; they cannot tolerate invisible, irreversible errors"). A user
who types `/undo` expecting to revert the last agent task can silently lose unrelated
manual work. The fact that checkpoint creation is *disabled by default*
(`chat_repl.py:537-539`, "Automatic checkpoint creation disabled for data safety")
makes the destructive fallback the common path.

**Fix direction.** Remove the `git checkout -- .` fallback; scope undo to the run's
`UndoJournal` (already used by the TUI/agent path at `tui/__init__.py:779-782`) or to
explicitly checkpointed files only. Never touch files the agent did not write.
Specified as P0-2.

---

## CG-03 — Cost and budget displays are fabricated / always zero  [P1]

**Evidence.**

- REPL: `session_cost_cents += 10  # Placeholder: 10 cents per task`
  (`chat_repl.py:563` and `:825`). `/cost` (`:661-666`) and `/budget`/effort status
  (`:528-535`) report this placeholder, not real spend.
- TUI: `self._session_cost_cents` is initialized to `0.0` (`tui/__init__.py:184`) and
  is **only ever read** — `_handle_cost` (`:670`), `_handle_effort` (`:674-678`),
  `_handle_budget` (`:702-706`). It is never incremented anywhere. So TUI `/cost`
  always prints `$0.00` regardless of actual usage.
- Real data is available and ignored: `RunResult` carries `cost_cents`,
  `input_tokens`, `output_tokens` (`runner/_core.py`), and the TUI even computes a
  `run_summary` from `result.cost_cents` at `tui/__init__.py:835-843` — then discards
  it from the session counter.

**Why P1.** Cost unpredictability is survey theme UX-F6 (HIGH) and the "Claude Is
Dead" rate-cap rage (UX-F1). Per Delta D-1, cost *accuracy* is now a competitive axis
(DeepSeek-TUI cache-aware tracking, `tokscale`, Codeburn). teaagent ships the UI for
this feature but wires it to fake numbers — arguably worse than omitting it, because
it teaches users to distrust the display.

**Fix direction.** Increment session cost from `result.cost_cents` after each run in
both surfaces; surface input/output/cached token counts; label the source
(server-reported). Specified as P1-1.

---

## CG-04 — REPL `/compact` and `/clear` act on an unpopulated context  [P1]

**Evidence.** `session_context['observations']` is appended to **only** on the
initial-task path (`chat_repl.py:564-570`). The interactive loop (`:804-827`) runs
tasks but never appends their results to `session_context`. So after the first turn,
`/compact` (`:611-625`) compresses a near-empty list and reports
`tokens_saved` / `compression_ratio` derived from nothing, and `/clear` (`:628-634`)
clears a structure that was never filling up.

**Why P1.** Context rot is survey theme UX-F3 (HIGH) — "the agent starts contradicting
earlier decisions." The REPL advertises `/compact` as the mitigation, but it is inert
for the actual conversation because the conversation is never recorded in the
structure compaction reads. (Note: `run_chat_agent` may manage its own context
internally per call, but the REPL-level session memory the commands target is empty —
so the *operator-visible* compaction is theater.)

**Fix direction.** Record each turn's task + result into `session_context` (this is
also required by CG-01's fix), so compaction and `/clear` operate on real history.
Specified as P1-2.

---

## CG-05 — Two divergent chat implementations  [P1]

**Evidence.** `teaagent chat` uses `chat_repl.py::run_chat_repl`; the TUI chat mode
uses `tui/__init__.py::TeaAgentTUI._run_agent_task`. Both independently implement:
checkpoint create/restore, undo, effort levels, file-watcher, cost display, pinned
files — with **different behavior**:

| Behavior | REPL (`chat_repl.py`) | TUI (`tui/__init__.py`) |
|---|---|---|
| Undo scope | `git checkout -- .` (all files) | surgical, stashed files only |
| Result handling | `result != 0` (broken, CG-01) | `result.status` / prints answer |
| Session memory | `session_context` list | `ChatSession` + `SessionStore` |
| Compaction | `ContextCompactor` on empty list | `compact` = stub (CG-07) |
| Cost | `+= 10` placeholder | `_session_cost_cents` never set |

**Why P1.** Two code paths for "the same product feature" guarantee the kind of
behavior drift that produces CG-01/02/03 in the first place. The survey's
gap-review F-ECO-010 asks for "CLI/TUI/dashboard parity for the same run state"; this
is the root cause that makes parity impossible to maintain by hand.

**Fix direction.** Extract a shared `ChatSessionController` that both surfaces drive,
owning result handling, cost accounting, undo scope, and session memory. Surfaces keep
only their I/O. Specified as P1-3 (enables P0-1/P0-2/P1-1/P1-2 to be fixed once).

---

## CG-06 — TUI "split-pane" clears the screen every prompt  [P1]

**Evidence.** `_should_use_split_pane` returns true for terminals ≥120×30
(`tui/__init__.py:189-195`) and the main loop calls `_print_state_panel()` on **every**
iteration (`:318-319`). `_print_state_panel` begins with
`print('\033[2J\033[H', end='')` (`:205`) — a full clear-screen + cursor-home. It then
prints a *vertical* list labelled "[Chat Area]" and "[State Panel]" — it is not an
actual split pane, and the clear wipes the previous command's output (including agent
answers and approval prompts) before each new prompt.

**Why P1.** This auto-activates on large terminals — precisely what power users run.
It destroys scrollback and prior output, which is the exact rendering-fragility
reviewers already punish in competitors (Delta D-2: "scrolling back creates messy
display"; OpenTUI praised as "better for extended sessions"). The feature as built is
a net regression versus a plain scrolling REPL.

**Fix direction.** Either implement a real fixed-region layout with prompt_toolkit's
`Application`/full-screen layout (state panel in a side/bottom region, scrollable chat
buffer that is never cleared), or disable the screen-clear and render the state panel
as an opt-in `state` command. Specified as P1-4.

---

## CG-07 — TUI `compact` is an advertised no-op  [P2]

**Evidence.** Help lists `compact   Compact session context to save tokens`
(`tui/__init__.py:103`), but `_handle_compact` prints
`'compact: session compaction not yet implemented in TUI'` (`:666-667`).

**Why P2.** Advertising a token-saving command that does nothing erodes trust on a
HIGH-priority theme (UX-F3), but it fails loudly (prints "not implemented") rather
than silently, so it is less harmful than CG-04. Fix as part of CG-05's shared
controller (the REPL compactor can be reused once session memory is shared).

---

## CG-08 — Two overlapping undo systems confuse recovery  [P2]

**Evidence.** TUI help documents both `undo  Undo all changes (using checkpoint)`
(`tui/__init__.py:108`) and, two lines earlier, references
`teaagent agent undo for advanced` (`:108` continuation) plus a separate
`undo [run_id]  Restore workspace files from the last undo journal`
(`:76`). So a user has: git-stash checkpoint undo, `UndoJournal` run-scoped undo, and
the CLI `agent undo` — three mechanisms with two help entries that both say "undo".

**Why P2.** Recovery is the moment trust is won or lost (UX-F4). Overlapping,
differently-scoped undo verbs make it ambiguous *what* a given `undo` will revert
(the whole concern behind CG-02). Consolidate onto the `UndoJournal` as the single
operator-facing undo, and rename the git-stash one to `checkpoint restore` to remove
the collision. Specified as P2-1.

---

## Cross-reference to baseline survey themes

| Survey theme (2026-05-31) | Grounded by |
|---|---|
| UX-F1 Rate/cap surprises | CG-03 |
| UX-F3 Context rot | CG-04, CG-06, CG-07 |
| UX-F4 Silent/irreversible action | CG-01, CG-02, CG-08 |
| UX-F5 Onboarding / first 5 min | CG-01 |
| UX-F6 Cost unpredictability | CG-03 |
| F-ECO-010 CLI/TUI parity | CG-05 |

## Residual risk of this review

- Findings are from static reading, not execution. CG-01 and CG-03 are
  near-certain (the type mismatch and the absent increment are unambiguous in source);
  CG-04 depends on whether `run_chat_agent` also persists session memory by another
  path — the *operator-visible* commands are still inert regardless. Each fix in the
  plan ships with a regression test that makes the behavior executable-verifiable.
- Line numbers reflect the working tree at 2026-06-01 on branch
  `codex/plan-exec-2026-05-31`; re-anchor before editing.
</content>
