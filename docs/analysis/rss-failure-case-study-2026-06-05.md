# RSS Dynamic Skill Failure Case Study - 2026-06-05

## Purpose

This case study records the RSS summarization failure that motivated the dynamic
skill and long-result research pass. The goal is to preserve the concrete
failure mode so future implementation work tests the real problem instead of a
cleaner imaginary version.

## Evidence Boundary

The supplied `preferenceFolder/` was treated as copied preference evidence. It
was not treated as the current workspace root, and secret material was not read
or copied into this document.

Observed evidence came from non-secret configuration, run metadata, and file
shape indicators already summarized in the dynamic skill audit.

This document records behavior patterns, not private content.

## User Goal

The intended workflow was:

1. Ask the agent to create or use a skill for RSS feed summarization.
2. Have the agent actually fetch or read RSS feed content.
3. Summarize the feeds into a useful final artifact.
4. Keep enough evidence to know that the summary was source-backed.
5. Reuse the skill later as durable procedural knowledge.

This is a strong test because it combines:

- dynamic skill generation
- external or long input
- helper script creation
- artifact writing
- summarization quality
- source citation
- user trust

## Observed Failure Pattern

### 1. The skill appeared in an active compatibility directory

Observed pattern:

- The RSS skill was written under an `.opencode/skill/...` style path.
- Later runs could discover the skill.

Why this matters:

- Discovery made the skill look available.
- It did not prove TeaAgent's governed candidate lifecycle was followed.
- The user could reasonably wonder why a `.teaagent`-intended flow wrote into
  `.opencode`.

Missing invariant:

- Active skill directories must be protected, quarantined, or labeled as
  unmanaged when written directly.

### 2. The helper scripts were placeholder-sized

Observed pattern:

- `rss_summarizer.py` and `rss_summarize.py` were tiny files.
- File size was inconsistent with a real RSS parsing or summarization helper.

Why this matters:

- Creating a file can falsely signal progress.
- A script artifact is useful only if it contains real logic and is executed.

Missing invariant:

- A generated helper must have execution evidence and output validation.

### 3. The final artifact was too small to prove a real summary

Observed pattern:

- A reported RSS markdown artifact was small enough to be suspicious.
- It did not prove feed ingestion, categorization, citation, or source coverage.

Why this matters:

- RSS summarization is verifiable against fixture inputs.
- A summary should include feed titles, source URLs, dates, categories, and
  enough content to be useful.

Missing invariant:

- Output artifacts for source-backed tasks need mechanical checks.

### 4. Invalid model decision JSON interrupted the workflow

Observed pattern:

- Some runs ended with `invalid_model_decision_json`.
- Earlier behavior could make invalid decision output look like a task result.

Why this matters:

- Tool-using agents need failure to be visible.
- Invalid tool decision syntax is not a successful natural-language answer for
  workspace tasks.

Current improvement:

- Recent hardening makes workspace-task invalid decision JSON fail visibly.

Remaining invariant:

- A failed decision loop should produce a repairable state and should not claim
  skill success.

### 5. Long content was not governed as evidence

Observed pattern:

- RSS/WebSearch-style content can exceed prompt budgets.
- Without a standard envelope, the model may reason over partial previews.

Why this matters:

- The final answer can look plausible while omitting critical source content.
- The user wants daily-use reliability, not pretty partial summaries.

Missing invariant:

- Long result handling must preserve full artifacts, hashes, cursors, and source
  IDs.

## Root Cause Model

| Layer | Failure | Root cause hypothesis | Evidence needed |
| --- | --- | --- | --- |
| Skill creation | Skill was written to active compatibility path. | No protected path rule for active skill dirs. | Direct write test. |
| Governance | Skill looked loaded but not reviewed. | Candidate lifecycle not mandatory for generated skills. | Candidate provenance explain output. |
| Execution | Helper scripts were tiny or fake. | No execution or artifact-quality validator. | Script execution audit and output checks. |
| Long input | RSS/WebSearch data not preserved as evidence. | No standard long-result envelope. | Large fixture tool test. |
| UX | User could not tell what happened. | Skill state not surfaced as a first-class result. | CLI/TUI explainability acceptance. |

## What TeaAgent Should Have Done

