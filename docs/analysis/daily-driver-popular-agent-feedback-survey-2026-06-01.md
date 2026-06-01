# Popular Agent Feedback Survey

Date: 2026-06-01

Scope: current public documentation plus community/forum signals for daily coding-agent
use. Community evidence is anecdotal and should be treated as directional, not as a
statistical survey.

## Products Reviewed

- OpenAI Codex / Codex CLI
- Anthropic Claude Code
- Cursor Agent / Background Agents
- Windsurf Cascade
- Aider
- OpenCode
- GitHub Copilot coding agent
- Cline / Roo-style extension agents
- Academic and forum discussion on overeager coding agents

## Source Map

Official / primary sources:

- OpenAI Codex help: https://help.openai.com/en/articles/11096431
- Anthropic Claude Code overview: https://docs.anthropic.com/en/docs/claude-code/overview
- GitHub Copilot coding agent docs: https://docs.github.com/en/copilot/using-github-copilot/coding-agent/about-assigning-tasks-to-copilot
- Cursor docs: https://docs.cursor.com
- Windsurf docs: https://docs.windsurf.com
- Aider docs: https://aider.chat/docs/
- OpenCode: https://www.opencode.live/
- Cline docs: https://docs.cline.bot
- Overeager Coding Agents paper: https://arxiv.org/abs/2605.18583

Community / forum sources sampled:

- Cursor forum thread on agent-mode slowness and flow breakage.
- Windsurf Reddit thread where a user says it used to be their daily driver.
- Reddit and forum threads discussing Claude Code, Codex CLI, Cursor, Windsurf, Aider,
  Copilot coding agent, and terminal-agent friction.

## Cross-Agent Daily-Use Themes

### 1. Trust Beats Raw Autonomy

Users are increasingly comfortable with agents editing code, but only when the agent
makes state legible: what changed, why it changed, how to undo it, and whether the user
is still on the expected branch. This is why git-backed flows, checkpoints, diff review,
and pull-request based background agents keep appearing across products.

TeaAgent implication: the project should treat undo, run evidence, current branch,
approval scope, and generated diffs as first-class UI fields in TUI and chat.

### 2. Cost Visibility Is A Daily-Driver Feature

Community complaints around AI coding tools often blend three concerns: high token use,
unclear cost, and agents looping without enough progress. Even when costs are estimates,
users want the meter to be consistent across surfaces.

TeaAgent implication: the TUI cost display cannot be advisory decoration. It needs to
share a single cost ledger with chat and agent mode.

### 3. Speed And Flow Matter More Than Novel UI

Forum feedback on agent modes often frames slowness as a loss of flow. Users forgive
waiting when progress is visible and interruptible; they do not forgive opaque thinking
or repeated tool confirmations that do not teach them anything.

TeaAgent implication: approvals should include blast radius and a useful default, while
long-running runs should emit compact progress, current tool, token/cost, and next
checkpoint.

### 4. Lifecycle Words Must Match Reality

Cloud agents, background PR agents, local terminal agents, and suspended sessions all
sound similar to non-expert users. Products that blur these states create false
confidence: users leave expecting work to continue, then return to a checkpoint.

TeaAgent implication: use one vocabulary:

- `suspend`: save state only; no work continues.
- `background`: work continues without the foreground UI.
- `attach`: watch or control an active background run.
- `resume`: start a new run from persisted context.
- `undo`: revert recorded changes, ideally previewable.

### 5. Rules And Memory Are Only Useful When Inspectable

Cursor rules, Claude Code memory, Windsurf memories/rules, and local skill systems all
show the same pattern: users want durable preferences, but they distrust hidden or stale
instructions.

TeaAgent implication: TUI should show active skills/rules/memory sources and make it easy
to inspect which project instruction affected the run.

### 6. Overeager Agents Need Containment

Academic and user-facing discussions both highlight agents that modify too broadly,
optimize the wrong target, or keep "helpfully" changing unrelated files.

TeaAgent implication: default runs should keep a narrow file scope, expose changed-file
counts, and require stronger approval for broad or destructive edits.

## Competitive Lessons For TeaAgent

| Lesson | Why users care | TeaAgent current gap |
|---|---|---|
| A task typed in chat must run. | First command is the product promise. | `teaagent chat <task>` can drop the task. |
| Cost display must be shared and real. | Budget surprise breaks trust. | TUI cost is not wired to run result cost. |
| Undo must be predictable and previewable. | Users need confidence to let agents edit. | TUI help and CLI/TUI semantics diverge. |
| Background must be literal. | Users plan around whether work continues. | Suspension copy conflicts with background copy. |
| Branch behavior must be explicit. | Surprise branch switching feels like instability. | Agent mode auto-starts git sandbox. |
| Docs must say what the code does today. | Stale readiness docs mislead both users and agents. | Current docs include superseded findings and overconfident completion language. |

## Survey Conclusion

TeaAgent already has a promising governance-first foundation: tool metadata, audit
records, permission modes, skills, memory, and run stores. The daily-driver gap is not a
lack of ambition. It is that the first-hour flows must become boringly reliable: task
entry, cost, undo, lifecycle state, branch state, and docs truth.

