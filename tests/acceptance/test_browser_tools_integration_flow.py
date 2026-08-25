"""Test module for browser automation tools integration.

This module tests the browser automation tools, which enable agents to interact
with web pages for testing, scraping, and verification. The tools integrate with
the workspace tool registry and handle graceful degradation when Playwright is not available.

Key concepts tested:
- Tool Registration: Browser tools are registered in the tool registry
- Effect classification: snapshot/screenshot/get_content stay read-only;
  navigate/click/fill/evaluate are local external mutations (EFX-002)
- Tool Availability: Tools are available when Playwright is installed
- Error Handling: Tools return errors gracefully when Playwright is unavailable
- Workspace Integration: Browser tools are included in workspace tool registry
- Schema Validity: All browser tools have valid input and output schemas

Acceptance Criteria:
- AC1: Browser tools (navigate, snapshot, screenshot, etc.) are registered
- AC2: Read-only browser tools stay read-only; mutating tools are external_effect
- AC3: Browser tools return error status when Playwright is not installed
- AC4: Browser tools are included in workspace tool registry when available
- AC5: All registered browser tools have valid input and output schemas
- AC6: Tool schemas include required 'type' field in output_schema

Technical Details:
- register_browser_tools adds browser tools to ToolRegistry
- HAS_PLAYWRIGHT flag indicates Playwright availability
- Browser tools include: browser_navigate, browser_snapshot, browser_screenshot,
  browser_get_content, browser_click, browser_fill, browser_evaluate
- Tools return error status when Playwright is not available
- build_workspace_tool_registry includes browser tools when Playwright is present
- All tools must have valid JSON schemas for input and output

References:
- Browser tools design: /docs/architecture/browser_tools.md
- Playwright integration: /docs/integration/playwright.md
- Tool registry spec: /docs/specs/tool_registry.md
"""

from __future__ import annotations

from teaagent.browser_tools import (
    HAS_PLAYWRIGHT,
    browser_navigate,
    register_browser_tools,
)
from teaagent.types import ToolRegistry

_READ_ONLY_BROWSER_TOOLS = (
    'browser_snapshot',
    'browser_screenshot',
    'browser_get_content',
)
_MUTATING_BROWSER_TOOLS = (
    'browser_navigate',
    'browser_click',
    'browser_fill',
    'browser_evaluate',
)


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
        # Verify all expected browser tools are registered
        assert name in tools, f'Expected browser tool {name!r} to be registered'


def test_browser_tools_are_read_only() -> None:
    registry = ToolRegistry()
    register_browser_tools(registry)
    for name in _READ_ONLY_BROWSER_TOOLS:
        ann = registry.get(name).annotations
        assert ann.read_only, f'Expected browser tool {name!r} to be marked read-only'
        assert ann.external_effect is False, (
            f'Expected browser tool {name!r} not to be an external effect'
        )
        assert ann.destructive is False, (
            f'Expected browser tool {name!r} not to be destructive'
        )


def test_browser_mutating_tools_are_external_effects() -> None:
    registry = ToolRegistry()
    register_browser_tools(registry)
    for name in _MUTATING_BROWSER_TOOLS:
        ann = registry.get(name).annotations
        assert ann.read_only is False, f'Expected {name!r} not to be read-only'
        assert ann.destructive is True, f'Expected {name!r} to be destructive'
        assert ann.external_effect is True, (
            f'Expected {name!r} to be an external effect'
        )
        assert ann.idempotent is False, f'Expected {name!r} not to be idempotent'


def test_browser_navigate_no_playwright() -> None:
    if not HAS_PLAYWRIGHT:
        result = browser_navigate('https://example.com')
        # Verify browser tools return error status when Playwright is not installed
        assert result.get('status') == 'error', (
            'Expected browser_navigate to return error status without Playwright'
        )


def test_browser_integration_in_workspace_tools() -> None:
    """Browser tools should be included when building workspace tool registry."""
    import tempfile

    from teaagent.workspace_tools._files import build_workspace_tool_registry

    with tempfile.TemporaryDirectory() as tmp:
        registry = build_workspace_tool_registry(tmp)
        tools = registry.list_tools()
        browser_related = [t for t in tools if t.startswith('browser_')]
        if HAS_PLAYWRIGHT:
            # Verify browser tools are included in workspace registry when Playwright is available
            assert len(browser_related) >= 3, (
                f'Expected at least 3 browser tools in workspace registry, got: {browser_related}'
            )
        else:
            # When Playwright is not available, browser tools should not be present
            pass


def test_browser_tool_registration_schema_validity() -> None:
    """Verify all registered browser tools have valid schemas."""
    registry = ToolRegistry()
    register_browser_tools(registry)
    for name in registry.list_tools():
        tool = registry.get(name)
        # Verify input schema is a valid dict
        assert isinstance(tool.input_schema, dict), (
            f'Expected input_schema to be dict for tool {name!r}'
        )
        # Verify output schema is a valid dict
        assert isinstance(tool.output_schema, dict), (
            f'Expected output_schema to be dict for tool {name!r}'
        )
        # Verify output schema includes required 'type' field
        assert 'type' in tool.output_schema, (
            f'Expected output_schema to include "type" field for tool {name!r}'
        )
