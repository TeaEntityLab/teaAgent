"""Browser automation tools using Playwright.

All tools are gated behind a ``HAS_PLAYWRIGHT`` feature flag.  When Playwright
is not installed, every registered tool returns an immediate error message
instead of raising.
"""

from __future__ import annotations

from typing import Any

try:
    import playwright  # noqa: F401

    HAS_PLAYWRIGHT = True
except ImportError:  # pragma: no cover
    HAS_PLAYWRIGHT = False

from teaagent.tools import ToolAnnotations, ToolRegistry
from teaagent.workspace_tools._helpers import object_schema

# ---------------------------------------------------------------------------
# Lazy browser singleton
# ---------------------------------------------------------------------------

_BROWSER_INSTANCE: Any = None
"""Lazily initialised Playwright browser object (sync wrapper around async)."""
_PLAYWRIGHT_INSTANCE: Any = None
_PAGE_INSTANCE: Any = None


def _ensure_browser() -> Any:
    """Return a global browser instance, starting one if needed."""
    global _BROWSER_INSTANCE  # noqa: PLW0603
    global _PLAYWRIGHT_INSTANCE  # noqa: PLW0603
    if _BROWSER_INSTANCE is None:
        if not HAS_PLAYWRIGHT:
            raise RuntimeError(
                'Playwright is not installed. Install with: pip install teaagent[playwright]'
            )
        from playwright.sync_api import sync_playwright

        _PLAYWRIGHT_INSTANCE = sync_playwright().start()
        _BROWSER_INSTANCE = _PLAYWRIGHT_INSTANCE.chromium.launch(headless=True)
    return _BROWSER_INSTANCE


def _get_page() -> Any:
    """Return a reusable browser page, creating one if needed."""
    global _PAGE_INSTANCE  # noqa: PLW0603
    if _PAGE_INSTANCE is None or _PAGE_INSTANCE.is_closed():
        browser = _ensure_browser()
        _PAGE_INSTANCE = browser.new_page()
    return _PAGE_INSTANCE


def _cleanup_browser() -> None:
    """Close the global browser instance (used by tests)."""
    global _BROWSER_INSTANCE  # noqa: PLW0603
    global _PLAYWRIGHT_INSTANCE  # noqa: PLW0603
    global _PAGE_INSTANCE  # noqa: PLW0603
    if _PAGE_INSTANCE is not None and not _PAGE_INSTANCE.is_closed():
        _PAGE_INSTANCE.close()
    _PAGE_INSTANCE = None
    if _BROWSER_INSTANCE is not None:
        _BROWSER_INSTANCE.close()
    _BROWSER_INSTANCE = None
    if _PLAYWRIGHT_INSTANCE is not None:
        _PLAYWRIGHT_INSTANCE.stop()
    _PLAYWRIGHT_INSTANCE = None


def _browser_error_result(exc: Exception) -> dict[str, Any]:
    return {'status': 'error', 'message': str(exc)}


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


def browser_navigate(url: str, *, timeout_ms: int = 30000) -> dict[str, Any]:
    """Navigate to *url* and return the resulting page title and URL."""
    try:
        page = _get_page()
        page.goto(url, timeout=timeout_ms, wait_until='domcontentloaded')
        return {
            'status': 'ok',
            'url': page.url,
            'title': page.title(),
        }
    except Exception as exc:
        return _browser_error_result(exc)


def browser_snapshot(*, timeout_ms: int = 5000) -> dict[str, Any]:
    """Return the current page state: URL, title, visible text, links."""
    try:
        page = _get_page()
        page.wait_for_load_state('networkidle', timeout=timeout_ms)
        links = page.eval_on_selector_all(
            'a[href]', 'els => els.map(e => ({text: e.innerText.trim(), href: e.href}))'
        )
        return {
            'status': 'ok',
            'url': page.url,
            'title': page.title(),
            'text': page.inner_text('body')[:10000],
            'links': links[:50],
        }
    except Exception as exc:
        return _browser_error_result(exc)


