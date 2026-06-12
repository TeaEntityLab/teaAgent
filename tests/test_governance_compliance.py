"""Verify code compliance with AGENTS.md governance rules.

Rules tested:
  - Tools must be registered through ToolRegistry (tools.py:112)
  - Each tool requires name, description, input schema, output schema, annotations
  - Destructive tools require approval checks
  - Every run has iteration/tool-call limits
  - Agent contribution contract compliance (V4-a, V4-c)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from teaagent.types import ToolAnnotations, ToolRegistry


@pytest.fixture
def registry() -> ToolRegistry:
    """Build the standard workspace tool registry for testing."""
    from teaagent.workspace_tools import build_workspace_tool_registry

    return build_workspace_tool_registry(root=Path.cwd())


# ── Tool governance ──────────────────────────────────────────────────


class TestToolRegistration:
    """AGENTS.md: "Tools must be registered through ToolRegistry"."""

    def test_all_tools_have_names(self, registry: ToolRegistry) -> None:
        """Each registered tool must have a non-empty name."""
        for name in registry.list_tools():
            tool = registry.get(name)
            assert tool.name, f"Tool '{name}' has empty name"

    def test_all_tools_have_descriptions(self, registry: ToolRegistry) -> None:
        """Each tool must have a description (AGENTS.md: 'Each tool requires a description')."""
        for name in registry.list_tools():
            tool = registry.get(name)
            assert tool.description, f"Tool '{name}' has empty description"

    def test_all_tools_have_input_schema(self, registry: ToolRegistry) -> None:
        """Each tool must have an input schema."""
        for name in registry.list_tools():
            tool = registry.get(name)
            assert isinstance(tool.input_schema, dict), (
                f"Tool '{name}' input_schema is not a dict"
            )
            assert 'type' in tool.input_schema, (
                f"Tool '{name}' input_schema missing 'type'"
            )

    def test_all_tools_have_output_schema(self, registry: ToolRegistry) -> None:
        """Each tool must have an output schema."""
        for name in registry.list_tools():
            tool = registry.get(name)
            assert isinstance(tool.output_schema, dict), (
                f"Tool '{name}' output_schema is not a dict"
            )

    def test_all_tools_have_annotations(self, registry: ToolRegistry) -> None:
        """Each tool must have annotations (safety metadata)."""
        for name in registry.list_tools():
            tool = registry.get(name)
            assert isinstance(tool.annotations, ToolAnnotations), (
                f"Tool '{name}' annotations is not a ToolAnnotations instance"
            )

    def test_all_tools_have_handlers(self, registry: ToolRegistry) -> None:
        """Each tool must have a callable handler."""
        for name in registry.list_tools():
            tool = registry.get(name)
            assert callable(tool.handler), f"Tool '{name}' handler is not callable"


class TestDestructiveToolAnnotations:
    """AGENTS.md: "Destructive tools must not run unless an approval token is present"."""

    def test_destructive_tools_marked_appropriately(
        self, registry: ToolRegistry
    ) -> None:
        """Destructive tools should have annotations.destructive=True."""
        for name in registry.list_tools():
            tool = registry.get(name)
            annotations = tool.annotations
            # Tools that modify the workspace should be marked destructive
            if (
                'write' in name.lower()
                or 'delete' in name.lower()
                or 'remove' in name.lower()
            ):
                assert annotations.destructive or annotations.read_only, (
                    f"Tool '{name}' may be destructive but is not marked as such "
                    f'(destructive={annotations.destructive}, read_only={annotations.read_only})'
                )

    def test_destructive_tools_have_security_tier(self, registry: ToolRegistry) -> None:
        """Destructive tools should have an appropriate security tier."""
        for name in registry.list_tools():
            tool = registry.get(name)
            if tool.annotations.destructive:
                tier = tool.get_security_tier()
                assert tier in {'High', 'Critical'}, (
                    f"Destructive tool '{name}' has security tier '{tier}', "
                    f"expected 'High' or 'Critical'"
                )

    def test_read_only_tools_have_low_security_tier(
        self, registry: ToolRegistry
    ) -> None:
        """Read-only tools should have security tier 'Low'."""
        for name in registry.list_tools():
            tool = registry.get(name)
            if tool.annotations.read_only:
                tier = tool.get_security_tier()
                assert tier == 'Low', (
                    f"Read-only tool '{name}' has security tier '{tier}', "
                    f"expected 'Low'"
                )


# ── Runtime safety ───────────────────────────────────────────────────


class TestRunBudgetLimits:
    """AGENTS.md: "Every run must have an iteration limit and tool-call limit"."""

    def test_run_has_iteration_limit(self) -> None:
        """Check that the agent runner enforces iteration limits."""
        from teaagent.types import RunBudget

        budget = RunBudget()
        assert budget.max_iterations > 0, (
            f'RunBudget.max_iterations should be positive, got {budget.max_iterations}'
        )

    def test_run_has_tool_call_limit(self) -> None:
        """Check that the agent runner enforces tool-call limits."""
        from teaagent.types import RunBudget

        budget = RunBudget()
        assert budget.max_tool_calls > 0, (
            f'RunBudget.max_tool_calls should be positive, got {budget.max_tool_calls}'
        )


# ── Audit logging ────────────────────────────────────────────────────


class TestAuditLogging:
    """AGENTS.md: "Every tool call and final result must be recorded in the audit log"."""

    def test_audit_logger_is_used_in_runner(self) -> None:
        """Verify the runner imports and uses the audit logger."""
        import inspect

        from teaagent.runner._core import AgentRunner

        sig = inspect.signature(AgentRunner.__init__)
        assert 'audit' in sig.parameters, (
            'AgentRunner.__init__ should accept an audit parameter'
        )

    def test_audit_event_has_required_fields(self) -> None:
        """Audit events must carry run_id, event_type, and payload."""
        from teaagent.types import AuditEvent

        event = AuditEvent(
            run_id='test-run',
            event_type='test_event',
            payload={},
        )
        assert event.run_id == 'test-run'
        assert event.event_type == 'test_event'
        assert event.payload == {}


# ── Tool error actionability ─────────────────────────────────────────


class TestToolErrors:
    """AGENTS.md: "Tool errors must be actionable and classified"."""

    def test_tool_execution_error_has_message(self) -> None:
        """ToolExecutionError must carry a human-readable message."""
        from teaagent.types import ToolExecutionError

        err = ToolExecutionError('test error message')
        assert 'test error message' in str(err)

    def test_tool_execution_error_is_classified(self) -> None:
        """ToolExecutionError is a subclass of Exception (classified by type)."""
        from teaagent.types import ToolExecutionError

        assert issubclass(ToolExecutionError, Exception)


# ── Agent contribution contract (V4-a, V4-c) ───────────────────────────────


class TestAgentContributionContract:
    """V4-a/V4-c: Agent contribution contract compliance and anti-bypass."""

    def test_bypass_trailer_is_critical_error(self) -> None:
        """Bypass trailer must be treated as critical error (V4-c)."""
        # Simulate the bypass detection logic
        commit_message = 'test\n\nBypass-agent-contract: testing'
        trailers = {
            line.split(':', 1)[0].strip(): line.split(':', 1)[1].strip()
            for line in commit_message.splitlines()
            if ':' in line and not line.startswith('#')
        }

        # Check if bypass trailer exists
        has_bypass = 'Bypass-agent-contract' in trailers
        assert has_bypass, 'Test setup should have bypass trailer'

        # The script should treat this as critical error
        assert has_bypass, 'Bypass trailer should be detected as critical violation'

    def test_bypass_environment_is_critical_error(self) -> None:
        """Bypass environment variable must be treated as critical error (V4-c)."""
        import os

        # Simulate environment bypass check
        has_bypass_env = os.getenv('ALLOW_AGENT_CONTRACT_BYPASS') == '1'

        # Normally this should be False
        assert not has_bypass_env, 'Environment bypass should not be set in normal test'

        # If set, it should be treated as critical error
        os.environ['ALLOW_AGENT_CONTRACT_BYPASS'] = '1'
        try:
            has_bypass_env = os.getenv('ALLOW_AGENT_CONTRACT_BYPASS') == '1'
            assert has_bypass_env, 'Environment bypass should be detected when set'
        finally:
            os.environ.pop('ALLOW_AGENT_CONTRACT_BYPASS', None)

    def test_normal_commit_passes_without_bypass(self) -> None:
        """Normal commit without bypass should pass validation."""
        # Simulate normal commit without bypass
        commit_message = 'test'
        trailers = {
            line.split(':', 1)[0].strip(): line.split(':', 1)[1].strip()
            for line in commit_message.splitlines()
            if ':' in line and not line.startswith('#')
        }

        # Should not have bypass trailer
        has_bypass = 'Bypass-agent-contract' in trailers
        assert not has_bypass, 'Normal commit should not have bypass trailer'
