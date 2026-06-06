# Competitor Signal Survey - 2026-06-04

> Supersession note, 2026-06-06: For the latest quarterly refresh, use
> [Competitor Signal Survey (2026-06-06)](competitor-signal-survey-2026-06-06.md)
> and [Competitor Self-Comparison Matrix (2026-06-06)](competitor-self-comparison-matrix-2026-06-06.md).

## Purpose

This survey collects current competitor signals from official documentation, release notes, and community feedback. The goal is not to rank "best agent" in the abstract. The goal is to extract what TeaAgent should learn, what it should avoid, and which product shapes are now common enough to count as baseline expectations.

## Method

- Official docs and release notes are treated as primary evidence.
- Reddit and forum posts are treated as community signals, not neutral truth.
- Recent signals are weighted more heavily than old ones because agent products change quickly.

## Survey

| Project | Positioning | What users seem to like | Common complaints or tensions | TeaAgent lesson |
|---|---|---|---|---|
| Pi.dev | Minimal, terminal-native, highly malleable agent harness with a growing extension ecosystem. | Fast iteration, hackability, self-extension, session branching, local-friendly design. | YOLO-default security, fragmented permission extensions, weaker built-in governance, less observable subagent behavior. | Adopt the malleability model, reject the security default. Make extensibility reviewable and governed. |
| OpenCode | Full-featured open-source agent across terminal, IDE, and desktop. | LSP integration, multi-session parallelism, desktop surface, provider breadth, plan/build separation. | Docs and ergonomics feel heavy to some users; broad feature surfaces can be overwhelming. | Learn from the surface breadth, but keep TeaAgent's front door smaller and more opinionated. |
| Claude Code | Mainstream terminal agent with skills, plugins, connectors, and increasingly rich review/task features. | Strong output quality, deep review utility, broad workflow support, growing ecosystem. | Users repeatedly worry about fake success, cost, and overtrusting output. | Keep receipts, proof, and honest state as first-class UX objects. |
| Codex | Command-center style agent with worktrees, automations, skills, review, and multi-agent workflows. | Strong multi-agent workflow, parallel work, review depth, broad engineering fit. | More complex than a simple local CLI, and users still layer their own process on top. | TeaAgent should embrace process support but remain transparent and locally controllable. |
| Aider | Surgical edit-first pair programmer with a narrow, practical workflow. | Diff-centered editing, clarity, low ceremony, predictable local git behavior. | Large-context or multi-step work can become manual and context-heavy. | Preserve surgical edit clarity without losing broader harness capabilities. |
| OpenHands | Open-source development agent with cloud/local options, MCP, skills, and Docker sandboxing. | Clear packaging, strong getting-started docs, explicit safety guidance, open source extensibility. | Single-user local deployment focus, enterprise caveats, and significant setup complexity. | Make safety claims concrete, not aspirational, and keep daily-driver docs easy to enter. |

## Evidence and Inference

### Pi.dev

**Evidence**

- Official release notes and project pages show a fast release cadence, packages for agent core and UI, and a growing package ecosystem.
- Community posts describe Pi as highly malleable and useful for people who want to extend the agent from inside the session.
- Community threads also show repeated concern about the lack of a built-in safety layer.

**Inference**

- Pi is the strongest example of "malleability first", but its ecosystem shows what happens when governance is left to extensions.

### OpenCode

**Evidence**

- Official docs highlight terminal, IDE, and desktop usage, LSP support, multi-session work, agents, and skill discovery.
- Docs also show explicit permission handling and agent configuration.
- Community discussion often frames OpenCode as powerful but heavy.

**Inference**

- OpenCode validates the market for a broad harness, but it also proves that breadth increases onboarding and configuration burden.

### Claude Code

**Evidence**

- Anthropic docs emphasize setup simplicity, CLI usage, MCP integration, and release notes now include skills, plugins, connectors, and tasking features.
- Community discussion repeatedly emphasizes review quality and the need for a human to catch silent failures.

**Inference**

- Claude Code sets the expectation that a serious coding agent should support the full engineering loop, not just chat.

### Codex

**Evidence**

- OpenAI's Codex pages emphasize multi-agent workflows, worktrees, automations, skills, and review.
- Community users often describe Codex as reliable but still process-heavy enough that they add their own `AGENTS.md` discipline.

**Inference**

- The market now expects multi-agent and automation features, but also expects a structured workflow around them.

### Aider

**Evidence**

- Aider docs center on pair-programming, in-chat commands, and code/architect/help chat modes.
- Community feedback values precision and low ceremony.

**Inference**

- Aider proves that a narrow, surgical workflow still has a durable audience even while broader harnesses grow.

### OpenHands

**Evidence**

- Official docs present OpenHands as open source, local or cloud deployable, and safety-aware through Docker and documentation on when to use it.
- Community discussion accepts that it is useful but operationally larger than a simple CLI.

**Inference**

- OpenHands shows the value of explicit safety language and the cost of making local setup too heavy.

## TeaAgent Implications

1. Malleability should remain visible and easy to use.
2. Governance must be first-party, not extension-fragmented.
3. The agent must show trust state honestly: cost, undo, approvals, and root must never be guesswork.
4. The docs must make the first hour easier than browsing the full architecture.
5. The roadmap should favor deep trust repair before adding more surface area.

## Risks

- Reddit and forum sentiment can overrepresent power users.
- Official docs can overstate current product maturity.
- New releases can shift the picture quickly.

## Sources

- [Pi.dev releases](https://pi.dev/news/releases)
- [Pi.dev news: Pi has a new home at Earendil](https://pi.dev/news/2026/5/7/pi-has-a-new-home)
- [Pi GitHub repository](https://github.com/earendil-works/pi)
- [Pi subreddit thread on OpenPi](https://www.reddit.com/r/PiCodingAgent/comments/1tcrb2v/openpi_a_desktop_workbench_for_the_pi_coding_agent/)
- [Pi subreddit thread on harness meaning](https://www.reddit.com/r/LocalLLaMA/comments/1t0fg3y/what_exactly_does_pi_harness_mean/)
- [OpenCode home](https://opencode.ai/)
- [OpenCode agents docs](https://dev.opencode.ai/docs/agents/)
- [OpenCode skills docs](https://dev.opencode.ai/docs/skills)
- [OpenCode tools docs](https://dev.opencode.ai/docs/tools/)
- [OpenCode subreddit thread on overkill concerns](https://www.reddit.com/r/opencodeCLI/comments/1rz44y1/am_i_wrong_about_oh_my_opencode_omo_being_overkill_for_experienced_devs_who_just_want_ai-assisted_iteration/)
- [OpenCode subreddit thread on benchmark chatter](https://www.reddit.com/r/opencodeCLI/comments/1talvrd/new_artificial_analysis_coding_agent_index_has_some_wild_data_about_the_current_state_of_programming_tools/)
- [Claude Code getting started](https://docs.anthropic.com/en/docs/claude-code/getting-started)
- [Claude Code CLI reference](https://docs.anthropic.com/en/docs/claude-code/cli-usage)
- [Claude Code release notes](https://docs.anthropic.com/ko/release-notes/claude-apps)
- [Claude Code MCP docs](https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-mcp)
- [Codex official page](https://openai.com/codex/)
- [OpenAI Codex CLI help](https://help.openai.com/en/articles/11096431)
- [OpenHands quick start](https://docs.openhands.dev/overview/quickstart)
- [OpenHands FAQ](https://docs.openhands.dev/overview/faqs)
- [Aider docs](https://aider.chat/docs/)
