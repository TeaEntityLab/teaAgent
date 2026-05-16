"""Tests for browser automation tools."""

from __future__ import annotations

import unittest

from teaagent.browser_tools import (
    _DISABLED_MESSAGE,
    HAS_PLAYWRIGHT,
    _cleanup_browser,
    register_browser_tools,
)
from teaagent.tools import ToolRegistry


class BrowserToolsRegistrationTest(unittest.TestCase):
    """Tests for tool registration (works regardless of Playwright availability)."""

    def tearDown(self) -> None:
        _cleanup_browser()

    def test_has_playwright_is_bool(self) -> None:
        self.assertIsInstance(HAS_PLAYWRIGHT, bool)

    def test_all_tools_registered_when_disabled(self) -> None:
        """When Playwright is not available, stub tools return the install message."""
        registry = ToolRegistry()
        register_browser_tools(registry)
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
            with self.subTest(tool=name):
                self.assertIsNotNone(registry.get(name))

    def test_disabled_tool_returns_install_error(self) -> None:
        """Stub tool handlers return an error message when Playwright is unavailable."""
        registry = ToolRegistry()
        register_browser_tools(registry)
        tool = registry.get('browser_navigate')
        assert tool is not None
        result = tool.handler({'url': 'https://example.com'})
        self.assertEqual(result['status'], 'error')
        self.assertIn('playwright', result['message'].lower())

    def test_disabled_message_constant(self) -> None:
        """The disabled message mentions the install command."""
        self.assertIn('pip install', _DISABLED_MESSAGE)


@unittest.skipUnless(HAS_PLAYWRIGHT, 'playwright packages not installed')
class BrowserToolsFunctionalTest(unittest.TestCase):
    """Functional tests that require Playwright and a browser binary."""

    def tearDown(self) -> None:
        _cleanup_browser()

    def test_navigate_to_url(self) -> None:
        from teaagent.browser_tools import browser_navigate

        result = browser_navigate('data:text/html,<h1>Hello</h1>')
        self.assertEqual(result['status'], 'ok')
        self.assertIn('Hello', result['title'])

    def test_snapshot_returns_text(self) -> None:
        from teaagent.browser_tools import browser_navigate, browser_snapshot

        browser_navigate('data:text/html,<h1>Hello World</h1>')
        result = browser_snapshot()
        self.assertEqual(result['status'], 'ok')
        self.assertIn('Hello World', result['text'])

    def test_screenshot_returns_base64(self) -> None:
        from teaagent.browser_tools import browser_navigate, browser_screenshot

        browser_navigate('data:text/html,<h1>Hello</h1>')
        result = browser_screenshot()
        self.assertEqual(result['status'], 'ok')
        self.assertIn('data', result)
        self.assertEqual(result['mime_type'], 'image/png')

    def test_get_content_text(self) -> None:
        from teaagent.browser_tools import browser_get_content, browser_navigate

        browser_navigate('data:text/html,<p>Visible text</p>')
        result = browser_get_content()
        self.assertEqual(result['status'], 'ok')
        self.assertIn('Visible text', result['content'])

    def test_get_content_html(self) -> None:
        from teaagent.browser_tools import browser_get_content, browser_navigate

        browser_navigate('data:text/html,<p>Para</p>')
        result = browser_get_content(include_html=True)
        self.assertEqual(result['status'], 'ok')
        self.assertIn('<p>', result['content'])

    def test_click_element(self) -> None:
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
        self.assertEqual(result['status'], 'ok')
        content = browser_get_content()
        self.assertIn('clicked', content['content'])

    def test_fill_form_field(self) -> None:
        from teaagent.browser_tools import (
            browser_evaluate,
            browser_fill,
            browser_navigate,
        )

        html = '<html><body><input id="name" value="old"/></body></html>'
        browser_navigate(f'data:text/html,{html}')
        result = browser_fill('#name', 'new value')
        self.assertEqual(result['status'], 'ok')
        eval_result = browser_evaluate('document.getElementById("name").value')
        self.assertIn('new value', eval_result['result'])

    def test_evaluate_javascript(self) -> None:
        from teaagent.browser_tools import browser_evaluate, browser_navigate

        browser_navigate('data:text/html,<h1>Test</h1>')
        result = browser_evaluate('document.title')
        self.assertEqual(result['status'], 'ok')
        self.assertIn('result', result)

    def test_navigate_error_returns_status(self) -> None:
        from teaagent.browser_tools import browser_navigate

        result = browser_navigate('http://nonexistent.invalid', timeout_ms=1000)
        self.assertEqual(result['status'], 'error')

    @unittest.skip('Performance test — run manually')
    def test_registration_all_tools(self) -> None:
        """When Playwright is available, register real handlers, not stubs."""
        registry = ToolRegistry()
        register_browser_tools(registry)
        tool = registry.get('browser_navigate')
        assert tool is not None
        result = tool.handler({'url': 'data:text/html,<h1>OK</h1>'})
        self.assertEqual(result['status'], 'ok')
