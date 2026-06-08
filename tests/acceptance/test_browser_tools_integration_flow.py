"""Acceptance test for browser automation tools integration.

Verifies: tools registered in workspace tool registry, error handling without Playwright.
"""

from __future__ import annotations

from teaagent.browser_tools import (
    HAS_PLAYWRIGHT,
    browser_navigate,
    register_browser_tools,
)
from teaagent.types import ToolRegistry


def test_browser_tools_registered() -> None:
    registry = ToolRegistry()
    register_browser_tools(registry)
    tools = registry.list_tools()
    expected = [
        'browser_navigate',
        'browser_snapshot',
        'browser_screenshot',
        'browser_get_content',
        'browser_click',
        'browser_fill',
        'browser_evaluate',
    ]
    for name in expected:
        assert name in tools, f'missing tool: {name}'


def test_browser_tools_are_read_only() -> None:
    registry = ToolRegistry()
    register_browser_tools(registry)
    tools = registry.list_tools()
    for name in tools:
        tool = registry.get(name)
        assert tool.annotations.read_only, f'{name} should be read-only'


def test_browser_navigate_no_playwright() -> None:
    if not HAS_PLAYWRIGHT:
        result = browser_navigate('https://example.com')
        assert result.get('status') == 'error', 'should error without playwright'


def test_browser_integration_in_workspace_tools() -> None:
    """Browser tools should be included when building workspace tool registry."""
    import tempfile

    from teaagent.workspace_tools._files import build_workspace_tool_registry

    with tempfile.TemporaryDirectory() as tmp:
        registry = build_workspace_tool_registry(tmp)
        tools = registry.list_tools()
        browser_related = [t for t in tools if t.startswith('browser_')]
        if HAS_PLAYWRIGHT:
            assert len(browser_related) >= 3, (
                f'expected browser tools, got: {browser_related}'
            )
        else:
            pass


def test_browser_tool_registration_schema_validity() -> None:
    """Verify all registered browser tools have valid schemas."""
    registry = ToolRegistry()
    register_browser_tools(registry)
    for name in registry.list_tools():
        tool = registry.get(name)
        assert isinstance(tool.input_schema, dict)
        assert isinstance(tool.output_schema, dict)
        assert 'type' in tool.output_schema
