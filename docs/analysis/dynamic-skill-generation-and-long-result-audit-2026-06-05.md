# Dynamic Skill Generation and Long Result Audit - 2026-06-05

## Purpose

This audit reviews whether TeaAgent can support the workflow the user actually
wanted to test:

1. Dynamically generate a skill during or after a real task.
2. Install or activate that skill through a governed path.
3. Prove that the skill was actually used by the later agent run.
4. Handle long WebSearch, RSS, or skill-result payloads without silently losing
   the useful parts.
5. Produce a real checked artifact, not a plausible-looking script or summary
   claim.

The RSS example is a good failure probe because it combines every risky axis:
dynamic skill creation, external/long content, summarization quality, artifact
creation, and user-visible proof.

Companion documents created from this audit:

- [Agent Ecosystem Core Values](../strategy/agent-ecosystem-core-values-2026-06-05.md)
- [RSS Dynamic Skill Failure Case Study](rss-failure-case-study-2026-06-05.md)
- [Dynamic Skill Critical Questioning](../reviews/dynamic-skill-critical-questioning-2026-06-05.md)
- [Dynamic Skill Lifecycle And Result Flow](../architecture/dynamic-skill-lifecycle-and-result-flow-2026-06-05.md)
- [Dynamic Skill And Long Result Work Items](../plans/dynamic-skill-and-long-result-work-items-2026-06-05.md)

## Current Verdict

TeaAgent is partially ready, but not yet reliable enough for this workflow.

The low-level ingredients exist:

- Skills can be discovered from project and user directories.
- Skills can be injected into the model prompt.
- Candidate skills can be proposed, reviewed, evaluated offline, and installed.
- Candidate installs now carry provenance that `skill explain` can surface.
- Oversized `SKILL.md` files are truncated with audit warnings.
- Workspace file search has offset pagination.

The missing system property is end-to-end skill outcome verification. The current
code can prove "a skill was loaded"; it does not yet prove "the model used the
skill correctly and produced the required checked output." That is the core
reason the RSS flow could create tiny fake scripts and still appear to proceed.

## Local Evidence

### Supplied Preference Folder Evidence

The supplied `preferenceFolder/` is a copied `.teaagent`-style directory, not a
workspace root. When treated as a root, the loader will look for
`preferenceFolder/.teaagent/config.json`, not `preferenceFolder/config.json`.
That can accidentally mix the copied preference state with the current machine's
real user skill directories.

Observed config:

- `provider = "opencodezen-go"`
- `permission_mode = "read-only"`
- `max_iterations = 10`
- `max_tool_calls = 10`
- No `skill_search_dirs`
- No `skill_source_profile`

Observed run/memory evidence:

- The RSS skill was written into `.opencode/skill/rss-feeds/SKILL.md`.
- Later runs loaded `.opencode/skill/rss-feeds/SKILL.md`.
- `rss_summarizer.py` was written with only about 20 bytes.
- `rss_summarize.py` was written with only about 12 bytes.
- A reported RSS markdown output was only about 151 bytes.
- Several runs ended in `invalid_model_decision_json` or asked the user to do
  more narrowing instead of summarizing.

Conclusion: the previous RSS workflow proved that skill files could appear in a
discoverable directory. It did not prove a working RSS summarizer.

### Repository Evidence

Relevant code paths:

- `teaagent/skill_loader.py`
  - Discovers `.config/agent/skills`, `.claude/skills`, `.opencode/skill`,
    `.opencode/skills`, and user equivalents.
  - Supports `selected_names` and `skill_prompt_mode=index_only`.
  - Provides `explain_skill_activation()`.
- `teaagent/skill_writer.py`
  - Publishes direct project skills to `.config/agent/skills`.
  - This is not the full candidate governance path.
- `teaagent/skill_candidates.py`
  - Stores proposed candidates under `.teaagent/skill-candidates`.
  - Requires review and offline eval before install.
  - Installs project skills to `.config/agent/skills/<name>`.
- `teaagent/skill_candidate_artifacts.py`
  - Requires `SKILL.md`, `REFERENCE.md`, `tool_call_contract.json`,
    `cost_profile.json`, `interaction_policy.json`, and `provenance.json`.
- `teaagent/skill_eval.py` and `teaagent/skill_eval_dataset.py`
  - Run deterministic checks, but today these checks are mostly structural.
  - They do not run a with-skill vs without-skill behavioral eval.
- `teaagent/chat_agent.py`
  - Loads skills and records a `skill_load` audit event.
  - Invalid model decision JSON is now being hardened so workspace tasks fail
    visibly instead of returning a fake successful JSON string.
- `teaagent/workspace_tools/_files.py`
  - Search and list tools support pagination through offsets.
  - Knowledge/hybrid backends can return results, but there is no universal
    long-result envelope for all tools.

### Fresh Verification Performed

The focused verification suite passed after fixing candidate provenance
explainability:

```text
python3 -m pytest \
  tests/acceptance/test_skill_activation_explain_flow.py \
  tests/acceptance/test_skill_candidate_contract_policy_provenance_flow.py \
  tests/acceptance/test_skill_install_flow.py \
  tests/test_chat_agent.py -q

42 passed, 1 warning
```

