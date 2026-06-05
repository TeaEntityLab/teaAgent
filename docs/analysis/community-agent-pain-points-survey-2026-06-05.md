# Community Agent Pain Points Survey - 2026-06-05

## Purpose

This document records current community pain points around coding agents and
maps them to TeaAgent design work. It complements the seven-control-loop survey
by focusing on user-reported friction: cost surprises, routing opacity, memory
pollution, review overhead, long-task drift, hook confusion, skill/MCP risk, and
proof gaps.

The goal is not to prove that any competitor is bad. The goal is to identify
where serious daily users are losing trust and convert those losses into
TeaAgent product requirements.

## Source Boundary

Official and upstream sources:

- Claude Code memory docs: https://code.claude.com/docs/en/memory
- Claude Code hooks docs: https://code.claude.com/docs/en/hooks
- Claude Code code review docs: https://code.claude.com/docs/en/code-review
- GitHub Copilot code review docs: https://docs.github.com/en/copilot/how-tos/copilot-on-github/use-copilot-agents/copilot-code-review
- GitHub Copilot usage-based billing discussion: https://github.com/orgs/community/discussions/192948
- GitHub Copilot code review Actions minutes changelog: https://github.blog/changelog/2026-04-27-github-copilot-code-review-will-start-consuming-github-actions-minutes-on-june-1-2026/
- OpenCode agents docs: https://dev.opencode.ai/docs/agents/
- OpenCode skills docs: https://opencode.ai/docs/skills/
- Kiro specs docs: https://kiro.dev/docs/specs/
- Kiro faster specs post: https://kiro.dev/blog/faster-smarter-specs/

Community sources:

- Claude Code memory pollution post: https://www.reddit.com/r/ClaudeCode/comments/1t776gn/claude_codes_memory_system_can_actually_make_ai/
- Claude Code compaction strategy post: https://www.reddit.com/r/ClaudeCode/comments/1trpxbb/what_is_your_claude_code_compacting_strategy/
- Cursor pricing transparency post: https://www.reddit.com/r/cursor/comments/1ro7iup/complaint_regarding_cursor_ai_pricing_and_token/
- OpenCode subagent misrouting post: https://www.reddit.com/r/opencodeCLI/comments/1tekba8/reliable_way_to_use_a_primary_agent_to/
- OpenCode model-routing workflow post: https://www.reddit.com/r/opencode/comments/1tvlk0x/i_finally_documented_my_entire_ai_coding_workflow/
- GitHub Copilot review reliability and billing posts from r/GithubCopilot
  search results, including review timeout, plan-switching, and Actions-minute
  cost confusion.

Research sources:

- Memory poisoning: https://arxiv.org/abs/2606.04329
- Sleeper memory poisoning: https://arxiv.org/abs/2605.15338
- Overeager coding agents: https://arxiv.org/abs/2605.18583
- Skill-based prompt injection: https://arxiv.org/abs/2602.14211
- AI code review effectiveness: https://arxiv.org/abs/2508.18771
- Agentic PR modification patterns: https://arxiv.org/abs/2601.17581

Interpretation rules:

- Official docs are evidence of intended product behavior and documented limits.
- GitHub issues and discussions are evidence of user confusion, defects, or
  product tension, not statistical consensus.
- Reddit and forum posts are treated as directional pain signals.
- Research papers are stronger evidence for general risk classes but may not
  match every product implementation.
- TeaAgent should adopt the pain pattern only when it maps to a concrete local
  risk or user journey.

## Executive Synthesis

The community pain is converging around seven practical trust failures:

1. Users cannot tell why an agent chose a model, subagent, skill, MCP tool, or
   route.
2. Long tasks drift because context grows, compaction strips rationale, and
   phase handoffs are not durable.
3. Memory helps continuity but can preserve emotional corrections, stale
   assumptions, poisoned web content, or broad rules that later mislead the
   agent.
4. Review agents are useful but can become another billable workflow with
   repeated comments, limited authority, and weak evidence boundaries.
5. Cost is no longer a subscription footnote. Agentic workflows multiply token,
   cache, tool, review, and Actions-minute spend.
6. Hooks, permissions, skills, and MCP add control and extensibility, but they
   can also bypass native approval or become supply-chain surfaces.
7. Agents can over-expand scope, edit too early, or claim completion without a
   strong proof bundle.

TeaAgent already has the right instincts: audit, approvals, permission modes,
budget tracking, plan gates, skill candidates, docs governance, and run
evidence. The current gap is user-facing closure. The user must see the route,
memory, review, cost, and gate evidence at the moment trust is being asked for.

