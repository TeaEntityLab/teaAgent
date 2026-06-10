# ADR 0030: Root Module Freeze and Canonical Package Homes

**Status:** Accepted  
**Date:** 2026-06-10  
**Work item:** WDF-001

## Context

The `teaagent/` package has 184 root-level modules. H4/H5 governance code
sprawled across root modules (`policy_engine.py`, `rbac.py`, etc.) before
consolidation into `teaagent/governance/`, `teaagent/consensus/`, and
`teaagent/coordination/`.

## Decision

1. **Canonical homes**
   - Policy, release gates, eval gates, conversation UX → `teaagent/governance/`
   - Consensus validation → `teaagent/consensus/` (when wired)
   - Approval coordination, signed queue writes → `teaagent/coordination/`

2. **Root module freeze**
   - Baseline: **184** root modules (`teaagent/*.py`, excluding `__init__.py`).
   - `scripts/check_root_module_count.py` fails CI when count exceeds baseline.
   - New root modules require an ADR exception with explicit justification.

3. **WDF-002 complete (2026-06-10)**
   - Folded seven H4/H5 root modules into `teaagent/governance/` and
     `teaagent/consensus/`; deprecated import aliases via `_compat_modules.py`.
   - Root count at HEAD: **177** (down from 184 baseline).

## Consequences

- Safer incremental consolidation without silent package growth.
- New features must land in canonical subpackages first.
