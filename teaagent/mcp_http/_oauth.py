from __future__ import annotations

from typing import Optional
from urllib.parse import parse_qs, urlparse

from teaagent.oauth21 import (
    _DPOP_HEADER,
    _DPOP_NONCE_HEADER,
    OAuth21AuthorizationServer,
    OAuth21Error,
)


def _handle_oauth_metadata(
    handler: object, oauth_server: Optional[OAuth21AuthorizationServer]
) -> None:
    if oauth_server is None:
        handler._send_status(404, 'not found')  # type: ignore[attr-defined]
        return
    metadata = oauth_server.metadata()
    dpop_header = handler.headers.get(_DPOP_HEADER)  # type: ignore[attr-defined]
    extra: dict[str, str] = {}
    if dpop_header:
        extra[_DPOP_NONCE_HEADER] = oauth_server.generate_dpop_nonce()
    handler._send_json(200, metadata, extra_headers=extra or None)  # type: ignore[attr-defined]


def _handle_oauth_authorize(
    handler: object, oauth_server: Optional[OAuth21AuthorizationServer]
) -> None:
    if oauth_server is None:
        handler._send_status(404, 'not found')  # type: ignore[attr-defined]
        return
    parsed = urlparse(handler.path)  # type: ignore[attr-defined]
    params = parse_qs(parsed.query)

    from teaagent.mcp_http import _first_param

    client_id = _first_param(params, 'client_id')
    redirect_uri = _first_param(params, 'redirect_uri')
    code_challenge = _first_param(params, 'code_challenge')
    code_challenge_method = _first_param(params, 'code_challenge_method') or 'S256'
    scope = _first_param(params, 'scope') or 'mcp'
    state = _first_param(params, 'state')

    if not client_id or not redirect_uri or not code_challenge:
        handler._send_json(  # type: ignore[attr-defined]
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
        handler.send_response(302)  # type: ignore[attr-defined]
        handler.send_header('Location', redirect_url)  # type: ignore[attr-defined]
        handler.send_header('Content-Length', '0')  # type: ignore[attr-defined]
        handler.end_headers()  # type: ignore[attr-defined]
    except OAuth21Error as exc:
        handler._send_json(  # type: ignore[attr-defined]
            400,
            {'error': 'invalid_request', 'error_description': str(exc)},
        )


def _handle_oauth_token(
    handler: object, oauth_server: Optional[OAuth21AuthorizationServer]
) -> None:
    if oauth_server is None:
        handler._send_status(404, 'not found')  # type: ignore[attr-defined]
        return

    length, length_error = handler._content_length()  # type: ignore[attr-defined]
    if length_error is not None:
        status = 413 if length_error == 'body too large' else 400
        handler._send_json(  # type: ignore[attr-defined]
            status,
            {'error': 'invalid_request', 'error_description': length_error},
        )
        return
    assert length is not None
    raw = handler.rfile.read(length)  # type: ignore[attr-defined]
    try:
        body = raw.decode('utf-8')
    except UnicodeDecodeError:
        handler._send_json(  # type: ignore[attr-defined]
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
    client_id = _first_param(params, 'client_id')
    client_secret = _first_param(params, 'client_secret')
    dpop_proof = handler.headers.get(_DPOP_HEADER)  # type: ignore[attr-defined]

    if grant_type != 'authorization_code':
        handler._send_json(  # type: ignore[attr-defined]
            400,
            {
                'error': 'unsupported_grant_type',
                'error_description': 'Only authorization_code is supported',
            },
        )
        return
    if not code:
        handler._send_json(  # type: ignore[attr-defined]
            400,
            {
                'error': 'invalid_request',
                'error_description': 'code is required',
            },
        )
        return
    if not code_verifier:
        handler._send_json(  # type: ignore[attr-defined]
            400,
            {
                'error': 'invalid_request',
                'error_description': 'code_verifier is required',
            },
        )
        return

    extra_headers: dict[str, str] = {}
    dpop_nonce = oauth_server.generate_dpop_nonce()
    extra_headers[_DPOP_NONCE_HEADER] = dpop_nonce

    try:
        response = oauth_server.exchange_code(
            code=code,
            code_verifier=code_verifier,
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
        handler._send_json(  # type: ignore[attr-defined]
            status_code,
            {'error': error_code, 'error_description': str(exc)},
            extra_headers=extra_headers,
        )
        return

    handler._send_json(  # type: ignore[attr-defined]
        200,
        {
            'access_token': response.access_token,
            'token_type': response.token_type,
            'expires_in': response.expires_in,
            'scope': response.scope,
            'refresh_token': response.refresh_token,
        },
        extra_headers=extra_headers,
    )