def browser_screenshot(
    *, full_page: bool = False, timeout_ms: int = 10000
) -> dict[str, Any]:
    """Take a screenshot and return it as a base64-encoded PNG."""
    try:
        import base64

        page = _get_page()

        b64 = base64.b64encode(
            page.screenshot(full_page=full_page, timeout=timeout_ms)
        ).decode('ascii')
        return {'status': 'ok', 'data': b64, 'mime_type': 'image/png'}
    except Exception as exc:
        return _browser_error_result(exc)


def browser_get_content(
    *, include_html: bool = False, timeout_ms: int = 5000
) -> dict[str, Any]:
    """Extract page content as text or HTML."""
    try:
        page = _get_page()
        page.wait_for_load_state('networkidle', timeout=timeout_ms)
        if include_html:
            content = page.content()
        else:
            content = page.inner_text('body')
        return {
            'status': 'ok',
            'url': page.url,
            'content': content[:50000],
            'truncated': len(content) > 50000,
        }
    except Exception as exc:
        return _browser_error_result(exc)


def browser_click(selector: str, *, timeout_ms: int = 10000) -> dict[str, Any]:
    """Click an element identified by *selector*."""
    try:
        page = _get_page()
        page.click(selector, timeout=timeout_ms)
        return {
            'status': 'ok',
            'url': page.url,
            'title': page.title(),
        }
    except Exception as exc:
        return _browser_error_result(exc)


def browser_fill(
    selector: str, value: str, *, timeout_ms: int = 10000
) -> dict[str, Any]:
    """Fill a form field identified by *selector* with *value*."""
    try:
        page = _get_page()
        page.fill(selector, value, timeout=timeout_ms)
        return {'status': 'ok'}
    except Exception as exc:
        return _browser_error_result(exc)


def browser_evaluate(expression: str) -> dict[str, Any]:
    """Run JavaScript *expression* in the page context."""
    try:
        page = _get_page()
        result = page.evaluate(expression)
        return {'status': 'ok', 'result': str(result)[:10000]}
    except Exception as exc:
        return _browser_error_result(exc)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


_DISABLED_MESSAGE = (
    'Playwright is not installed. '
    'Install it with: pip install teaagent[playwright] && playwright install'
)


def _disabled_handler(message: str) -> dict[str, Any]:
    return {'status': 'error', 'message': message}


