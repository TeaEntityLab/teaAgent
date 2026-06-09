# 02: Persistent Context Strategy

> **Core question:** How should AI-accessible project context be structured to prevent architectural drift across sessions?
> **Priority:** P0 — structural risk that compounds if left unaddressed.
> **Last reviewed:** 2026-06-09
> **Depends on:** [01-founder-playbook-reflection.md](01-founder-playbook-reflection.md) (Learning 3)
> **Work plan:** [Phase 01: Persistent Context](../../plans/phase-01-persistent-context.md)

## Problem Statement

The Founder's Playbook warns that AI-generated technical debt compounds when architectural decisions are not recorded in a location AI agents can read. Every new session re-derives foundational decisions, causing the codebase to drift from a coherent mental model.

TeaAgent's current state:

| Artifact | Purpose | Current Health |
|----------|---------|----------------|
| `AGENTS.md` | AI project instructions + cross-session memory | ❌ Mixed: stable rules + ephemeral context in one file |
| `CLAUDE.md` | Claude Code persistent context | ❌ Does not exist |
| `.teaagent/memory.jsonl` | 3-tier memory catalog | ✅ Functioning, auto-managed |
| ADR docs | Architecture decisions | ✅ 29 records, well-structured |
| `docs/architecture.md` | System overview | ✅ Well-maintained |

The paradox: **a governance-first agent harness has the least governed AI context file in its own repository.**

## Design Goals

1. **Separation of stable and ephemeral**: Architecture rules (stable) must not share a file with session memory (ephemeral).
2. **AI-accessible first**: Context must be in a format and location that the project's own AI agents can read automatically.
3. **Versioned**: Changes to architecture context should be reviewable and revertible (git-tracked).
4. **Minimal maintenance burden**: Context files must survive without active curation — they should be updated as part of normal development workflow (ADR creation, module changes), not as a separate overhead task.

## Proposed Architecture

### Tier 1: Stable Architecture Context (`CLAUDE.md`)

**Purpose:** Immutable reference that every AI session reads. Contains what never changes day-to-day.

```
CLAUDE.md                    # Project root — auto-discovered by Claude Code / OpenCode
├── Project Identity         # One-paragraph: what TeaAgent is, what it is not
├── Architecture Principles  # From ADRs and operating rules
│   ├── Thin harness (governance belongs here, reasoning belongs in model/skills)
│   ├── Protocol assets over vendor-specific assets
│   ├── No second agent framework without ADR
│   └── Tools registered through ToolRegistry with schema + annotations
├── Key Module Map           # Directory → purpose (living, updated on structural changes)
├── Design Patterns          # Recurring patterns: factory, adapter, etc.
├── Known Trade-offs         # Explicit: what was consciously accepted and why
└── Decision Log             # Link to ADR index + recent decisions
```

**Content sourced from:**
- `AGENTS.md` (stable rules section)
- `docs/architecture.md`
- ADR index
- `AGENTS.md` operating rules (Architecture, Tool Governance, Runtime Safety, Skills)

**Update triggers:**
- New ADR → add link
- New module → update module map (one line)
- New pattern → add to patterns section

### Tier 2: Working Memory (`.claude/MEMORY.md` or equivalent)

**Purpose:** Cross-session learnings that are useful but not architecturally binding. Failure cards, user preferences, context from recent sessions.

**TeaAgent already has this** via:
- `.teaagent/memory.jsonl` (3-tier: Project/Personal/Auto)
- Failure cards with automated invalidation
- Context compaction

The existing Memory Catalog is **more sophisticated** than a flat MEMORY.md. The issue is that it's not wired into how AI agents read project context. The tool that reads CLAUDE.md is different from the tool that queries memory.jsonl.

### Tier 3: Session Logs (Automatic)

**Purpose:** Each AI session's trace for replay and reference.

**TeaAgent already has this** via RunStore (JSONL with hash-chained audit, replay capability).

### The Gap

The gap is not in capability — TeaAgent has Tier 2 and Tier 3 already, both more sophisticated than flat files. The gap is:

1. **No Tier 1 file exists** (no CLAUDE.md equivalent for stable architecture context)
2. **AGENTS.md mixes Tier 1 and Tier 2 content** — stable rules and ephemeral memory coexist, causing both to degrade
3. **No defined interface between tiers** — context queries don't know which tier to consult for which question

## Recommendation

### Phase 1 (Immediate — P0)

**Create `CLAUDE.md`** from the stable portions of `AGENTS.md`:

Extract from `AGENTS.md`:
- Architecture section (lines 5-7: thin harness, protocol assets, no second framework)
- Tool Governance section (lines 11-14: registration, schema, destructive tools, actionable errors)
- Runtime Safety section (lines 18-20: iteration limits, audit, externalized state)
- Skills section (lines 24-25: SKILL.md short, review supply-chain)

Add from `docs/architecture.md`:
- System overview diagram
- Key module directory map (teaagent/ top-level dirs with one-line purpose)
- Design patterns (factories, adapters, policy chain)
- URL to ADR index

Add from `01-founder-playbook-reflection.md`:
- Project identity statement (one paragraph)
- Known trade-offs (governance-first means...)

**Result:** `CLAUDE.md` is ~80-120 lines, stable, git-tracked, reviewed on changes.

### Phase 2 (Short-term — P1)

**Refactor `AGENTS.md`:**

Strip all stable architecture content from AGENTS.md. Keep only:
- Session-rolling context (claude-mem section)
- Dynamic project-state notes
- Cross-session learnings that are not yet stable enough for CLAUDE.md

Add a header: `> This file contains ephemeral working memory. Stable architecture context is in CLAUDE.md.`

### Phase 3 (Medium-term — P2)

**Wire Tier 1-3 together:**

When an AI agent starts a session:
1. Read `CLAUDE.md` → stable architecture context
2. Query Memory Catalog → relevant failure cards and learnings
3. Load recent session traces from RunStore → context for continuity

This creates a unified context pipeline that respects the stable/ephemeral boundary.

## Success Criteria

- [ ] `CLAUDE.md` exists at project root with stable architecture context
- [ ] AGENTS.md no longer contains stable architecture rules (only ephemeral memory)
- [ ] AI agents starting a new session automatically load context from both CLAUDE.md and Memory Catalog
- [ ] No context drift detectable across 3+ consecutive sessions on the same task
- [ ] CLAUDE.md updates are triggered by ADR creation (not as standalone overhead)

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| CLAUDE.md becomes stale | Medium | Tie update triggers to existing workflows (ADR, module creation) |
| Two sources of truth (CLAUDE.md vs AGENTS.md) | Medium | Clear header in AGENTS.md pointing to CLAUDE.md for stable context |
| Overhead of maintaining another file | Low | CLAUDE.md is designed to be minimal (not a wiki) |
| AI ignores CLAUDE.md | Low | Claude Code and OpenCode auto-discover it at project root |

## References

- Founder's Playbook Learning 3: "CLAUDE.md Is Not Documentation — It's the Codebase's Memory"
- Claude Code docs: [Using CLAUDE.md files](https://claude.com/docs/claude-code/settings/claude-md)
- TeaAgent's own Memory Catalog: `teaagent/memory/`
- Context compaction: `teaagent/context_compaction.py`