Expected safe flow:

1. The agent proposes `rss-summary` as a skill candidate under
   `.teaagent/skill-candidates/rss-summary/`.
2. Candidate artifacts are generated:
   - `SKILL.md`
   - `REFERENCE.md`
   - `tool_call_contract.json`
   - `cost_profile.json`
   - `interaction_policy.json`
   - `provenance.json`
   - optional fixtures or eval dataset
3. Offline structural checks run.
4. A deterministic RSS fixture eval runs.
5. The user or policy approves install.
6. The skill installs to `.config/agent/skills/rss-summary/`.
7. A later run explicitly activates `rss-summary`.
8. The RSS input is loaded through a tool result envelope if large.
9. The final markdown artifact is checked against source titles and URLs.
10. The run evidence says whether the skill was verified or why it failed.

## Minimal RSS Acceptance Scenario

Prompt:

```text
Use the RSS summary skill to summarize the feeds in feedbro-subscriptions.opml.
Write categorized markdown into outputs/rss-summary.md with source links,
dates, and at least three bullets per category.
```

Fixture inputs:

- `feedbro-subscriptions.opml`
- `ai-news.xml`
- `security.xml`
- `devtools.xml`
- `large-feed.xml`

Assertions:

- `outputs/rss-summary.md` exists.
- File size is greater than a meaningful lower bound.
- At least three categories are present.
- At least N fixture item titles are present.
- Source URLs are present.
- Prompt-injection text from fixture feeds is not followed.
- Audit includes `rss-summary` activation.
- If a helper script is generated, audit proves it was executed.
- If any result is truncated, the envelope includes a full artifact pointer and
  hash.

## User Experience Failure

The painful part was not only that RSS summarization failed. The deeper UX
failure was that the system did not make the failure legible.

The user should have seen something like:

```text
RSS summary skill was generated as an unmanaged direct-write skill.
It was not reviewed or installed through TeaAgent candidate governance.
The generated helper script did not pass the RSS fixture eval.
No verified summary artifact was produced.
Next action: review candidate .teaagent/skill-candidates/rss-summary.
```

Instead, the workflow left ambiguity:

- Was the skill created?
- Was it loaded?
- Was it used?
- Did the script run?
- Was the output real?
- Why did `.opencode` receive the skill?

## Competitor Lessons Applied

### Agent Skills

The RSS skill should be a progressive folder asset, not just prompt text. The
model should load references and scripts only when needed, and evals should
prove the skill's value.

### Pi.dev

The workflow needs explicit activation and long-output truncation with full
output saved elsewhere. A preview-only RSS summary is not enough.

### Hermes

Agent-managed skill creation is powerful, but direct mutation of persistent
skill state is risky. TeaAgent should route changes through candidates.

### Community signal

Users tolerate agent failure better when the system keeps receipts. They do not
tolerate confident fake completion.

## Required Product Changes

| ID | Change | Priority | Why |
| --- | --- | --- | --- |
| RSS-CASE-001 | Add RSS offline fixture acceptance test. | P0 | Tests the exact failed workflow. |
| RSS-CASE-002 | Add active skill write quarantine. | P0 | Prevents `.opencode` compatibility path confusion. |
| RSS-CASE-003 | Add skill lifecycle audit states. | P0 | Separates loaded from used. |
| RSS-CASE-004 | Add long-result envelope. | P0 | Prevents preview-only source summaries. |
| RSS-CASE-005 | Add output artifact validators. | P0 | Stops fake tiny scripts and summaries. |
| RSS-CASE-006 | Add TUI/CLI skill trust display. | P1 | Makes failures legible to daily users. |

## Non-Goals

- Do not build a network-dependent RSS test first.
- Do not require a real LLM for the first CI acceptance test.
- Do not delete compatibility discovery paths.
- Do not claim all dynamic skills are unsafe.
- Do not copy private preference or secret material into docs.

## Conclusion

The RSS failure is the right north-star bug for dynamic skills. It is concrete,
user-visible, and hard to fake when tested properly. If TeaAgent can make this
flow pass with offline fixtures, governed candidate install, explicit
activation, long-result evidence, and checked output, then dynamic skill support
becomes credible for daily use.
