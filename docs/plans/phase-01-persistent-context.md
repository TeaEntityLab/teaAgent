# Phase 01: Persistent Context — Create CLAUDE.md & Refactor AGENTS.md

**Priority:** P0
**Concept doc:** [Persistent Context Strategy](../docs/architecture-reflection/02-persistent-context-strategy.md)
**Estimated effort:** 2-3 sessions
**Dependencies:** None

## Objective

Create a `CLAUDE.md` file with stable architecture context and refactor `AGENTS.md` to hold only ephemeral working memory. Prevent architectural drift across AI agent sessions.

## Tasks

### Task 1.1: Extract stable architecture content from AGENTS.md

- [ ] Read current `AGENTS.md` and extract:
  - Architecture section (lines 5-7)
  - Tool Governance section (lines 11-14)
  - Runtime Safety section (lines 18-20)
  - Skills section (lines 24-25)
- [ ] Remove these sections from AGENTS.md
- [ ] Add header to AGENTS.md: `> Stable architecture context moved to CLAUDE.md`

**Verification:** AGENTS.md no longer contains architecture/tool governance/runtime safety rules.

### Task 1.2: Create CLAUDE.md from extracted content

- [ ] Write CLAUDE.md at project root with:
  - Project identity (one paragraph: what TeaAgent is, what it is not)
  - Architecture principles (from AGENTS.md + ADR index)
  - Key module map (teaagent/ top-level directories with one-line purpose)
  - Design patterns (factory, adapter, policy chain — from architecture.md)
  - Known trade-offs (governance-first means...)
  - Link to ADR index
  - Link to architecture.md
- [ ] Target file size: 80-120 lines (not a wiki — minimal reference)

**Verification:** CLAUDE.md exists at project root. AI agents starting a new session read it automatically.

### Task 1.3: Add session start/end prompt template

- [ ] Create a minimal session template in CLAUDE.md:
  - Session start: re-read scope document + CLAUDE.md
  - Session end: log decisions, update module map if changed
- [ ] Template is embedded in CLAUDE.md as a comment block

**Verification:** 3 consecutive test sessions show consistent architectural decisions with no drift.

### Task 1.4: Wire update triggers

- [ ] Add CLAUDE.md update to definition of done for new ADRs
- [ ] Add CLAUDE.md update checklist item for structural module changes

**Verification:** Next ADR creation prompts CLAUDE.md review.

## Success Criteria

- [ ] CLAUDE.md exists and is reviewed on architectural changes
- [ ] AGENTS.md no longer contains duplicated stable context
- [ ] AI agents produce consistent architectural decisions across sessions
- [ ] Total maintenance overhead ≤5 minutes per ADR

## Rollback

If CLAUDE.md causes confusion (AI reads both files and gets conflicting context):
- Revert to AGENTS.md as single source of truth
- Add explicit precedence rules at the top of both files
