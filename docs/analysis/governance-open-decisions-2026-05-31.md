# Governance Hardening Open Decisions - 2026-05-31

**Purpose:** Address open decisions from governance-hardening.md

---

## Open Decisions from governance-hardening.md

### 1. Swarm LLM Execution

**Decision:** Keep as optional

**Rationale:**
- Real adapter path exists via `SwarmManager.with_agent_execution`
- Deeper tournament benchmarks remain optional
- Core functionality is shipped; benchmarks are nice-to-have
- No action required - this is a feature flag/optional enhancement

**Status:** ✅ Resolved - no action needed

---

### 2. Phase 4–6 Status

**Decision:** Keep as Beta with current status

**Rationale:**
- Consensus, sandbox execution, and control-plane CLI are **Beta** with acceptance/unit tests
- See `docs/backlog-priority.md` for details
- Beta status is appropriate - core shipped, E2E hardening ongoing
- No action required - status is correctly documented

**Status:** ✅ Resolved - no action needed

---

### 3. Dependabot #10 (CVE-2026-23949 - jaraco.context)

**Decision:** Dismiss in GitHub UI (requires maintainer action)

**Rationale:**
- Vulnerability is patched in default branch (jaraco-context 6.1.2)
- `uv.lock` pins jaraco-context 6.1.2 (>=6.1.0 constraint in pyproject.toml)
- Selftest confirms: `jaraco_context.ok: true` when installed
- Documented in `docs/dependabot-alert-10.md` with dismissal instructions

**Action Required:**
- Maintainer must dismiss the alert in GitHub Security → Dependabot → alert #10
- Use the documented dismissal command or manual dismissal

**Status:** ⏸️ Blocked - requires maintainer GitHub access

---

## Summary

| Decision | Status | Action Required |
|----------|--------|------------------|
| Swarm LLM execution | ✅ Resolved | None |
| Phase 4–6 status | ✅ Resolved | None |
| Dependabot #10 | ⏸️ Blocked | Maintainer to dismiss in GitHub UI |

---

**Reviewed:** 2026-05-31
**Decisions resolved:** 2
**Decisions blocked:** 1 (requires maintainer action)
