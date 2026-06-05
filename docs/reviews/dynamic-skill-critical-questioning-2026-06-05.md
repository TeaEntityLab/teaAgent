# Dynamic Skill Critical Questioning - 2026-06-05

## Purpose

This review challenges TeaAgent's current dynamic skill direction after the RSS
failure evidence and competitor research. It is intentionally skeptical. The
goal is not to prove that TeaAgent is bad; the goal is to prevent attractive
skill features from becoming another way for the agent to fake progress.

## Review Stance

Dynamic skills are only valuable if they produce durable improvement in later
runs. A generated `SKILL.md` is not the achievement. The achievement is a later
task where the system can prove that the skill was activated, used, and verified
against source evidence.

## Critical Questions

### 1. Are we confusing discoverability with capability?

Concern:

- The loader can discover skills in several compatibility directories.
- A discovered skill may appear in the prompt.
- A model can still ignore it, misunderstand it, or fail before using it.

Current evidence:

- `skill_loader.py` can expose discovered skills and explain search paths.
- `chat_agent.py` records skill load events.
- The RSS run evidence showed loaded skill files but no reliable summary.

What would falsify the concern:

- An audit event sequence showing `skill_selected`, `skill_activated`,
  `skill_resource_read`, `skill_used_for_output`, and
  `skill_output_verified`.
- A test proving the same RSS prompt fails without the skill and passes with the
  skill.

Required change:

- Do not call a dynamic skill workflow successful until behavioral evidence
  exists.

### 2. Are we letting generated files masquerade as completed work?

Concern:

- The previous RSS flow produced tiny helper scripts.
- A file write can create a satisfying sense of progress even when the file is a
  placeholder.

Current evidence:

- The supplied preference evidence recorded `rss_summarizer.py` and
  `rss_summarize.py` as tiny files.
- The final markdown artifact was far too small to represent the requested
  summary.

What would falsify the concern:

- Tests that assert minimum artifact size, expected source titles, source URLs,
  categories, dates, and prompt-injection resistance.
- Audit evidence that the helper script was executed, not only written.

Required change:

- RSS acceptance tests must inspect output content and source coverage, not only
  command status.

### 3. Are we over-trusting the model's intent report?

Concern:

- A model can say it used a skill or summarized a feed without doing either.
- Natural-language claims are not sufficient run evidence.

Current evidence:

- TeaAgent already values audit logs and approval gates, but skill use is still
  partly inferred from context injection.
- The dynamic skill audit states that TeaAgent lacks end-to-end skill outcome
  verification.

What would falsify the concern:

- Skill usage events emitted by code paths, not by model self-report.
- Final output validators that inspect artifacts independently of model claims.

Required change:

- Add `skill_output_verified` only after deterministic checks pass.

### 4. Are active skill directories too easy to corrupt?

Concern:

- Compatibility discovery scans `.opencode/skill` and similar paths.
- If agents can write there directly, a generated skill becomes active without
  candidate review or provenance.

Current evidence:

- The RSS failure wrote into `.opencode/skill/rss-feeds/SKILL.md`.
- Hermes issue evidence shows that agent-managed skill mutation can corrupt
  installed or bundled skill surfaces if not guarded.

What would falsify the concern:

- Workspace write tools reject active skill directory writes by default.
- A direct-write attempt creates a quarantined candidate with a clear operator
  message.
- `skill explain` labels unmanaged active skills.

Required change:

- Block or quarantine direct writes to active skill directories.

### 5. Are we building a skill ecosystem before proving one skill loop?

Concern:

- Skills, plugins, MCP, hooks, and subagents all compete for attention.
- Without a single validated dynamic skill loop, more ecosystem surface area can
  multiply failure modes.

Current evidence:

- H3 roadmap currently names broad ecosystem trust.
- The user specifically cares about dynamic skills and long results because RSS
  failed.

What would falsify the concern:

- A green E2E flow where an RSS skill is generated, reviewed, installed,
  activated, used, and verified.

Required change:

- Treat RSS as the H3 spine test before adding more generic extensibility.

### 6. Are long results being treated as a prompt-size inconvenience instead of
an evidence-chain problem?

Concern:

- The issue is not only that long results are too large.
- The issue is that the model may make final claims from an incomplete preview.

Current evidence:

- Pi docs explicitly require truncation with full output stored elsewhere.
- TeaAgent has pagination in some file tools but no universal long-result
  envelope for web/RSS/skill outputs.

What would falsify the concern:

- A tool result envelope with preview, total bytes, preview bytes, artifact path,
  content hash, cursor, and source IDs.
- A final summary validator that resolves citations back to the full artifact.

Required change:

- Implement a long-result envelope before trusting WebSearch/RSS summaries.

