from __future__ import annotations

from typing import Any, Optional, Protocol
from urllib.parse import parse_qs, urlparse

from teaagent.oauth21 import (
    _DPOP_HEADER,
    _DPOP_NONCE_HEADER,
    OAuth21AuthorizationServer,
    OAuth21Error,
)


class _HandlerProtocol(Protocol):
    """Protocol for HTTP request handlers used by OAuth endpoints."""

    path: str
    headers: Any
    rfile: Any

    def _send_status(self, status: int, message: Optional[str] = None) -> None: ...

    def _send_json(
        self,
        status: int,
        body: dict[str, object],
        extra_headers: Optional[dict[str, str]] = None,
    ) -> None: ...

    def send_response(self, code: int) -> None: ...

    def send_header(self, keyword: str, value: str) -> None: ...

    def end_headers(self) -> None: ...

    def _content_length(self) -> tuple[Optional[int], Optional[str]]: ...


def _handle_oauth_metadata(
    handler: _HandlerProtocol, oauth_server: Optional[OAuth21AuthorizationServer]
) -> None:
    if oauth_server is None:
        handler._send_status(404, 'not found')
        return
    metadata = oauth_server.metadata()
    dpop_header = handler.headers.get(_DPOP_HEADER)
    extra: dict[str, str] = {}
    if dpop_header:
        extra[_DPOP_NONCE_HEADER] = oauth_server.generate_dpop_nonce()
    handler._send_json(200, metadata, extra_headers=extra or None)


def _handle_oauth_authorize(
    handler: _HandlerProtocol, oauth_server: Optional[OAuth21AuthorizationServer]
) -> None:
    if oauth_server is None:
        handler._send_status(404, 'not found')
        return
    parsed = urlparse(handler.path)
    params = parse_qs(parsed.query)

    from teaagent.mcp_http import _first_param

    client_id = _first_param(params, 'client_id')
    redirect_uri = _first_param(params, 'redirect_uri')
    code_challenge = _first_param(params, 'code_challenge')
    code_challenge_method = _first_param(params, 'code_challenge_method') or 'S256'
    scope = _first_param(params, 'scope') or 'mcp'
    state = _first_param(params, 'state')

    if not client_id or not redirect_uri or not code_challenge:
        handler._send_json(
            400,
            {
                'error': 'invalid_request',
                'error_description': (
                    'client_id, redirect_uri, and code_challenge are required'
                ),
            },
        )
        return

    try:
        redirect_url, _ = oauth_server.create_authorization_code(
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            scope=scope,
            state=state,
        )
        handler.send_response(302)
        handler.send_header('Location', redirect_url)
        handler.send_header('Content-Length', '0')
        handler.end_headers()
    except OAuth21Error as exc:
        handler._send_json(
            400,
            {'error': 'invalid_request', 'error_description': str(exc)},
        )


def _handle_oauth_token(  # noqa: C901
    handler: _HandlerProtocol, oauth_server: Optional[OAuth21AuthorizationServer]
) -> None:
    if oauth_server is None:
        handler._send_status(404, 'not found')
        return

    length, length_error = handler._content_length()
    if length_error is not None:
        status = 413 if length_error == 'body too large' else 400
        handler._send_json(
            status,
            {'error': 'invalid_request', 'error_description': length_error},
        )
        return
    assert length is not None
    raw = handler.rfile.read(length)
    try:
        body = raw.decode('utf-8')
    except UnicodeDecodeError:
        handler._send_json(
            400,
            {
                'error': 'invalid_request',
                'error_description': 'invalid encoding',
            },
        )
        return
    params = parse_qs(body)

    from teaagent.mcp_http import _first_param

    grant_type = _first_param(params, 'grant_type')
    code = _first_param(params, 'code')
    code_verifier = _first_param(params, 'code_verifier')
    refresh_token = _first_param(params, 'refresh_token')
    client_id = _first_param(params, 'client_id')
    client_secret = _first_param(params, 'client_secret')
    dpop_proof = handler.headers.get(_DPOP_HEADER)

    extra_headers: dict[str, str] = {}
    dpop_nonce = oauth_server.generate_dpop_nonce()
    extra_headers[_DPOP_NONCE_HEADER] = dpop_nonce

    if grant_type == 'authorization_code':
        if not code:
            handler._send_json(
                400,
                {
                    'error': 'invalid_request',
                    'error_description': 'code is required',
                },
            )
            return
        if not code_verifier:
            handler._send_json(
                400,
                {
                    'error': 'invalid_request',
                    'error_description': 'code_verifier is required',
                },
            )
            return
    elif grant_type == 'refresh_token':
        if not refresh_token:
            handler._send_json(
                400,
                {
                    'error': 'invalid_request',
                    'error_description': 'refresh_token is required',
                },
            )
            return
    else:
        handler._send_json(
            400,
            {
                'error': 'unsupported_grant_type',
                'error_description': (
                    'Supported grant types: authorization_code, refresh_token'
                ),
            },
        )
        return

    try:
        if grant_type == 'authorization_code':
            assert code is not None and code_verifier is not None
            response = oauth_server.exchange_code(
                code=code,
                code_verifier=code_verifier,
                client_id=client_id,
                client_secret=client_secret,
                dpop_proof_jwt=dpop_proof,
            )
        else:
            assert refresh_token is not None
            response = oauth_server.exchange_refresh_token(
                refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                dpop_proof_jwt=dpop_proof,
            )
    except OAuth21Error as exc:
        status_code = 400
        error_code = 'invalid_grant'
        if 'DPoP' in str(exc) or 'dpop' in str(exc).lower():
            status_code = 401
            error_code = 'invalid_dpop_proof'
            extra_headers[_DPOP_NONCE_HEADER] = dpop_nonce
        elif 'client' in str(exc).lower():
            status_code = 401
            error_code = 'invalid_client'
        handler._send_json(
            status_code,
            {'error': error_code, 'error_description': str(exc)},
            extra_headers=extra_headers,
        )
        return

    token_body: dict[str, object] = {
        'access_token': response.access_token,
        'token_type': response.token_type,
        'expires_in': response.expires_in,
        'scope': response.scope,
    }
    if response.refresh_token is not None:
        token_body['refresh_token'] = response.refresh_token
    handler._send_json(
        200,
        token_body,
        extra_headers=extra_headers,
    )
