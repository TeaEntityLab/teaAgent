"""TLS / mTLS helpers for embedded HTTP servers."""

from __future__ import annotations

import ssl
from pathlib import Path


def build_server_ssl_context(
    *,
    cert_file: Path,
    key_file: Path,
    client_ca_file: Path | None = None,
) -> ssl.SSLContext:
    """Build a server TLS context; when *client_ca_file* is set, require client certs (mTLS)."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(cert_file), str(key_file))
    if client_ca_file is not None:
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.load_verify_locations(cafile=str(client_ca_file))
    return ctx


def wrap_server_socket(httpd: object, ssl_context: ssl.SSLContext) -> None:
    """Wrap an existing ``HTTPServer`` listening socket with *ssl_context*."""
    httpd.socket = ssl_context.wrap_socket(httpd.socket, server_side=True)  # type: ignore[attr-defined]
