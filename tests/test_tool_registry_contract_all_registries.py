# test-type: contract
"""G-P1-7: every built-in tool registry satisfies the AGENTS.md tool contract.

AGENTS.md requires that tools are registered through ``ToolRegistry`` and that
each tool carries a name, description, input schema, output schema, and
annotations. ``tests/test_governance_compliance.py`` only covers the workspace
registry; this module covers the remaining built-in ``register_*_tools``
surfaces and reuses ``lint_registry`` as the static oracle.

Excluded by design: ADR-0043 quarantined surfaces and MCP remote tools (covered
by G-P1-6).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from teaagent.governance.tool_lint import lint_registry
from teaagent.types import ToolAnnotations, ToolRegistry


def _workspace_registry(tmp_path: Path) -> ToolRegistry:
    from teaagent.workspace_tools import build_workspace_tool_registry

    return build_workspace_tool_registry(root=tmp_path)


def _git_registry(tmp_path: Path) -> ToolRegistry:
    from teaagent.workspace_tools._git import GitToolConfig, register_git_tools

    registry = ToolRegistry()
    register_git_tools(registry, GitToolConfig(root=tmp_path))
    return registry


def _github_registry(tmp_path: Path) -> ToolRegistry:
    from teaagent.github_integration import register_github_tools

    registry = ToolRegistry()
    register_github_tools(registry)
    return registry


def _browser_registry(tmp_path: Path) -> ToolRegistry:
    from teaagent.browser_tools import register_browser_tools

    registry = ToolRegistry()
    register_browser_tools(registry)
    return registry


def _code_analysis_registry(tmp_path: Path) -> ToolRegistry:
    from teaagent.code_analysis import CodeAnalysisConfig, register_code_analysis_tools

    registry = ToolRegistry()
    register_code_analysis_tools(
        registry, CodeAnalysisConfig.from_root(tmp_path, enabled=True)
    )
    return registry


def _subagent_registry(tmp_path: Path) -> ToolRegistry:
    from teaagent.chat_agent import ChatAgentConfig
    from teaagent.subagents import SubagentManager
    from teaagent.subagents._tools import register_subagent_tools

    (tmp_path / '.teaagent').mkdir(exist_ok=True)
    config = ChatAgentConfig(root=tmp_path)
    adapter = MagicMock()
    adapter.provider = 'fake'
    manager = SubagentManager(
        root=tmp_path, parent_config=config, parent_adapter=adapter
    )
    registry = ToolRegistry()
    register_subagent_tools(
        registry,
        adapter=adapter,
        config=config,
        depth=0,
        manager=manager,
    )
    return registry


BUILDERS: dict[str, Callable[[Path], ToolRegistry]] = {
    'workspace': _workspace_registry,
    'git': _git_registry,
    'github': _github_registry,
    'browser': _browser_registry,
    'code_analysis': _code_analysis_registry,
    'subagent': _subagent_registry,
}


@pytest.fixture(params=sorted(BUILDERS), ids=sorted(BUILDERS))
def built(request: pytest.FixtureRequest, tmp_path: Path) -> tuple[str, ToolRegistry]:
    """Build one built-in registry and return (label, registry)."""
    label = request.param
    return label, BUILDERS[label](tmp_path)


def test_registry_is_non_empty(built: tuple[str, ToolRegistry]) -> None:
    label, registry = built
    assert registry.list_tools(), f"registry '{label}' registered no tools"


def test_lint_registry_reports_no_errors(built: tuple[str, ToolRegistry]) -> None:
    label, registry = built
    errors = [issue for issue in lint_registry(registry) if issue.level == 'error']
    assert not errors, f"registry '{label}' has lint errors: {errors}"


def test_every_tool_meets_contract(built: tuple[str, ToolRegistry]) -> None:
    label, registry = built
    for name in registry.list_tools():
        tool = registry.get(name)
        where = f"[{label}] tool '{name}'"
        assert tool.name and tool.name == name, f'{where} has empty or mismatched name'
        assert isinstance(tool.description, str) and tool.description.strip(), (
            f'{where} has empty description'
        )
        assert isinstance(tool.input_schema, dict) and 'type' in tool.input_schema, (
            f"{where} input_schema must be a dict with 'type'"
        )
        assert isinstance(tool.output_schema, dict) and tool.output_schema, (
            f'{where} output_schema must be a non-empty dict'
        )
        assert isinstance(tool.annotations, ToolAnnotations), (
            f'{where} annotations missing'
        )
