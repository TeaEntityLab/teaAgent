# TeaAgent Terminology Guide

**Last reviewed:** 2026-08-26 (Effect Authority Vocabulary added; EFX-001–003)

> **Review trigger:** Canonical terminology or state vocabulary changes.

This document standardizes terminology across all TeaAgent documentation.

## Canonical Core Nouns (WDC-004)

These nouns are frozen for general-user documentation. Use them consistently;
do not invent synonyms in user-facing copy.

| Noun | Meaning |
| --- | --- |
| **tenant** | Isolated operator boundary for policy, budgets, and audit scope |
| **workspace** | On-disk project root the agent may read or mutate |
| **session** | One interactive conversation loop (chat/TUI) until exit or suspend |
| **run** | One agent execution with audit trail, receipts, and terminal status |
| **goal** | Operator intent for a run (task description or objective text) |
| **background** | Durable work that continues outside the foreground session |

## Permission Modes

### CLI Flags (Hyphens)
When using CLI flags, permission modes use hyphens:
- `--permission-mode read-only`
- `--permission-mode workspace-write`
- `--permission-mode prompt`
- `--permission-mode allow`
- `--permission-mode danger-full-access`

### Code Variables (Underscores)
When referencing permission modes in code or configuration, use underscores:
- `permission_mode = "read_only"`
- `permission_mode = "workspace_write"`
- `permission_mode = "prompt"`
- `permission_mode = "allow"`
- `permission_mode = "danger_full_access"`

### Tool Names (Underscores)
Tool names use underscores:
- `workspace_read_file`
- `workspace_write_file`
- `workspace_edit_at_hash`

### Documentation Reference
When writing documentation, use the hyphenated form for CLI examples and underscored form for code examples.


## Effect Authority Vocabulary (EFX)

Governance terms introduced by the durable-effect guards. Use these exact
nouns in docs, audit output, and operator guidance; do not invent synonyms.

| Term | Meaning |
| --- | --- |
| **external effect** | A tool annotation (`external_effect=True`) marking actions that change systems outside the workspace. Local-only: remote MCP/vendor hints cannot set it to false. |
| **unmatched start** | An audited `tool_call_started` with no matching completion, failure, or checkpoint settlement — typically after process death mid-dispatch. |
| `OUTCOME_UNKNOWN` | The disclosure status recorded for an unmatched non-idempotent start. Disclosure, not settlement: inspect run, workspace, and external system before any new authorized attempt; blind redispatch is refused. |
| **payload digest** | Canonical hash of tool name plus arguments. One-time approvals bind to it and are consumed at authorization, so a grant cannot authorize changed arguments. |

## Phase Naming

### Standard Format
Always use "Phase X" format (capitalized, no hyphen):
- Phase 4
- Phase 5
- Phase 6

### Examples
- "Phase 4: Federated Swarm Consensus"
- "Phase 5: Hardened Sandbox Virtualization"
- "Phase 6: Skill Writer, Docker Monitor, Control Plane"

### Incorrect Usage
- phase 4 (lowercase)
- phase-4 (hyphenated)
- Phase-4 (hyphenated)

## Component Names

### Class Names (PascalCase)
- `AgentRunner`
- `ToolRegistry`
- `ApprovalManager`
- `WorkflowEngine`

### Module Names (snake_case)
- `agent_runner`
- `tool_registry`
- `approval_manager`
- `workflow_engine`

### File Names (snake_case)
- `agent_runner.py`
- `tool_registry.py`
- `approval/manager.py`

### Documentation Reference
When writing documentation, use PascalCase for class names and snake_case for module/file names.

## ADR References

### Standard Format
Always use "ADR XXXX" format (space between ADR and number, no hyphen):
- ADR 0001
- ADR 0009
- ADR 0019

### Incorrect Usage
- ADR-0001 (hyphenated)
- ADR 0010: (colon)
- ADR0010 (no space)

## Status Indicators

### Implementation Status
- **Accepted and Implemented**: Decision accepted and fully implemented
- **Accepted and Implemented (Beta)**: Decision accepted and implemented in Beta
- **Proposed**: Decision proposed but not yet implemented

### Completion Markers
- ✅ Completed
- 🔲 In Progress
- ❌ Blocked/Failed

## Date Format

### Last Updated Dates
Use ISO 8601 format: `YYYY-MM-DD`
- Example: `Last updated: 2026-06-01`

### Git Timestamps
Use ISO 8601 with timezone: `YYYY-MM-DD HH:MM:SS +0800`
- Example: `2026-05-08 00:31:33 +0800`

## File Path References

### Absolute Paths
When referencing files in documentation, use project-relative paths from the repository root:
- `teaagent/runner/_core.py`
- `docs/architecture.md`
- `tests/test_plan_contract.py`

### Incorrect Usage
- `/Users/teee/dev/teaagent/teaagent/runner/_core.py` (absolute path)
- `runner/_core.py` (relative to current directory)

## Command Examples

### CLI Commands
Use the full command with flags:
```bash
teaagent run --permission-mode read-only
teaagent memory failures review
teaagent tool lint --root .
```

### Python Commands
Use the module syntax:
```bash
python3 -m pytest tests/test_plan_contract.py -v
python3 -m teaagent selftest --root .
```

## Cross-References

### Internal Links
Use relative paths with markdown anchors:
```markdown
[Architecture](architecture.md)
[ADR 0009](adr/0009-5-loop-governance-system.md)
[Choose Your Surface](USAGE.md#choose-your-surface)
```

### External Links
Use full URLs:
```markdown
[Python Documentation](https://docs.python.org/)
[MCP Specification](https://modelcontextprotocol.io/)
```

## Code Blocks

### Language Tags
Always specify the language for syntax highlighting:
```python
def example_function():
    pass
```

```bash
teaagent run --help
```

```markdown
# Heading
```

## Tables

### Format
Use markdown table format with aligned columns:
```markdown
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |
```

## Lists

### Bulleted Lists
Use hyphens for bulleted lists:
```markdown
- Item 1
- Item 2
- Item 3
```

### Numbered Lists
Use numbers for ordered lists:
```markdown
1. Step 1
2. Step 2
3. Step 3
```

## Headings

### Hierarchy
Use H1 for document title, H2 for main sections, H3 for subsections:
```markdown
# Document Title (H1)
## Main Section (H2)
### Subsection (H3)
```

### Incorrect Usage
- Don't skip heading levels (e.g., H1 → H3)
- Don't use H4+ unless necessary for deep nesting