def register_browser_tools(
    registry: ToolRegistry,
) -> None:
    """Register browser automation tools into *registry*.

    When Playwright is not installed, all tools return an immediate error
    message so the agent can fail gracefully.
    """

    if not HAS_PLAYWRIGHT:
        _register_disabled(registry)
        return

    registry.register(
        name='browser_navigate',
        description='Navigate to a URL in a headless browser. Returns the page title and final URL.',
        input_schema=object_schema(
            {
                'url': {'type': 'string', 'description': 'The URL to navigate to.'},
                'timeout_ms': {
                    'type': 'integer',
                    'description': 'Navigation timeout in milliseconds (default 30000).',
                },
            },
            required=['url'],
        ),
        output_schema=object_schema(
            {
                'status': 'string',
                'url': 'string',
                'title': 'string',
                'message': 'string',
            },
            required=['status'],
        ),
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: browser_navigate(
            args['url'], timeout_ms=args.get('timeout_ms', 30000)
        ),
    )

    registry.register(
        name='browser_snapshot',
        description='Get current page state: URL, title, visible text, and links.',
        input_schema=object_schema(
            {
                'timeout_ms': {
                    'type': 'integer',
                    'description': 'Wait timeout in milliseconds (default 5000).',
                },
            },
            required=[],
        ),
        output_schema=object_schema(
            {
                'status': 'string',
                'url': 'string',
                'title': 'string',
                'text': 'string',
                'links': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'text': {'type': 'string'},
                            'href': {'type': 'string'},
                        },
                    },
                },
                'message': 'string',
            },
            required=['status'],
        ),
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: browser_snapshot(timeout_ms=args.get('timeout_ms', 5000)),
    )

    registry.register(
        name='browser_screenshot',
        description='Take a screenshot of the current page. Returns base64-encoded PNG.',
        input_schema=object_schema(
            {
                'full_page': {
                    'type': 'boolean',
                    'description': 'Capture full scrollable page (default false).',
                },
                'timeout_ms': {
                    'type': 'integer',
                    'description': 'Timeout in milliseconds (default 10000).',
                },
            },
            required=[],
        ),
        output_schema=object_schema(
            {
                'status': 'string',
                'data': 'string',
                'mime_type': 'string',
                'message': 'string',
            },
            required=['status'],
        ),
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: browser_screenshot(
            full_page=args.get('full_page', False),
            timeout_ms=args.get('timeout_ms', 10000),
        ),
    )

    registry.register(
        name='browser_get_content',
        description='Extract visible text or HTML content from the current page.',
        input_schema=object_schema(
            {
                'include_html': {
                    'type': 'boolean',
                    'description': 'Return HTML instead of plain text (default false).',
                },
                'timeout_ms': {
                    'type': 'integer',
                    'description': 'Wait timeout in milliseconds (default 5000).',
                },
            },
            required=[],
        ),
        output_schema=object_schema(
            {
                'status': 'string',
                'url': 'string',
                'content': 'string',
                'truncated': 'boolean',
                'message': 'string',
            },
            required=['status'],
        ),
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: browser_get_content(
            include_html=args.get('include_html', False),
            timeout_ms=args.get('timeout_ms', 5000),
        ),
    )

    registry.register(
        name='browser_click',
        description='Click an element on the page by CSS selector.',
        input_schema=object_schema(
            {
                'selector': {
                    'type': 'string',
                    'description': 'CSS selector of the element to click.',
                },
                'timeout_ms': {
                    'type': 'integer',
                    'description': 'Timeout in milliseconds (default 10000).',
                },
            },
            required=['selector'],
        ),
        output_schema=object_schema(
            {
                'status': 'string',
                'url': 'string',
                'title': 'string',
                'message': 'string',
            },
            required=['status'],
        ),
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: browser_click(
            args['selector'], timeout_ms=args.get('timeout_ms', 10000)
        ),
    )

    registry.register(
        name='browser_fill',
        description='Fill a form field with a value, identified by CSS selector.',
        input_schema=object_schema(
            {
                'selector': {
                    'type': 'string',
                    'description': 'CSS selector of the input element.',
                },
                'value': {
                    'type': 'string',
                    'description': 'Value to fill into the field.',
                },
                'timeout_ms': {
                    'type': 'integer',
                    'description': 'Timeout in milliseconds (default 10000).',
                },
            },
            required=['selector', 'value'],
        ),
        output_schema=object_schema(
            {'status': 'string', 'message': 'string'},
            required=['status'],
        ),
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: browser_fill(
            args['selector'], args['value'], timeout_ms=args.get('timeout_ms', 10000)
        ),
    )

    registry.register(
        name='browser_evaluate',
        description='Run JavaScript code in the browser page context.',
        input_schema=object_schema(
            {
                'expression': {
                    'type': 'string',
                    'description': 'JavaScript expression to evaluate.',
                },
            },
            required=['expression'],
        ),
        output_schema=object_schema(
            {'status': 'string', 'result': 'string', 'message': 'string'},
            required=['status'],
        ),
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: browser_evaluate(args['expression']),
    )


def _register_disabled(registry: ToolRegistry) -> None:
    """Register stub tools that return an install-prompt error."""
    disabled_tools = [
        ('browser_navigate', 'Navigate to a URL in a headless browser.'),
        (
            'browser_snapshot',
            'Get current page state: URL, title, visible text, and links.',
        ),
        ('browser_screenshot', 'Take a screenshot of the current page.'),
        ('browser_get_content', 'Extract visible text or HTML from the current page.'),
        ('browser_click', 'Click an element by CSS selector.'),
        ('browser_fill', 'Fill a form field with a value.'),
        ('browser_evaluate', 'Run JavaScript in the browser page context.'),
    ]
    for name, desc in disabled_tools:
        registry.register(
            name=name,
            description=desc,
            input_schema=object_schema({'message': 'string'}, required=['message']),
            output_schema=object_schema(
                {'status': 'string', 'message': 'string'},
                required=['status'],
            ),
            annotations=ToolAnnotations(read_only=True),
            handler=lambda _args, msg=_DISABLED_MESSAGE: {  # type: ignore[misc]
                'status': 'error',
                'message': msg,
            },
        )
