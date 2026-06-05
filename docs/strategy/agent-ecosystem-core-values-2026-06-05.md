# Agent Ecosystem Core Values - 2026-06-05

## Purpose

This document turns the latest competitor and community research into durable
strategy for TeaAgent. It records what other agent ecosystems appear to value,
what TeaAgent should learn from them, what it should reject, and how those
values change the near-term roadmap.

This is not a ranking of agents. It is a value map for product direction.

## Source Boundary

Evidence sources:

- Official Agent Skills documentation:
  - https://agentskills.io/home
  - https://agentskills.io/specification
  - https://agentskills.io/client-implementation/adding-skills-support
  - https://agentskills.io/skill-creation/evaluating-skills
- Official Pi documentation:
  - https://pi.dev/docs/latest
  - https://pi.dev/docs/latest/skills
  - https://pi.dev/docs/latest/packages
  - https://pi.dev/docs/latest/extensions
- Pi extension source documentation:
  - https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md
- Hermes skill documentation and issue evidence:
  - https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/skills.md
  - https://github.com/NousResearch/hermes-agent/issues/20273
  - https://github.com/NousResearch/hermes-agent/issues/429
- Community sentiment from Reddit and forum posts gathered in the June 5
  dynamic skill audit.
- Local TeaAgent evidence from:
  - `docs/analysis/dynamic-skill-generation-and-long-result-audit-2026-06-05.md`
  - `docs/plans/dynamic-skill-e2e-test-roadmap-2026-06-05.md`
  - `docs/modules/skills/spec.md`
  - `docs/modules/skills/risks.md`

Related June 5 control-loop package:

- `docs/analysis/seven-control-loops-competitor-survey-2026-06-05.md`
- `docs/strategy/seven-control-loops-product-direction-2026-06-05.md`
- `docs/architecture/seven-control-loops-teaagent-integration-map-2026-06-05.md`
- `docs/reviews/seven-control-loops-critical-questioning-2026-06-05.md`
- `docs/plans/seven-control-loops-work-items-2026-06-05.md`

Interpretation rules:

- Official docs are evidence of intended design, not proof of real user success.
- GitHub issues are evidence of observed failure modes, not proof of global
  product quality.
- Reddit/forum posts are operational signals, not controlled measurements.
- TeaAgent code and tests remain the highest-authority source for what TeaAgent
  can currently claim.

## Value Map

| Ecosystem | Core value | Evidence | TeaAgent response |
| --- | --- | --- | --- |
| Agent Skills | Progressive disclosure and reusable procedure | Skills are folder assets with metadata-first loading, optional references, scripts, and eval guidance. | Adopt the lifecycle distinction: discovered, activated, resource-read, used, verified. |
| Pi.dev | Malleable terminal-native extension | Skills, packages, extensions, settings, and CLI activation make the agent easy to bend from inside daily work. | Adopt explicit activation and package-like extensibility, but keep governance first-party. |
| Pi.dev | Long-output discipline | Extension docs require truncation with full output available elsewhere. | Adopt a uniform long-result envelope with preview, artifact pointer, hash, and cursor. |
| Hermes | Agent-managed procedural memory | `skill_manage` can create, patch, edit, delete, and add files to skills. | Adopt the ambition, not the direct mutation risk. Route generated skills through candidate review. |
| Hermes | Skill trust lifecycle | Skill docs discuss review, security, trust, hubs, and updates. | Convert TeaAgent's candidate artifacts into user-visible trust states. |
| Claude Code | High model quality and broad workflow support | Skills, plugins, MCP, connectors, and review workflows are part of the expected serious coding-agent loop. | Compete on proof, audit, and local control rather than raw model quality alone. |
| Codex | Multi-agent and worktree orchestration | Users increasingly expect parallel execution, review, automation, and durable work surfaces. | Keep multi-agent power tied to run evidence and mergeable artifacts. |
| OpenCode | Broad open agent surface | Terminal, IDE, desktop, LSP, agents, skills, and tool systems define a wide harness shape. | Borrow surface breadth selectively; avoid making the first hour too heavy. |
| Aider | Surgical edit clarity | Users value predictable diff-centered local work. | Preserve simple edit-review flows even while adding richer skill governance. |
| OpenHands | Sandbox and deployment realism | Docker/local/cloud guidance makes operational cost visible. | Keep sandbox claims concrete and acceptance-tested. |

