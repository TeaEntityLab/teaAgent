# Dynamic Skill E2E Test Roadmap - 2026-06-05

## Goal

Make TeaAgent's dynamic skill workflow objectively testable:

- A skill can be generated from a successful run.
- The generated skill enters a reviewed candidate bundle.
- The skill can be installed and activated.
- The later run uses the skill in a way that changes behavior.
- Long WebSearch/RSS/skill results remain usable through truncation, artifact
  pointers, pagination, and compaction.
- Final outputs are checked mechanically before the run claims success.

Related June 5 documentation package:

- [Agent Ecosystem Core Values](../strategy/agent-ecosystem-core-values-2026-06-05.md)
- [RSS Dynamic Skill Failure Case Study](../analysis/rss-failure-case-study-2026-06-05.md)
- [Dynamic Skill Critical Questioning](../reviews/dynamic-skill-critical-questioning-2026-06-05.md)
- [Dynamic Skill Lifecycle And Result Flow](../architecture/dynamic-skill-lifecycle-and-result-flow-2026-06-05.md)
- [Dynamic Skill And Long Result Work Items](dynamic-skill-and-long-result-work-items-2026-06-05.md)

## Priority Order

### P0 - Prove the Lifecycle, Not the Claim

#### DSK-P0-001: Skill Lifecycle State Machine

Define explicit states:

- `discovered`
- `indexed`
- `selected`
- `activated`
- `resource_read`
- `candidate_proposed`
- `candidate_eval_passed`
- `review_passed`
- `installed`
- `used_in_run`
- `output_verified`
- `superseded`
- `blocked`

Acceptance checks:

- `skill explain` reports search path, winning path, shadowed paths, write
  target, governance status, and activation mode.
- Audit log records state transitions, not only `skill_load`.
- A skill cannot be reported as `used_in_run` unless a runtime action references
  that skill name.

ROI:

- Very high. It directly turns vague success claims into inspectable facts.

Risk:

- Low. Mostly metadata and tests.

#### DSK-P0-002: Block or Quarantine Direct Active Skill Writes

Problem:

- The RSS failure wrote directly into `.opencode/skill`. Compatibility discovery
  made the skill visible, but the user could not tell whether this was a governed
  TeaAgent skill or an unmanaged file.

Plan:

- Add a protected path rule for active skill directories:
  - `.config/agent/skills/**`
  - `.claude/skills/**`
  - `.opencode/skill/**`
  - `.opencode/skills/**`
- Allow writes only through:
  - `skill candidate propose`
  - `skill candidate install`
  - an explicit `--allow-direct-skill-write` development flag
- If blocked, write the proposed content into `.teaagent/skill-candidates/` or a
  rejected proposal artifact with an actionable message.

Acceptance checks:

- Workspace write tool cannot write directly to active skill dirs by default.
- Candidate install can still write to `.config/agent/skills`.
- TUI message explains where the candidate was quarantined.

ROI:

- Very high. Prevents the exact "it went to `.opencode`" confusion.

Risk:

- Medium. Existing users may intentionally keep shared skills in `.opencode`.
  Provide explicit opt-in and migration notes.

#### DSK-P0-003: RSS Fixture Acceptance Test

Build an offline deterministic RSS test fixture.

Fixture files:

- `fixtures/rss/feedbro-subscriptions.opml`
- `fixtures/rss/ai-news.xml`
- `fixtures/rss/security.xml`
- `fixtures/rss/devtools.xml`
- `fixtures/rss/large-feed.xml`

Test prompt:

```text
Use the RSS summary skill to summarize the feeds in feedbro-subscriptions.opml.
Write categorized markdown into outputs/rss-summary.md with source links,
dates, and at least three bullets per category.
```

Assertions:

- Output file exists.
- Output file has minimum size, for example > 2000 bytes.
- Output includes at least three categories.
- Output includes at least N feed item titles from fixtures.
- Output includes source URLs.
- Output does not include fixture prompt-injection text as instructions.
- Audit shows selected or activated `rss-summary`.
- The helper script, if generated, was executed.

ROI:

- Very high. RSS is the user's concrete failed scenario.

Risk:

- Low if offline fixtures are used.

#### DSK-P0-004: Long Result Envelope

Add a standard envelope for large tool results:

```json
{
  "content_type": "text/markdown",
  "preview": "...",
  "truncated": true,
  "total_bytes": 123456,
  "preview_bytes": 50000,
  "artifact_path": ".teaagent/artifacts/tool-results/run-id/tool-id.txt",
  "content_hash": "sha256:...",
  "cursor": "offset:50000",
  "suggested_next_action": "read artifact_path with offset cursor"
}
```

