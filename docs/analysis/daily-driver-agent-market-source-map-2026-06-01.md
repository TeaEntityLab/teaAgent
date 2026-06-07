# Daily-Driver Agent Market Source Map

> **Supersession note, 2026-06-07:** This file contains volatile facts
> (star counts, pricing, model availability, or adoption claims) that may be
> stale. For current competitive positioning and claim hygiene, see
> [competitive-claim-audit-2026-06-06.md](./competitive-claim-audit-2026-06-06.md).

Date: 2026-06-01

Purpose: preserve the source trail behind the daily-driver market survey. This is a
research artifact, not an endorsement of every product or every community claim.

## Source Reliability Tiers

| Tier | Source type | Use |
|---|---|---|
| Tier 1 | Official docs, product docs, official repos | Product capabilities, supported workflows, current terminology. |
| Tier 2 | GitHub issues, official community forums | Recent pain points, regressions, user confusion, missing affordances. |
| Tier 3 | Reddit, Hacker News, broad forums | Directional sentiment and language users use when frustrated. |
| Tier 4 | Blogs and third-party comparisons | Context only; verify against Tier 1 or current code before acting. |

## Product Source Map

### OpenAI Codex / Codex CLI

Official anchors:

- Help Center getting started: https://help.openai.com/en/articles/11096431
- Codex usage with ChatGPT plan: https://help.openai.com/en/articles/11369540
- Codex repository: https://github.com/openai/codex
- Codex product announcements: OpenAI Codex upgrade and general-availability posts.

Community themes:

- Long-session compaction and context-loss complaints.
- Slow or stuck desktop/local behavior.
- Demand for cost tracking.
- Approval state drift and confusion around autonomy levels.

TeaAgent lesson:

Expose mode, cost, context state, and approval state in every long-running surface.

### Anthropic Claude Code

Official anchors:

- Overview: https://docs.anthropic.com/en/docs/claude-code/overview
- CLI usage: https://docs.anthropic.com/en/docs/claude-code/cli-usage
- Security / permissions docs.
- Data usage docs; consumer opt-in changes are dated 2025-08-28 in current docs.

Community themes:

- Hangs, freezes, latency regressions.
- Usage-limit surprises.
- Compaction and permission friction.
- Approval-loop frustration in terminal workflows.

TeaAgent lesson:

Long-session UX must show live progress, context pressure, and budget before the user
feels trapped in an expensive loop.

### Cursor Agent

Official anchors:

- Agent modes: https://docs.cursor.com/agent
- Review/diffs: https://docs.cursor.com/en/agent/review
- Memories: https://docs.cursor.com/en/context/memories
- Rules: https://docs.cursor.com/context/rules
- Rate limits and pricing policy pages.

Community themes:

- Agent chats perceived as extremely slow.
- Missing visibility into what causes delay.
- Confusion around mode/model switching.
- Frustration when rules or context appear ignored.

TeaAgent lesson:

Use explicit mode labels and context-source displays. If a run is slow, say what it is
waiting on.

### Windsurf / Cascade

Official anchors:

- Cascade overview: https://docs.windsurf.com/windsurf/cascade
- Memories/rules: https://docs.windsurf.com/windsurf/cascade/memories
- Skills and workflows docs.

Community themes:

- Reports of slow, laggy, or unresponsive Cascade sessions.
- Pricing and credit confusion.
- "Used to be my daily driver" defection language in Reddit/forum discussion.

TeaAgent lesson:

Daily-driver trust erodes quickly when performance, pricing, and state visibility change
without clear explanation.

### Aider

Official anchors:

- Repository: https://github.com/Aider-AI/aider
- Chat modes: https://aider.chat/docs/usage/modes.html
- General docs: https://aider.chat/docs/

Community themes:

- Token spikes and cost surprises.
- Repo-map/context overflow.
- Requests for better review and diff workflow.

TeaAgent lesson:

Terminal-first tools need excellent git/diff/repo-map hygiene, not just a powerful model.

### OpenCode

Official anchors:

- Repository: https://github.com/sst/opencode
- Docs: https://dev.opencode.ai/docs
- Tools/permissions: https://dev.opencode.ai/docs/tools/
- GitHub integration docs.

Community themes:

- Plan-mode stalls.
- Tool timeouts.
- Stuck states.
- Context crowding and reconstruction pain.

TeaAgent lesson:

Read-only plan mode, approval-aware tools, and TUI-first design are strong patterns, but
they still need timeout and stuck-state recovery.

### Cline

Official anchors:

- Repository: https://github.com/cline/cline
- Plan and Act mode: https://docs.cline.bot/features/plan-and-act
- CLI overview in repository docs.

Community themes:

- Mode-switching surprises.
- Plan/Act confusion.
- Unexpected approval behavior.
- Long-running process handling expectations.

TeaAgent lesson:

Separate exploration from execution, and never let a mode switch silently change
authority.

### Roo Code

Official anchor:

- Archived repository: https://github.com/RooCodeInc/Roo-Code

Version note:

- The repository was archived on 2026-05-15, so Roo is a stale reference point rather
  than an active competitive baseline.

TeaAgent lesson:

Archived projects are useful for historical UX patterns, not current market claims.

### Continue

Official anchors:

- CLI quickstart: https://docs.continue.dev/cli/quickstart
- TUI mode: https://docs.continue.dev/cli/tui-mode
- Context selection: https://docs.continue.dev/agent/context-selection
- Agents overview: https://docs.continue.dev/hub/agents/overview

Community themes:

- Context-provider breakage.
- Intermittent failures.
- Agent/workflow configuration confusion.

TeaAgent lesson:

Context selection needs to be inspectable and resilient; hidden retrieval failures make
agents feel arbitrary.

### GitHub Copilot Coding Agent

Official anchors:

- IDE agent/chat docs.
- Copilot app agent sessions.
- Cloud coding agent concepts.
- Copilot code review.
- Copilot Spaces.

Community themes:

- Slow chat/agent responses.
- Cost and usage concern.
- Long issue/discussion summaries can degrade quality.

TeaAgent lesson:

Background or PR-centric agents should be branch-oriented, review-centric, and clear
about context limits.

### Devin / Cognition

Official anchors:

- Cognition home: https://cognition.ai/
- Devin release and review posts.

Community themes:

- Mixed reaction to "software engineer" framing.
- Questions about whether review overhead and cost outweigh autonomy.
- Better fit for PR/review workflows than quick local chat.

TeaAgent lesson:

Avoid overclaiming autonomy. A smaller promise with excellent review and recovery can be
more useful for daily developers.

## Volatile Facts

Pricing, rate limits, model availability, and product-specific plan names are volatile.
Before implementing pricing or model-specific docs, re-check official sources.