## Pain Point 1: Routing Opacity And Subagent Misrouting

### Community signal

OpenCode community posts show users building multi-model and multi-agent stacks
to control cost and quality. One reported failure mode is subagent misrouting:
the orchestrator selects the wrong agent or ignores workspace constraints.
Another thread argues that model routing helps, but phase boundaries fail when
input context, output artifact, evidence, and "do not carry forward" rules are
not explicit.

### Product evidence

OpenCode docs support per-agent model overrides and note that subagents inherit
the invoking primary agent's model if no override is set. That is powerful, but
it means route behavior is partly configuration, partly inheritance, and partly
agent decision.

### TeaAgent implication

TeaAgent should treat routing as an auditable decision, not a hidden preference.
Every significant run should expose:

- requested provider and model
- resolved provider and model
- role or phase
- route reason
- policy source
- fallback reason, if any
- estimated and actual cost
- subagent or skill selected

### Required work

- Implement `SCL-P0-005` model-route receipts.
- Add a route table to run evidence and TUI summaries.
- Add phase handoff packets so route changes cannot silently drop constraints.

## Pain Point 2: Long-Task Drift And Context Compaction Loss

### Community signal

Claude Code users repeatedly describe "context rot" and long-session drift:
older constraints fade, rationale gets compressed away, and the model begins
second-guessing earlier plans. Some users work around the issue by writing plan
files, closing the session, and restarting with a clean execution context.
Others disable auto-compact and use manual checkpoint files.

### Product evidence

Claude Code memory docs say sessions begin with fresh context and that memory
files are context, not enforcement. Kiro's spec workflow and Spec Kit's
spec-first direction show a different response: make requirements, design, and
tasks explicit artifacts rather than relying on chat history.

### TeaAgent implication

TeaAgent should not expect one long conversation to remain coherent. A long task
needs durable state:

- current objective
- accepted spec or exemption
- current task wave
- decisions and rejected alternatives
- cost and token pressure
- memory entries read or written
- evidence already collected
- re-plan triggers

### Required work

- Implement `SCL-P0-004` persisted goal records.
- Add context-health and drift checkpoints to long runs.
- Fail long-goal closure when no durable checkpoint exists.

## Pain Point 3: Memory Pollution, Stale State, And Poisoned Memory

### Community signal

Community posts report that auto-written memory can make an assistant worse
when angry corrections, one-off frustration, or stale local facts become durable
guidance. Other posts argue that simple, precise project files can outperform
heavy vector-memory stacks when the real problem is unclear instructions.

### Research signal

Recent memory-poisoning research identifies persistent memory as a long-term
attack surface. The June 2026 memory-poisoning paper reports multiple write
channels and structural vulnerabilities, and the sleeper-memory paper shows
that poisoned memories can remain dormant and later steer agentic behavior.

### Product evidence

Claude Code docs state that `CLAUDE.md` and auto memory are loaded as context,
not enforcement, and recommend hooks/settings for blocking behavior. They also
document scoping, loading limits, and troubleshooting for memory uncertainty.

### TeaAgent implication

TeaAgent should make memory precise before making it more automatic. Agent-
written durable memory should not become project-wide truth without review.

Minimum metadata:

- scope
- source run
- source artifact
- owner
- confidence
- TTL or expiry
- review state
- supersession link
- injection reason

### Required work

- Implement `SCL-P1-001` typed memory metadata.
- Implement `SCL-P1-002` memory quarantine and promotion.
- Add "memory explain" to run evidence and TUI.
- Add tests where untrusted web/tool output attempts to become durable memory.

## Pain Point 4: Review Cost, Noise, And Limited Authority

### Community signal

Users now treat review as another expensive agentic workflow, not a free bonus.
GitHub Copilot community discussions show confusion and frustration around
usage-based billing. Reddit posts mention review timeouts, repeated comments,
and missing access after plan changes.

### Product evidence

GitHub documentation says Copilot review comments can be rated and that Copilot
does not automatically re-review after new changes; it may repeat earlier
comments. GitHub also documents that Copilot code review can use repository
instructions, skills, and MCP logs, but instruction files have documented
limits. The GitHub changelog and community discussion say private-repo Copilot
reviews consume Actions minutes starting June 1, 2026.

### Research signal

A study of AI review actions found wide variance in effectiveness. Concise,
snippet-backed, manually triggered, hunk-level comments were more likely to
lead to code changes.

### TeaAgent implication

TeaAgent should not make review feel like an infinite second agent loop. Review
must be budgeted, scoped, actionable, and evidence-linked.