What this proves:

- Skill discovery and prompt injection still work.
- Candidate provenance and install checks still work.
- `skill explain` can report candidate governance status.
- Invalid decision JSON behavior has focused regression coverage.

What this does not prove:

- A generated skill is behaviorally useful.
- A skill is activated on demand rather than merely loaded.
- RSS/WebSearch long payloads are summarized correctly.
- The final artifact is complete, source-backed, and checked.

## External Research Signals

### Agent Skills Standard

Agent Skills defines a skill as a folder with `SKILL.md` plus optional scripts,
references, and assets. It explicitly describes progressive disclosure:
metadata is loaded first, full `SKILL.md` loads when activated, and resources are
loaded only when needed.

Sources:

- https://agentskills.io/home
- https://agentskills.io/specification
- https://agentskills.io/client-implementation/adding-skills-support
- https://agentskills.io/skill-creation/evaluating-skills

Implications for TeaAgent:

- TeaAgent should distinguish "discovered", "activated", "resource loaded",
  and "used successfully" as separate states.
- Skill content should be protected during context compaction once activated.
- User-explicit activation should be a first-class UX path.
- Evals should compare with-skill vs without-skill output, not only validate
  files.

### Pi Coding Agent

Pi documents a small core extended through TypeScript extensions, skills, prompt
templates, themes, and packages. Pi can load global, project, package, settings,
and CLI-specified skills. It also documents that models do not always read the
full skill automatically, so explicit `/skill:name` activation can be needed.

Pi extension docs also require tool output truncation. The documented built-in
limit is 50 KB or 2000 lines, with the full output saved elsewhere and the model
informed where to find it.

Sources:

- https://pi.dev/docs/latest
- https://pi.dev/docs/latest/skills
- https://pi.dev/docs/latest/packages
- https://pi.dev/docs/latest/extensions
- https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md

Implications for TeaAgent:

- Dynamic extensibility is useful, but the agent must not rely on implicit
  model obedience to prove activation.
- Tool results need a uniform truncation and artifact-pointer protocol.
- Extension or skill output should include a machine-readable summary, not only
  free text.

### Hermes Agent

Hermes documents agent-managed skills through a `skill_manage` tool: the agent
can create, patch, edit, delete, and add supporting files. Hermes treats this as
procedural memory. Hermes docs also describe security scanning, trust levels,
skill hubs/taps, update lifecycle, and skill bundles.

Sources:

- https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/skills.md
- https://github.com/NousResearch/hermes-agent/issues/20273
- https://github.com/NousResearch/hermes-agent/issues/429

Critical signal:

- A reported Hermes bug shows that agent-managed skills can become a persistent
  corruption vector if code-level guards do not prevent background agents from
  editing bundled or hub-installed skills.

Implications for TeaAgent:

- TeaAgent's quarantine-first candidate path is directionally safer than direct
  self-editing.
- Direct writes into active skill directories should be treated as unmanaged,
  user-visible, and possibly blocked or quarantined.
- Background or automatic skill improvement must never patch trusted/bundled
  skills without an explicit fork/customize flow.

### Community Feedback

Community posts should be treated as sentiment and operational signal, not as
controlled evidence. Recurring patterns are still useful:

- Users report that context waste before implementation degrades agent output.
  They value indexes, focused agents, and context routing.
  Source: https://www.reddit.com/r/LocalLLaMA/comments/1rr5fo5/why_ai_coding_agents_waste_half_their_context/
- A Pi user credited a plan-first skill with making local-model coding more
  reliable.
  Source: https://www.reddit.com/r/LocalLLaMA/comments/1stjwg5/been_using_pi_coding_agent_with_local_qwen36_35b/
- Users report that loaded skills can still be ignored when the model does not
  understand how to invoke them.
  Source: https://www.reddit.com/r/LocalLLaMA/comments/1rblce7/i_created_yet_another_coding_agent_its_tiny_and/
- Some OpenCode users move from MCPs to CLI-plus-skills because MCP context
  overhead can become too large.
  Source: https://www.reddit.com/r/opencodeCLI/comments/1sq582m/what_skills_became_part_of_your_workflow/
- Local-model users repeatedly ask for context windowing, explicit file
  selection, small tool outputs, resumable task state, and separation between
  planning, editing, and verification.
  Source: https://www.reddit.com/r/LocalLLaMA/comments/1tqohv6/which_coding_agent_features_are_useful_for_local/

Implications for TeaAgent:

- The RSS failure is not surprising. The system lacked enough activation proof,
  result shaping, and verification pressure.
- "More skill text" is not the fix. Smaller skills, explicit activation, tested
  scripts, and result envelopes are the fix.

### Academic Signals

SkillSmith argues that raw skill injection can waste tokens and repeated
reasoning. It proposes compiling skills into smaller runtime interfaces and
reports reduced solve-stage token usage, iterations, time, and cost.

Source:

- https://arxiv.org/abs/2605.15215