## Core Values To Adopt

### 1. Skills must be progressive, not monolithic

Evidence:

- Agent Skills treats `SKILL.md` as a progressive disclosure entry point.
- Pi skills can be explicitly referenced when the model does not discover or
  read them automatically.

TeaAgent implication:

- The loader should not treat prompt injection as the whole skill experience.
- A skill's lifecycle must separate:
  - discovered
  - indexed
  - selected
  - activated
  - resource-read
  - used-in-run
  - output-verified

Required roadmap change:

- Implement `DSK-P0-001` skill lifecycle state machine.
- Add audit events that distinguish load from use.

### 2. Extensibility must be governed before it becomes persistent memory

Evidence:

- Hermes shows a powerful procedural-memory direction through agent-managed
  skills.
- Hermes issue evidence shows that agent-managed skill mutation can become a
  corruption path if the write surface is not guarded.

TeaAgent implication:

- TeaAgent should not normalize direct writes to active skill directories.
- Direct active-skill writes should be blocked, quarantined, or loudly labeled
  as unmanaged.

Required roadmap change:

- Implement `DSK-P0-002` direct active-skill write quarantine.
- Treat `.config/agent/skills`, `.claude/skills`, `.opencode/skill`, and
  `.opencode/skills` as protected active discovery surfaces.

### 3. Long results need a protocol, not a bigger prompt

Evidence:

- Pi extension docs set explicit truncation limits and require full output to be
  available elsewhere.
- TeaAgent's RSS failure showed tiny placeholder scripts and final artifacts
  that did not prove a real summary.

TeaAgent implication:

- WebSearch, RSS, file search, skill execution, and MCP tool outputs should
  return a common envelope when content is large.
- The model-visible preview must include enough metadata to know what was lost.
- The full artifact must be retrievable by offset and stable hash.

Required roadmap change:

- Implement `DSK-P0-004` long-result envelope.
- Add acceptance tests for large RSS/WebSearch fixtures.

### 4. Claims should be evidence objects

Evidence:

- Community agent users repeatedly complain about plausible fake success.
- The RSS case created files and claims without proving the end result.

TeaAgent implication:

- A run should be unable to claim skill success unless it can point to:
  - selected or activated skill
  - source inputs
  - generated or used helper
  - final artifact
  - mechanical output checks

Required roadmap change:

- Implement `DSK-P0-003` offline RSS fixture acceptance test.
- Implement `DSK-P1-001` behavioral skill eval harness.

### 5. Local control is a product value only if state is explainable

Evidence:

- Pi and other terminal-native agents appeal to users who want hackability and
  local control.
- TeaAgent's copied `preferenceFolder` showed how easily skill source location,
  project root, and user-level compatibility paths can confuse the operator.

TeaAgent implication:

- `skill explain` must be a primary UX surface, not a debugging afterthought.
- It must explain search order, winning path, shadowed paths, governance status,
  write target, and activation evidence.

Required roadmap change:

- Expand explainability after `DSK-P0-001`.
- Surface the same state in TUI and run evidence summaries.

## Values To Reject

### Reject YOLO as the default skill posture

Some agent ecosystems optimize for maximum convenience and let users add safety
through extensions. TeaAgent should take the opposite default: safe by default,
explicitly escapable for development.

Default rule:

- Reviewed candidate install is the normal path.
- Direct active-skill write is a development exception.

### Reject "loaded means used"

A loaded prompt package can still be ignored by the model. TeaAgent should stop
using load events as proxy evidence for skill success.

Default rule:

- `skill_load` proves availability only.
- `skill_used_for_output` requires runtime evidence.
- `skill_output_verified` requires mechanical checks.

### Reject preview-only summarization for evidence-heavy tasks

Summaries over RSS/WebSearch inputs are source-backed tasks. Preview-only
reasoning is not enough when the full source exists outside the prompt.

Default rule:

- If a tool result is truncated, the final artifact must cite source IDs that
  can be resolved to the full artifact.

### Reject self-modifying trusted skills

Automatic improvement is useful only when it forks or proposes changes. It must
not silently patch trusted, bundled, or installed skills.

Default rule:

- Agent-generated skill improvements produce candidates.
- Trusted skill mutation requires explicit review/install.

## TeaAgent Current Gap

TeaAgent already has several valuable ingredients:

- Candidate skill bundles.
- Artifact gates.
- Offline eval hooks.
- Skill explainability.
- Audit logs.
- Approval gates.
- Zero-dependency core posture.

The missing product property is behavioral closure.

TeaAgent can increasingly say:

- "This skill exists."
- "This skill passed structural checks."
- "This skill was installed through a governed path."

TeaAgent cannot yet reliably say:

- "This run activated the skill for this task."
- "The skill changed behavior relative to no skill."
- "The long input was preserved and used."
- "The final result was checked against source evidence."

That gap should become the center of H3 ecosystem trust.

## Roadmap Reorientation

### H3 should become dynamic-skill trust, not generic extensibility

Current H3 wording covers MCP, plugins, skills, hooks, subagents, and
automations. The research suggests H3 needs one sharper spine:

> Extensions are useful only when users can explain, revoke, and verify them.

Recommended H3 exit evidence:

- A generated RSS summary skill can be proposed, reviewed, installed, activated,
  used, and verified against offline fixtures.
- A direct write to an active skill directory is blocked or quarantined by
  default.
- A long WebSearch/RSS result is truncated into an envelope with a full artifact
  pointer, hash, and cursor.
- TUI and CLI can explain which skill was used and why.

### P0 should prioritize proof over ecosystem breadth

Do not add more skill surfaces before proving the current ones.

Highest ROI sequence:

1. Lifecycle state machine.
2. Direct-write quarantine.
3. RSS fixture acceptance.
4. Long-result envelope.
5. Behavioral skill eval.

### Documentation should name negative values

TeaAgent should be clear about what it will not optimize for:

- It will not prefer silent autonomy over proof.
- It will not treat compatibility discovery as trust.
- It will not let generated persistent memory bypass review.
- It will not claim long-source summarization from partial evidence.

## Follow-Up Work

| ID | Work | Priority | Reason |
| --- | --- | --- | --- |
| DSK-DOC-001 | Link this value map from `docs/INDEX.md` and current status. | P0 | Prevents the research from becoming buried dated evidence. |
| DSK-DOC-002 | Update roadmap H3 to reference dynamic skill trust. | P0 | Aligns ecosystem roadmap with the strongest current user concern. |
| DSK-DOC-003 | Add an RSS failure case study. | P0 | Keeps the concrete failure mode visible. |
| DSK-DOC-004 | Add a work-item ledger for dynamic skills and long results. | P0 | Converts strategy into executable work. |
| DSK-DOC-005 | Add architecture lifecycle flow. | P1 | Gives implementers a shared state model. |

## Open Questions

- Should direct active-skill writes be blocked at the workspace write tool layer,
  the skill writer layer, or both?
- Should `activate_skill` be a model-facing tool, a user command, or both?
- Should long-result envelopes be introduced first for RSS/WebSearch only or
  generalized immediately across all tools?
- Should behavioral skill evals use only deterministic fake adapters in CI, or
  also provide optional real-model eval profiles?

## Bottom Line

The competitor lesson is not "build more skills faster." The better lesson is:
make self-extension observable, reversible, and falsifiable. TeaAgent's most
credible differentiation is governed malleability: users can teach the agent,
but the system keeps receipts about whether the lesson actually worked.