### Required work

- Implement `SCL-P0-006` synthesis review artifacts.
- Add review budgets and repeat-comment suppression.
- Prefer hunk/file/command evidence over broad prose summaries.
- Make review unable to close high-risk work without test/evidence references.

## Pain Point 5: Cost Surprise And Token Burn

### Community signal

Cursor users report confusion over token usage and cost during agent workflows.
Claude Code users report rate limits and token spend surprises, especially
during long sessions, multi-agent pipelines, heavy review loops, and repeated
context reloads. GitHub users are now dealing with AI credits plus Actions
minutes for some review paths.

### Product evidence

GitHub's billing discussion says monthly bills include both token usage and
Actions minute consumption for relevant Copilot review runs. GitHub's changelog
adds a concrete date: June 1, 2026 for private-repo Copilot review Actions
minute billing.

### TeaAgent implication

TeaAgent's cost model should include not only model calls but also:

- subagent fan-out
- review loops
- context reloads
- cache reads, if visible from provider data
- tool execution cost where applicable
- CI or external review minutes, if invoked

### Required work

- Extend model-route receipts with actual cost.
- Add per-phase cost budget and stop condition.
- Add "why did this cost so much?" post-run breakdown.
- Add warnings when review or subagent fan-out would exceed budget.

## Pain Point 6: Hook, Permission, And Human Gate Confusion

### Community signal

GitHub issues against Claude Code show user confusion around hook behavior. One
issue reports that a blocking `PreToolUse` hook stopped the agent instead of
letting it act on feedback. Another issue warns that a default
`permissionDecision: "allow"` hook can bypass native permission prompts.

### Product evidence

Claude Code hook docs say hooks can run as shell commands, HTTP endpoints, LLM
prompts, and experimental agent hooks. The docs also warn that command hooks run
with the user's full permissions.

### TeaAgent implication

TeaAgent's approval system is a differentiator only if hooks and extensions
cannot silently replace it. A human gate must be a packet of evidence plus an
explicit decision, not just a yes/no prompt.

### Required work

- Implement `SCL-P0-007` human review gate packets.
- Add hook/approval invariants: hook allow must not imply global approval.
- Add fail-closed tests for approval bypass patterns.
- Show "who granted authority" in run evidence.

## Pain Point 7: Skill, MCP, And Extension Supply-Chain Risk

### Community and security signal

The latest security discussion around coding agents increasingly treats MCP
servers, skills, hooks, and extension packages as supply-chain surfaces.
SkillJect research frames skills as reusable trusted guidance that can be
poisoned; memory-poisoning work shows that persistent state can become an attack
surface; prompt-injection posts warn that untrusted issue text, docs, webpages,
and tool output can influence agents with real tool authority.

### Product evidence

OpenCode skills are loaded on demand from repo or home directories. Claude Code
hooks and skills can run executable commands or scoped hooks. Pi extensions can
intercept tool calls and run with broad local permissions. These are useful
power-user features but they move trust from the model into the harness.

### TeaAgent implication

TeaAgent should preserve dynamic workflow, but never let dynamic capabilities
become trusted runtime assets without provenance, review, tests, and revocation.

### Required work

- Keep DSK-P0 candidate skill lifecycle as H3's first proof.
- Add skill/MCP provenance to run evidence.
- Add quarantine for new executable skill assets.
- Add revocation and "why was this loaded?" UX.

## Pain Point 8: Spec-First Process Overhead

### Community and product signal

Kiro's own May 2026 post acknowledges the tension: spec flow can feel too slow
when the user already knows the scope, but small clarifying questions can save
implementation time and tokens when a task has hidden assumptions. This is the
same product tension users report across coding agents: too much process blocks
small work, too little process lets complex work drift.

### TeaAgent implication

TeaAgent should use risk-adaptive spec requirements:

- small clear task: spec exemption receipt
- medium multi-file task: plan receipt
- high-risk task: spec plus human gate packet
- long-running task: spec plus goal record plus review artifact

### Required work

- Implement `SCL-P0-001` spec binding with exemptions.
- Add UX language that explains why a spec is required.
- Add tests proving low-risk commands are not buried in ceremony.

## Pain Point 9: Overeager Agents And Scope Creep

### Research signal

The Overeager Coding Agents paper separates scope expansion from capability
failure. It reports that consent wording materially changes behavior and that
permissive frameworks had much higher overeager rates than an ask-to-continue
framework.

### Community signal

Users describe agents doing plausible but unrequested work, rewriting
configuration, creating files in unexpected locations, or moving from the asked
fix into a broader refactor.