An empirical study of AI coding tool bugs reports that many user-facing failures
are functionality, integration, configuration, terminal, and command-execution
problems.

Source:

- https://arxiv.org/abs/2603.20847

Implications for TeaAgent:

- TeaAgent should test integration boundaries, not only pure functions.
- Skill execution should move repeated scripts into checked resources, not rely
  on the model repeatedly writing throwaway scripts.

## Critical Questions

1. Does "skill generated" mean a governed candidate was created, or merely that
   the model wrote a `SKILL.md` file?
2. Does "skill used" mean the skill appeared in the prompt, was explicitly
   activated, loaded resources, or changed the output measurably?
3. Can the user see which skill path won when `.config`, `.claude`, and
   `.opencode` all contain overlapping skill names?
4. Can a model directly write to `.opencode/skill` or `.config/agent/skills`
   and bypass candidate review?
5. If a tool returns 100 KB of feed entries, does the model receive a useful
   preview plus a resumable pointer, or a random truncation?
6. If the model writes a helper script, does the harness verify script size,
   execution, output file existence, and artifact content?
7. If the final answer says "summarized," which assertion proves that a summary
   exists and includes real feed items?
8. Does compaction preserve activated skill instructions and tool-result
   artifact pointers?
9. Are RSS/WebSearch results considered untrusted input before persistence into
   memory or skills?
10. Does TUI chat expose enough trace to debug why a skill was ignored?

## Failure Model

### FM-DSK-001: Active Directory Write Masquerades as Reviewed Skill

The model writes a skill directly into `.opencode/skill` or
`.config/agent/skills`. The loader discovers it, so the system appears to work,
but no candidate artifacts, evals, or provenance exist.

Required control:

- Direct active-skill writes should be marked `governance_status=direct_write`.
- Candidate installs should be marked `governance_status=candidate_installed`.
- TUI and CLI should show that distinction.

### FM-DSK-002: Prompt Injection Without Activation Proof

A skill is loaded into the system prompt, but the model ignores it or fails to
read referenced resources.

Required control:

- Add `skill_activation` and `skill_resource_read` audit events.
- Add explicit `/skill NAME` and CLI `--skill NAME` paths for user-forced
  activation.
- Add behavioral evals where with-skill must outperform without-skill on
  objective assertions.

### FM-DSK-003: Fake Helper Script

The model writes a tiny or placeholder script, then claims the task is complete.

Required control:

- Require helper-script execution evidence for generated skill tasks.
- Validate expected output artifacts by file existence, minimum size, schema,
  source count, and content assertions.
- Treat "script written but never executed" as failure.

### FM-DSK-004: Long Tool Result Loses the Important Data

RSS/WebSearch returns too much text. The harness truncates without stable
pagination, artifact pointers, source IDs, or summaries.

Required control:

- Introduce a `ToolResultEnvelope` with preview, truncation metadata,
  artifact path, content hash, cursor, and suggested next read.
- Preserve envelope metadata through audit logs and compaction.

### FM-DSK-005: Untrusted External Content Becomes Persistent Instructions

Web pages or feed items include prompt injection. The model converts the content
into skill instructions or memory.

Required control:

- Treat web/RSS content as untrusted.
- Never auto-promote untrusted content into active skills.
- Keep candidate quarantine and require review/eval before install.

## Current Structure Assessment

### Good

- The candidate workflow is a better safety foundation than direct self-editing.
- Provenance, policy, cost, and reference artifacts already exist.
- `skill explain` is the right UX direction.
- Loader search order is deterministic and now documented.
- Invalid JSON workspace task behavior is being hardened.

### Weak

- The direct `SkillWriter` path and candidate path are separate mental models.
- `.opencode/skill` compatibility is useful but easy to misread as TeaAgent's
  write target.
- Offline evals are structural, not behavioral.
- Skill activation is mostly prompt-state, not a first-class runtime event.
- There is no universal long-result protocol across RSS/WebSearch/skills/tools.
- TUI chat likely cannot yet explain "why did this skill not run?" clearly.

### Missing

- A deterministic RSS fixture runner.
- A generated-skill e2e test that installs a candidate and then uses it in a new
  run.
- A long-result fixture that forces truncation and resumes from the artifact.
- A final-output validator for RSS summaries.
- A model-visible, user-visible activation ledger.
- A guard that blocks or quarantines active skill directory writes from ordinary
  workspace write tools unless the user explicitly asks for unmanaged direct
  write.

## Recommendation

Do not copy Hermes' fully autonomous self-editing loop yet. Adopt Pi's
progressive disclosure and explicit activation UX, Hermes' lifecycle ambition,
and TeaAgent's own quarantine/provenance posture.

The target architecture should be:

```text
Task success evidence
  -> candidate skill proposal
  -> candidate bundle artifacts
  -> offline structural eval
  -> behavioral with-skill eval
  -> human or policy review
  -> install with provenance
  -> explicit activation or audited model activation
  -> checked output artifact
  -> optional post-use candidate patch
```

The most important product principle:

> A skill is not trusted because it exists. A skill is trusted only after it has
> provenance, tests, activation evidence, and output evidence.
