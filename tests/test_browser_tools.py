"""Tests for browser automation tools."""

from __future__ import annotations

import pytest

from teaagent.browser_tools import (
    _DISABLED_MESSAGE,
    HAS_PLAYWRIGHT,
    _cleanup_browser,
    register_browser_tools,
)
from teaagent.types import ToolRegistry


def _playwright_runtime_available() -> bool:
    if not HAS_PLAYWRIGHT:
        return False
    try:
        import asyncio

        asyncio.get_running_loop()
        return False
    except RuntimeError:
        # No running event loop; continue with sync playwright check
        pass
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:
        return False


@pytest.fixture(autouse=True)
def cleanup_browser():
    """Cleanup browser after each test."""
    yield
    _cleanup_browser()


def test_has_playwright_is_bool() -> None:
    assert isinstance(HAS_PLAYWRIGHT, bool)


def test_all_tools_registered_when_disabled(empty_tool_registry: ToolRegistry) -> None:
    """When Playwright is not available, stub tools return the install message."""
    register_browser_tools(empty_tool_registry)
    expected_tools = [
        'browser_navigate',
        'browser_snapshot',
        'browser_screenshot',
        'browser_get_content',
        'browser_click',
        'browser_fill',
        'browser_evaluate',
    ]
    for name in expected_tools:
        assert empty_tool_registry.get(name) is not None


def test_disabled_tool_returns_install_error(empty_tool_registry: ToolRegistry) -> None:
    """Stub tool handlers return an error message when Playwright is unavailable."""
    if HAS_PLAYWRIGHT:
        pytest.skip('playwright package installed; use functional tests instead')
    register_browser_tools(empty_tool_registry)
    tool = empty_tool_registry.get('browser_navigate')
    assert tool is not None
    result = tool.handler({'url': 'https://example.com'})
    assert result['status'] == 'error'
    assert 'playwright' in result['message'].lower()


def test_disabled_message_constant() -> None:
    """The disabled message mentions the install command."""
    assert 'pip install' in _DISABLED_MESSAGE


@pytest.mark.skipif(
    not _playwright_runtime_available(),
    reason='playwright runtime unavailable (missing browser binaries or running asyncio loop)',
)
def test_navigate_to_url() -> None:
    from teaagent.browser_tools import browser_navigate

    result = browser_navigate(
        'data:text/html,<html><title>Hello</title><h1>Hello</h1></html>'
    )
    assert result['status'] == 'ok'
    assert 'Hello' in result['title']


@pytest.mark.skipif(
    not _playwright_runtime_available(),
    reason='playwright runtime unavailable (missing browser binaries or running asyncio loop)',
)
def test_snapshot_returns_text() -> None:
    from teaagent.browser_tools import browser_navigate, browser_snapshot

    browser_navigate('data:text/html,<h1>Hello World</h1>')
    result = browser_snapshot()
    assert result['status'] == 'ok'
    assert 'Hello World' in result['text']


@pytest.mark.skipif(
    not _playwright_runtime_available(),
    reason='playwright runtime unavailable (missing browser binaries or running asyncio loop)',
)
def test_screenshot_returns_base64() -> None:
    from teaagent.browser_tools import browser_navigate, browser_screenshot

    browser_navigate('data:text/html,<h1>Hello</h1>')
    result = browser_screenshot()
    assert result['status'] == 'ok'
    assert 'data' in result
    assert result['mime_type'] == 'image/png'


@pytest.mark.skipif(
    not _playwright_runtime_available(),
    reason='playwright runtime unavailable (missing browser binaries or running asyncio loop)',
)
def test_get_content_text() -> None:
    from teaagent.browser_tools import browser_get_content, browser_navigate

    browser_navigate('data:text/html,<p>Visible text</p>')
    result = browser_get_content()
    assert result['status'] == 'ok'
    assert 'Visible text' in result['content']


@pytest.mark.skipif(
    not _playwright_runtime_available(),
    reason='playwright runtime unavailable (missing browser binaries or running asyncio loop)',
)
def test_get_content_html() -> None:
    from teaagent.browser_tools import browser_get_content, browser_navigate

    browser_navigate('data:text/html,<p>Para</p>')
    result = browser_get_content(include_html=True)
    assert result['status'] == 'ok'
    assert '<p>' in result['content']


@pytest.mark.skipif(
    not _playwright_runtime_available(),
    reason='playwright runtime unavailable (missing browser binaries or running asyncio loop)',
)
def test_click_element() -> None:
    from teaagent.browser_tools import (
        browser_click,
        browser_get_content,
        browser_navigate,
    )

    html = (
        '<html><body>'
        '<div id="before">before</div>'
        "<button onclick=\"document.getElementById('before').innerText='clicked'\">Go</button>"
        '</body></html>'
    )
    browser_navigate(f'data:text/html,{html}')
    result = browser_click('button')
    assert result['status'] == 'ok'
    content = browser_get_content()
    assert 'clicked' in content['content']


@pytest.mark.skipif(
    not _playwright_runtime_available(),
    reason='playwright runtime unavailable (missing browser binaries or running asyncio loop)',
)
def test_fill_form_field() -> None:
    from teaagent.browser_tools import (
        browser_evaluate,
        browser_fill,
        browser_navigate,
    )

    html = '<html><body><input id="name" value="old"/></body></html>'
    browser_navigate(f'data:text/html,{html}')
    result = browser_fill('#name', 'new value')
    assert result['status'] == 'ok'
    eval_result = browser_evaluate('document.getElementById("name").value')
    assert 'new value' in eval_result['result']


@pytest.mark.skipif(
    not _playwright_runtime_available(),
    reason='playwright runtime unavailable (missing browser binaries or running asyncio loop)',
)
def test_evaluate_javascript() -> None:
    from teaagent.browser_tools import browser_evaluate, browser_navigate

    browser_navigate('data:text/html,<h1>Test</h1>')
    result = browser_evaluate('document.title')
    assert result['status'] == 'ok'
    assert 'result' in result


@pytest.mark.skipif(
    not _playwright_runtime_available(),
    reason='playwright runtime unavailable (missing browser binaries or running asyncio loop)',
)
def test_navigate_error_returns_status() -> None:
    from teaagent.browser_tools import browser_navigate

    result = browser_navigate('http://nonexistent.invalid', timeout_ms=1000)
    assert result['status'] == 'error'


@pytest.mark.skip('Performance test — run manually')
def test_registration_all_tools() -> None:
    """When Playwright is available, register real handlers, not stubs."""
    registry = ToolRegistry()
    register_browser_tools(registry)
    tool = registry.get('browser_navigate')
    assert tool is not None
    result = tool.handler({'url': 'data:text/html,<h1>OK</h1>'})
    assert result['status'] == 'ok'