### TeaAgent implication

Approval alone is not enough. The agent needs an intent-drift detector that
compares current tool calls and diffs to the accepted objective.

### Required work

- Add scope budget and drift gate to high-risk runs.
- Include rejected alternatives and "not in scope" in spec/goal records.
- Make new files outside the planned work packet require explicit gate review.

## Pain Point 10: Fake Success And Weak Proof Bundles

### Community signal

Across agent forums, users report a familiar pattern: the agent says the task is
done, but did not actually run the script, execute the skill, summarize the
source, rerun tests, or inspect the failure. The RSS failure case in this repo
is the same class of defect.

### TeaAgent implication

TeaAgent should make "proof of use" visible:

- which skill loaded
- which skill executed
- which source artifact was read
- which command ran
- which output was summarized
- which tests/lints passed
- which gaps remain

### Required work

- Link this pain point to DSK-P0-003 and DSK-P0-004.
- Make run summaries distinguish "claimed" from "verified".
- Add validators that reject docs-only closure for runtime tasks.

## Pain-To-Control Mapping

| Pain point | Control loop | TeaAgent control object |
| --- | --- | --- |
| Routing opacity | Model routing | `model_route` receipt |
| Subagent misrouting | Dynamic workflow / model routing | phase handoff packet |
| Long-task drift | Loop / goal | persisted goal record |
| Context compaction loss | Spec-first / goal | checkpoint + spec hash |
| Memory pollution | Precise memory | memory quarantine and metadata |
| Memory poisoning | Precise memory / human review | memory gate packet |
| Review cost/noise | Synthesis review / model routing | review budget and review artifact |
| Cost surprise | Model routing | phase cost ledger |
| Hook permission bypass | Human review | fail-closed approval invariant |
| Skill/MCP supply chain | Dynamic workflow / human review | candidate lifecycle and revocation |
| Spec process overhead | Spec-first | risk-adaptive spec exemption |
| Overeager edits | Human review / spec-first | intent-drift gate |
| Fake success | Synthesis review | proof-of-use evidence bundle |

## TeaAgent Current Strengths

- Permission modes and approval tokens already give a strong authority model.
- Hash-chained audit and run evidence provide a basis for proof bundles.
- The dynamic skill candidate path already points toward governed extension.
- Budget and model-routing modules already exist as implementation anchors.
- TUI, chat, and agent mode already have daily-driver status tracking.
- Docs governance now has canonical status vocabulary and roadmap ownership.

## TeaAgent Current Gaps

- Route decisions are not yet a user-visible receipt.
- Goal state is not yet a single durable object across multiple runs.
- Memory does not yet have full provenance, TTL, confidence, and quarantine
  semantics.
- Review artifacts are not yet normalized enough to control review cost/noise.
- Human approval prompts do not yet always include the complete review packet.
- Skill execution proof is still weaker than skill discovery proof.
- Long-result handling is not yet uniform enough to prove source-backed summary.

## Product Direction

TeaAgent should position itself as a governed daily-driver harness:

- It should be more transparent than auto-routing IDE agents.
- It should be safer than full-power extension-first harnesses.
- It should be less process-heavy for small tasks than pure spec-first tools.
- It should be more durable for long tasks than chat-history agents.
- It should make cost and review work first-class, not after-the-fact surprises.

## Immediate Recommendations

1. Finish dynamic skill and long-result P0 work first because it is a real local
   failure case, not abstract strategy.
2. Add `model_route` receipts next because routing opacity and cost surprise are
   high-frequency community pains and narrow to implement.
3. Add persisted goal records before deeper long-running agent work.
4. Add memory quarantine before enabling more automatic memory writes.
5. Add synthesis review artifacts before expanding automated review.
6. Add human gate packets before trusting hook/skill/MCP expansion.
7. Add intent-drift tests for overeager behavior before broad autonomy modes.

## Open Questions

- Should TeaAgent show route receipts by default in TUI, or hide them behind a
  "trust details" panel?
- Should memory promotion require human review for all durable entries, or only
  entries that cross from run-local to project-wide scope?
- Should review budgets be hard caps or warning thresholds?
- Should spec exemptions be user-selectable, model-suggested, or policy-derived?
- Should skill/MCP revocation invalidate old run resumes that depended on the
  revoked asset?

## Conclusion

The community is not asking only for better models. It is asking for agents that
can explain themselves when they route, remember, review, spend, approve, and
continue. TeaAgent's opportunity is to turn those hidden control-plane events
into visible receipts and risk-adaptive gates.
