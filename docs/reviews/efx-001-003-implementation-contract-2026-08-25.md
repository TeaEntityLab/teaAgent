# EFX-001–003 Implementation Contract — 2026-08-25

Coordinator-owned. Isolated workers must follow this file split and must
not edit files assigned to another worker.

## Authority

Harness-First, DR-006, ADR-0032, ADR-0042. No second framework. No generic
outbox/ledger/fencing/actor/lease. No live GitHub/browser/provider network.

## File split

- **EFX-002:** `teaagent/tools.py`, `teaagent/github_integration.py`,
  `teaagent/browser_tools.py`, `teaagent/mcp_tool_adapter.py`,
  `teaagent/approval/backend.py`, `tests/test_efx002_effect_classification.py`,
  and existing tests that assert MCP/GitHub/browser annotations.
- **EFX-003:** `teaagent/prompt.py`, `teaagent/approval/manager.py`,
  `tests/test_efx003_one_time_approval.py`, and
  `tests/acceptance/test_security_approval_manager_flow.py` only for the
  one-time grant assertions.
- **EFX-001:** `teaagent/checkpoint.py`, `teaagent/runner/_core.py`,
  `teaagent/integration/resume_preparation.py`,
  `tests/test_efx001_interrupted_dispatch.py`.
  In `_core.py` only: annotations dict pass-through, pending-effect sandwich,
  unconfirmed redispatches. Do not retouch approval backends or JIT state.

## Non-goals (all workers)

Do not edit roadmap/docs-consistency/INDEX except as noted by coordinator.
Skip project-wide tests, formatters, and linters. No new dependencies.