Acceptance checks:

- A fake WebSearch/RSS tool returning > 80 KB produces an envelope.
- The model-visible observation includes the preview and artifact pointer.
- Full content is retrievable by offset.
- Compaction preserves artifact pointer and content hash.
- Final summary cites source IDs that exist in the full artifact.

ROI:

- Very high for daily usage. Long tool results are unavoidable.

Risk:

- Medium. It touches tool result shape and audit expectations.

### P1 - Make Generated Skills Actually Useful

#### DSK-P1-001: Behavioral Skill Eval Harness

Extend candidate eval from structural checks to behavioral checks.

Run each eval case in two modes:

- `without_skill`
- `with_skill`

Record:

- status
- produced files
- tokens
- duration
- tool calls
- assertion results

Assertions should be mechanical when possible:

- file exists
- JSON parses
- markdown contains source IDs
- row count matches fixture
- no prompt-injection phrase was followed
- no placeholder scripts remain

ROI:

- High. It detects skills that look valid but do not improve behavior.

Risk:

- Medium. Requires a scripted adapter or deterministic model harness for CI.

#### DSK-P1-002: Skill Invocation Audit

Add first-class events:

- `skill_indexed`
- `skill_selected`
- `skill_activated`
- `skill_resource_read`
- `skill_used_for_output`
- `skill_output_verified`

The event payload should include:

- skill name
- source path
- governance status
- token estimate
- activation cause: user explicit, model selected, config selected, eager
- run ID
- final output artifact paths

ROI:

- High. Debugging becomes possible in TUI and logs.

Risk:

- Low to medium. Event naming must remain stable.

#### DSK-P1-003: Dedicated Skill Activation Tool

Current prompt injection is ambiguous. Add an optional runtime tool:

```json
{
  "name": "activate_skill",
  "schema": {
    "skill_name": {"enum": ["rss-summary", "code-review", "..."]}
  }
}
```

Behavior:

- Registered only when skills exist.
- `skill_name` enum prevents hallucinated skill names.
- Returns tagged skill content, resource list, skill root, governance status, and
  usage constraints.
- Deduplicates if already activated.

ROI:

- High. It moves activation from implicit prompt hope to explicit runtime event.

Risk:

- Medium. Requires careful prompt and compaction integration.

#### DSK-P1-004: Script Promotion Rule

If a generated skill requires a helper script:

- The script belongs in `scripts/`.
- The skill must describe when to run it.
- The candidate eval must execute it against fixtures.
- The script must not be an untested one-off file in the workspace root.

Acceptance checks:

- Candidate with a script but no script eval fails review.
- Candidate with placeholder script fails minimum content/execution checks.
- Candidate with a working RSS parser script passes fixture eval.

ROI:

- High for RSS and data-processing skills.

Risk:

- Low.

### P2 - UX and Daily-Driver Improvements

#### DSK-P2-001: TUI Skill Diagnostics Panel

Show:

- loaded skills
- selected skills
- active skill
- governance status
- shadowed skills
- long-result artifacts
- output verification result

ROI:

- Medium to high. Helps users trust and debug the workflow.

Risk:

- Medium. TUI space is limited.

#### DSK-P2-002: RSS Summary Built-In Starter Skill

Ship a conservative built-in starter skill for RSS:

- `SKILL.md` under built-in or reviewed project skills.
- `scripts/rss_summarize.py`.
- `references/rss-output-contract.md`.
- Offline fixtures.
- Acceptance tests.

This should be an example of how dynamic skills should evolve: start with a
tested seed, then allow candidate patches.

ROI:

- Medium. It directly addresses user need and creates a reference pattern.

Risk:

- Medium if network fetching is included. Keep CI offline and make live network
  fetching optional.

#### DSK-P2-003: WebSearch Result Contract

For any future live web search tool, require:

- source URL
- title
- fetched date
- content hash
- preview
- full artifact path
- trust label: untrusted external content
- prompt-injection scan result
- citation/source ID

ROI:

- Medium to high. Prevents web outputs from becoming untraceable context.

Risk:

- Medium. Requires source-specific adapters.

## Test Matrix