### 7. Are we asking users to understand too many skill surfaces?

Concern:

- TeaAgent supports Agent Skills prompt packages and executable skill tools.
- It also discovers compatibility directories from other ecosystems.
- Users may not know which surface owns a failure.

Current evidence:

- `docs/modules/skills/spec.md` now distinguishes prompt packages from
  executable tools.
- The copied preference folder confused `.teaagent` expectation with
  `.opencode` writes.

What would falsify the concern:

- `skill explain` shows the surface type, write target, governance status, and
  activation state.
- TUI shows "reviewed candidate", "unmanaged compatibility skill", or
  "executable tool" without requiring the user to inspect paths.

Required change:

- Make skill source and trust state part of the user-facing UX.

### 8. Are we making enough room for failure?

Concern:

- If a skill cannot summarize RSS, that is useful information only when the
  system records why.
- A failed dynamic skill loop should produce an actionable repair task, not a
  silent hallucinated artifact.

Current evidence:

- Invalid decision JSON was previously able to look like a fake result path in
  some flows.
- Recent hardening makes workspace-task invalid decision JSON fail more
  visibly.

What would falsify the concern:

- Failure states such as `candidate_eval_failed`, `activation_failed`,
  `long_result_unread`, and `output_verification_failed`.
- TUI and CLI display next actions for each failure.

Required change:

- Dynamic skill lifecycle needs blocked/failure states, not only happy states.

## Counterarguments

### Counterargument: Direct skill writes are useful for power users

This is true. Power users may want to edit `.opencode/skill` or
`.config/agent/skills` directly.

Resolution:

- Keep an explicit development flag or manual path.
- Do not make direct writes the default agent behavior.
- Label direct writes as unmanaged in explainability output.

### Counterargument: Behavioral evals are expensive and brittle

This is partly true. Real-model evals can be slow and nondeterministic.

Resolution:

- Start with deterministic fake-adapter acceptance tests.
- Use fixture RSS feeds.
- Add optional real-model eval profiles later.

### Counterargument: Long-result envelopes add complexity

This is true.

Resolution:

- The complexity already exists implicitly and causes fake summaries.
- A standard envelope reduces duplicated ad hoc truncation behavior.

### Counterargument: Skills should be simple prompt files

This is true for many skills.

Resolution:

- Simple skills can stay simple.
- Claims about task success still need output evidence when the task has
  objective artifacts or source inputs.

## Risk Register Additions

| Risk | Severity | Trigger | Required control |
| --- | --- | --- | --- |
| Prompt-only skill ignored | High | Skill is loaded but not activated or used. | Lifecycle audit events and behavioral eval. |
| Direct active-skill corruption | High | Agent writes to active discovery dirs. | Protected path quarantine. |
| Long-result evidence loss | High | Tool output is truncated without artifact pointer. | Long-result envelope. |
| Fake helper artifact | High | Script is written but not executed or meaningful. | Output validators and execution evidence. |
| Skill source confusion | Medium | Compatibility path shadows governed path. | `skill explain` and TUI trust state. |
| Skill ecosystem sprawl | Medium | New surfaces added before one loop is proven. | RSS spine test as H3 gate. |

## Required Evidence Before Calling This Done

TeaAgent should not claim dynamic skill reliability until the following evidence
exists:

- A generated skill candidate bundle with required artifacts.
- A passed offline structural eval.
- A passed behavioral eval against fixtures.
- A reviewed install to the canonical project skill directory.
- An activation event in a later run.
- A source-backed final artifact.
- A validator that checks the final artifact.
- A long-result artifact pointer when source content is truncated.

## Product Direction

The right product posture is:

> TeaAgent can learn new skills, but it proves the lesson before trusting it.

This is stricter than the fastest self-extension systems. That strictness is a
feature for users who want a daily driver, not just a demo loop.

## Follow-Up Work

| ID | Task | Priority | Acceptance |
| --- | --- | --- | --- |
| DSK-CRIT-001 | Add lifecycle events beyond `skill_load`. | P0 | Audit shows activation and verification states. |
| DSK-CRIT-002 | Add RSS fixture acceptance test. | P0 | Output cites fixture titles and URLs. |
| DSK-CRIT-003 | Add protected active skill write rule. | P0 | Direct writes are blocked or quarantined. |
| DSK-CRIT-004 | Add long-result envelope. | P0 | Large fake feed output has preview plus retrievable artifact. |
| DSK-CRIT-005 | Add skill source/trust state to TUI. | P1 | User can see reviewed vs unmanaged skill state. |

## Closing Judgment

TeaAgent's direction is promising precisely because it already values audit,
approval, and candidate governance. The risk is that dynamic skills could sneak
around those values by looking like harmless prompt files. The project should
treat that as a first-class trust boundary.
