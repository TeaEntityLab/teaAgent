# Daily-Driver Defeat Modes

Date: 2026-06-01

Purpose: list the ways TeaAgent can technically work but still fail as a daily tool.
These are "defeat modes": conditions where the user loses trust, stops using the tool,
or avoids giving it real work.

## Defeat Mode 1: The First Command Does Not Run

Pattern:

- User types a task into a command that appears to accept it.
- The app opens a shell or prompt instead of executing.
- User concludes the product is flaky or the docs are wrong.

TeaAgent trigger:

- `teaagent chat <task>` accepts a positional task but the current runtime path does not
  forward it into TUI execution.

Prevention:

- Make the syntax execute.
- Or reject it with a clear message and suggested supported command.

## Defeat Mode 2: Cost Is Decorative

Pattern:

- UI shows cost or budget controls.
- The number does not move after real work.
- User treats every future budget claim as fiction.

TeaAgent trigger:

- TUI stores and displays `_session_cost_cents`, but run result cost is not accumulated
  in `_run_agent_task`.

Prevention:

- One shared cost ledger.
- Tests that prove cost changes after real run paths, not only manual field seeding.

## Defeat Mode 3: Safety Creates Surprise

Pattern:

- A "safe" feature changes repository state.
- The user did not knowingly opt into that state transition.
- The product feels less safe than a normal shell.

TeaAgent trigger:

- Agent mode can auto-start git sandboxing in available repositories, while the parser
  exposes `--git-sandbox` as if it controls the behavior.

Prevention:

- Align flags, defaults, prompts, and docs.
- Always show current branch and sandbox lineage.

## Defeat Mode 4: Background Is Not Background

Pattern:

- User asks the tool to continue later or in the background.
- Tool saves a checkpoint but does not keep working.
- User exits and returns disappointed.

TeaAgent trigger:

- Chat REPL suspension says no work continues, but caller copy says converted to a
  background task.

Prevention:

- Use `suspend` for checkpoint-only behavior.
- Reserve `background` for active detached work.

## Defeat Mode 5: The Fix Lands In The Wrong Path

Pattern:

- Engineers fix the tested path.
- Users run another path.
- The bug appears "already fixed" in docs but persists in product.

TeaAgent trigger:

- `chat_repl.py`, `_chat.py`, TUI, and `ChatSessionController` still have divergent
  responsibilities.

Prevention:

- Collapse all chat execution through one controller.
- Add tests at real CLI entry points.
- Remove or quarantine stale duplicate code.

## Defeat Mode 6: Approval Fatigue

Pattern:

- User gets too many prompts.
- User chooses broad approval to stop interruptions.
- Safety model becomes ceremonial.

TeaAgent trigger:

- Approval prompt outcomes can become broad when path context is unavailable.
- Docs discuss pre-approval, but the UI needs clearer blast-radius language.

Prevention:

- Every approval prompt should explain scope, duration, and why the tool needs it.
- Offer safer narrowing before global or session-wide approval.

## Defeat Mode 7: Context Feels Haunted

Pattern:

- The agent cites stale rules or forgets recent work.
- Compaction or memory retrieval changes behavior without explanation.
- User stops trusting long sessions.

TeaAgent trigger:

- Skills, memory, project instructions, and compaction are all powerful, but users need
  visibility into which context sources are active.

Prevention:

- Show active instructions, skills, memory sources, and compaction state in TUI/run
  evidence.
- Add preview for compacted context.

## Defeat Mode 8: Documentation Becomes A Second Product

Pattern:

- Docs say a risk is fixed.
- Code still has a variant of the risk.
- Agents and maintainers plan from old truth.

TeaAgent trigger:

- Earlier June 1 docs include completed/old findings while current code still has active
  daily-driver gaps.

Prevention:

- Keep a current-truth audit first in the index.
- Validate acceptance counts.
- Tie readiness claims to commands run in the same change.

## Defeat Mode 9: The TUI Looks Like A Cockpit But Behaves Like A Shell

Pattern:

- Marketing/docs promise an operational cockpit.
- The real interface is a line REPL with occasional panels.
- Users cannot see what matters during a run.

TeaAgent trigger:

- TUI docs and README promote daily cockpit use, while tests mostly validate strings and
  no-throw behavior.

Prevention:

- Define required cockpit fields.
- Add headless tests for those fields.
- Make the line REPL honest if full cockpit behavior is not ready.

## Defeat Mode 10: Autonomy Outruns Review

Pattern:

- Agent edits broadly.
- Diffs are hard to inspect.
- User spends more time reviewing than doing.

TeaAgent trigger:

- Any agent mode with broad write permissions and weak evidence bundle can drift here.

Prevention:

- Always show changed files, tool calls, approvals, tests run, and undo journal status.
- Prefer small tasks and reviewable plans for high-risk changes.

## Priority Order

1. Fix first-command behavior.
2. Fix cost truth.
3. Fix branch/sandbox contract.
4. Fix lifecycle words.
5. Collapse duplicate chat paths.
6. Add cockpit and evidence-bundle tests.