| Area | Test | Why It Matters | Priority |
| --- | --- | --- | --- |
| Candidate lifecycle | propose -> eval -> review -> install -> explain | Prevents direct-write masquerade | P0 |
| Explicit activation | `--skill rss-summary` and activation tool | Proves user can force use | P0/P1 |
| Implicit activation | model sees index and activates by name | Proves normal UX | P1 |
| Shadowing | same name in `.config`, `.claude`, `.opencode`, user dir | Prevents wrong skill use | P0 |
| Direct write block | workspace write to active skill dir | Prevents unreviewed persistence | P0 |
| RSS fixture | OPML + multiple XML feeds | Replays failed user scenario | P0 |
| Long result | 80 KB/200 KB synthetic results | Proves truncation and retrieval | P0 |
| Prompt injection | feed item says "ignore instructions" | Prevents external content persistence | P0 |
| Compaction | activated skill survives compaction | Prevents mid-run skill amnesia | P1 |
| TUI diagnostics | visible skill status and artifact pointer | Makes failures debuggable | P2 |

## Proposed Acceptance Tests

### `tests/acceptance/test_dynamic_skill_generation_flow.py`

Scenarios:

- Generate candidate from a completed run.
- Verify artifacts exist.
- Run offline eval.
- Review passes.
- Install project skill.
- `skill explain` reports `candidate_installed`.
- A new run with `--skill` receives the skill content.

### `tests/acceptance/test_rss_skill_fixture_flow.py`

Scenarios:

- Seed or generate `rss-summary` candidate.
- Install it.
- Run against offline OPML/RSS fixtures.
- Verify `outputs/rss-summary.md` mechanically.
- Confirm no placeholder script is accepted.

### `tests/acceptance/test_long_tool_result_envelope_flow.py`

Scenarios:

- Fake tool returns large content.
- Envelope writes full artifact and preview.
- Agent reads continuation by cursor.
- Final output references source IDs from the full artifact.

### `tests/acceptance/test_skill_context_compaction_flow.py`

Scenarios:

- Activate skill.
- Inject many observations.
- Trigger compaction.
- Verify skill content tags, artifact pointers, and active-skill state remain.

### `tests/acceptance/test_active_skill_write_guard_flow.py`

Scenarios:

- Direct `workspace_write_file` into `.opencode/skill/name/SKILL.md` is blocked
  or quarantined.
- Candidate install remains allowed.
- Error message points to candidate workflow.

## Implementation Sequencing

### Sprint 1

1. Add active skill write guard.
2. Add `skill_activation` audit event and expose it in `skill explain`.
3. Add RSS fixture files.
4. Add RSS summary output validator.
5. Add acceptance test for installed candidate governance.

Exit criteria:

- RSS fixture cannot pass with a fake 12-byte script.
- Direct active skill writes are visible or blocked.

### Sprint 2

1. Add `ToolResultEnvelope`.
2. Add long-result artifact store under `.teaagent/artifacts/tool-results/`.
3. Add cursor-based artifact read helper.
4. Preserve envelope metadata during compaction.
5. Add synthetic long-result acceptance test.

Exit criteria:

- A 200 KB fake search result can be summarized using artifact continuation.

### Sprint 3

1. Add dedicated `activate_skill` tool.
2. Add behavioral with-skill vs without-skill eval mode.
3. Add TUI diagnostics panel or command.
4. Add built-in RSS starter skill or project fixture skill.

Exit criteria:

- A generated skill has measurable behavioral value over baseline.

## ROI Ranking

1. RSS fixture acceptance test: highest ROI because it targets a real failure.
2. Active skill write guard: highest safety ROI.
3. Long result envelope: highest reliability ROI for WebSearch/RSS.
4. Skill activation audit: highest debug UX ROI.
5. Behavioral eval harness: highest long-term quality ROI.
6. TUI diagnostics: high user trust ROI after the backend facts exist.
7. Built-in RSS starter skill: useful product feature, but should come after the
   lifecycle harness can prove it.

## Non-Goals

- Do not add live web dependencies to CI.
- Do not trust arbitrary community skills by default.
- Do not let background agents patch bundled or installed skills silently.
- Do not treat a final-answer sentence as verification.
- Do not solve all RSS feed formats in the first pass.

## Definition of Done

The workflow is usable when this command family is true in CI and locally:

```text
generate skill -> review/eval -> install -> explain -> activate -> run fixture ->
verify artifacts -> audit proves lifecycle
```

For the RSS case specifically:

- The summary markdown exists.
- It contains real fixture item titles and links.
- It is categorized.
- It records source coverage.
- It ignores feed-level prompt injection.
- It is impossible for a placeholder script or empty summary to pass.
