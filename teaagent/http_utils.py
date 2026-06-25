"""Secure HTTP utilities for external network requests.

This module provides a centralized wrapper for HTTP requests with:
- Scheme validation (https:// by default, http:// only if explicitly allowed)
- Timeout enforcement
- Redirect limit control
- Consistent error handling

This replaces direct urllib.request.urlopen calls throughout the codebase
to improve security and consistency.
"""

from __future__ import annotations

import logging
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default timeout for HTTP requests (seconds)
DEFAULT_TIMEOUT = 30

# Maximum number of redirects to follow
MAX_REDIRECTS = 5

# Allowed schemes (https is always allowed, http requires explicit allow_http)
DEFAULT_ALLOWED_SCHEMES = {'https'}


def _allowed_schemes(*, allow_http: bool) -> set[str]:
    return DEFAULT_ALLOWED_SCHEMES | ({'http'} if allow_http else set())


def _validate_url_scheme(url: str, *, allow_http: bool) -> None:
    parsed = urllib.parse.urlparse(url)
    allowed_schemes = _allowed_schemes(allow_http=allow_http)
    if parsed.scheme not in allowed_schemes:
        raise ValueError(
            f"URL scheme '{parsed.scheme}' not allowed. "
            f'Allowed schemes: {", ".join(sorted(allowed_schemes))}'
        )


def safe_urlopen_request(
    request: urllib.request.Request,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    allow_http: bool = False,
    context: Optional[ssl.SSLContext] = None,
) -> Any:
    """Open a pre-built Request after validating its URL scheme."""
    _validate_url_scheme(request.full_url, allow_http=allow_http)
    open_kwargs: dict[str, Any] = {'timeout': timeout}
    if context is not None:
        open_kwargs['context'] = context
    # Centralized, scheme-validated HTTP entry point (S-05).
    return urllib.request.urlopen(request, **open_kwargs)  # nosec B310


def safe_urlopen(  # noqa: C901
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    allow_http: bool = False,
    max_redirects: int = MAX_REDIRECTS,
    data: Optional[bytes] = None,
    headers: Optional[dict[str, str]] = None,
    method: str = 'GET',
    context: Optional[ssl.SSLContext] = None,
) -> Any:
    """Open a URL with security constraints and consistent error handling.

    Args:
        url: The URL to open
        timeout: Request timeout in seconds (default: 30)
        allow_http: Whether to allow http:// scheme (default: False, only https://)
        max_redirects: Maximum number of redirects to follow (default: 5)
        data: Optional data to send with the request (for POST requests)
        headers: Optional HTTP headers to include in the request
        method: HTTP method (default: GET)
        context: Optional SSL context for HTTPS requests

    Returns:
        The response object from urllib.request.urlopen

    Raises:
        ValueError: If the URL scheme is not allowed
        urllib.error.URLError: If the request fails
        urllib.error.HTTPError: If the HTTP request returns an error status
        TimeoutError: If the request times out
    """
    _validate_url_scheme(url, allow_http=allow_http)
    allowed_schemes = _allowed_schemes(allow_http=allow_http)

    # Create request with headers if provided
    if data is not None:
        req = urllib.request.Request(
            url, data=data, headers=headers or {}, method=method
        )
    else:
        req = urllib.request.Request(url, headers=headers or {}, method=method)

    # Set redirect limit
    redirect_count = 0
    current_url = url

    while redirect_count <= max_redirects:
        try:
            open_kwargs: dict[str, Any] = {'timeout': timeout}
            if context is not None:
                open_kwargs['context'] = context
            response = urllib.request.urlopen(req, **open_kwargs)  # nosec B310
            # Check for redirect
            if response.getcode() in (301, 302, 303, 307, 308):
                redirect_count += 1
                if redirect_count > max_redirects:
                    raise ValueError(f'Too many redirects (max: {max_redirects})')
                location = response.headers.get('Location')
                if not location:
                    raise ValueError('Redirect response missing Location header')
                current_url = location
                # Validate redirect URL scheme
                redirect_parsed = urllib.parse.urlparse(current_url)
                if redirect_parsed.scheme not in allowed_schemes:
                    raise ValueError(
                        f"Redirect to scheme '{redirect_parsed.scheme}' not allowed. "
                        f'Allowed schemes: {", ".join(sorted(allowed_schemes))}'
                    )
                req = urllib.request.Request(
                    current_url, headers=headers or {}, method=method
                )
                continue
            return response
        except urllib.error.HTTPError:
            # HTTP errors should be propagated
            raise
        except urllib.error.URLError as exc:
            # Log but propagate URL errors
            logger.debug('URL request failed: %s (url=%s)', exc, url)
            raise
        except TimeoutError as exc:
            logger.debug('URL request timed out: %s (url=%s)', exc, url)
            raise

    # Should not reach here, but just in case
    raise ValueError(f'Too many redirects (max: {max_redirects})')
