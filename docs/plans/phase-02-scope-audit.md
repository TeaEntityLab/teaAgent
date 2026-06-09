# Phase 02: Scope Governance — Feature Necessity Audit
Last updated: 2026-06-09

**Priority:** P0
**Concept doc:** [Scope Governance Framework](../architecture-reflection/03-scope-governance-framework.md)
**Estimated effort:** 3-4 sessions
**Dependencies:** Phase 01 (CLAUDE.md for architectural clarity)

## Objective

Audit every P4-P6 Beta feature against PMF necessity criteria. Demote non-essential features to experimental status or document intentional deferral. Establish scope decision protocol to prevent future sprawl.

## Tasks

### Task 2.1: Classify all P4-P6 features

- [ ] For each Beta feature, classify according to framework:
  - Swarm/Consensus engine
  - Tournament execution
  - WASM runtime
  - Docker sandbox
  - Control plane API
  - Skill writer pipeline
  - Context bus (cross-sandbox)
  - Remote JIT approval
  - ACP adapter
- [ ] Apply two-axis classification: PMF Necessity × Dogfooding Value
- [ ] Document classification rationale in scope document

**Verification:** Every Beta feature has a documented classification with rationale.

### Task 2.2: Implement experimental gating

- [ ] For features classified as "experimental candidates" (from 03-scope-governance-framework.md):
  - Swarm/Consensus → gate behind `--experimental` flag
  - Tournament → gate behind `--experimental` flag
  - WASM runtime → gate behind `--experimental` flag
  - Docker sandbox → gate behind `--experimental` flag
  - Control plane → gate behind `--experimental` flag
  - Context bus → gate behind `--experimental` flag
  - Remote JIT approval → gate behind `--experimental` flag
- [ ] Add CLI warning: "This feature is experimental and may change without notice"
- [ ] Move experimental features to opt-in plugin or separate module

**Verification:** `teaagent --help` no longer advertises experimental features as core capabilities.

### Task 2.3: Write non-goals document

- [ ] Create `docs/non-goals.md` with explicit list of what TeaAgent will NOT build pre-PMF:
  - Hosted cloud platform
  - Enterprise SSO/SAML
  - Native mobile/desktop app
  - Plugin marketplace hosting
  - Third-party security certifications
  - Multi-tenant server
- [ ] Link from README and CLAUDE.md

**Verification:** Non-goals document exists and is reviewed monthly.

### Task 2.4: Establish scope decision protocol

- [ ] Create PR template with scope classification section
- [ ] Add checklist: "Does this feature pass the PMF Necessity gate?"
- [ ] Document protocol in CONTRIBUTING.md or `docs/operations/scope-protocol.md`

**Verification:** Next feature PR includes scope classification.

## Success Criteria

- [ ] At least 3 Beta features demoted to experimental
- [ ] Experimental features hidden from default CLI/TUI surface
- [ ] Non-goals documented and linked from CLAUDE.md
- [ ] Scope decision protocol used on next feature proposal

## Rollback

If gating causes user confusion:
- Restore feature visibility
- Add `--include-experimental` flag instead of hiding completely
