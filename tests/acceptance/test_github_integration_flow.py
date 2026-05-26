"""Acceptance test for GitHub integration tools.

Verifies: tool registration, schema validation, error handling.
"""

from __future__ import annotations

from teaagent.github_integration import (
    github_create_pr,
    github_list_prs,
    register_github_tools,
)
from teaagent.tools import ToolRegistry


def test_github_tools_registered() -> None:
    registry = ToolRegistry()
    register_github_tools(registry)
    tools = registry.list_tools()
    assert 'github_create_pr' in tools
    assert 'github_list_prs' in tools
    assert 'github_review_pr' in tools
    assert 'github_ci_status' in tools


def test_github_create_pr_no_token() -> None:
    """Should raise PermissionError when GITHUB_TOKEN is not set."""
    import os

    if 'GITHUB_TOKEN' not in os.environ and 'GH_TOKEN' not in os.environ:
        try:
            github_create_pr('owner/repo', 'title', 'branch')
            assert False, 'should have raised'
        except PermissionError:
            pass


def test_github_list_prs_registration_schema() -> None:
    registry = ToolRegistry()
    register_github_tools(registry)
    tool = registry.get('github_list_prs')
    assert tool.annotations.read_only


def test_github_ci_status_annotations() -> None:
    registry = ToolRegistry()
    register_github_tools(registry)
    tool = registry.get('github_ci_status')
    assert tool.annotations.read_only


def test_github_tool_execution_errors() -> None:
    """Tools should raise PermissionError (not crash) when GITHUB_TOKEN is not set."""
    import os

    if 'GITHUB_TOKEN' not in os.environ and 'GH_TOKEN' not in os.environ:
        import pytest

        with pytest.raises(PermissionError, match='GitHub token not found'):
            github_list_prs('owner/nonexistent-repo-12345')
