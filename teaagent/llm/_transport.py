from __future__ import annotations

import json
import os
import ssl
from typing import Any
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from teaagent.llm._types import LLMHTTPError


def build_ssl_context_from_env() -> ssl.SSLContext | None:
    ca_bundle = os.environ.get('REQUESTS_CA_BUNDLE') or os.environ.get('SSL_CERT_FILE')
    client_cert = os.environ.get('TEAAGENT_TLS_CLIENT_CERT')
    client_key = os.environ.get('TEAAGENT_TLS_CLIENT_KEY')
    if not ca_bundle and not client_cert:
        return None
    context = ssl.create_default_context()
    if ca_bundle:
        context.load_verify_locations(cafile=ca_bundle)
    if client_cert:
        if client_key:
            context.load_cert_chain(certfile=client_cert, keyfile=client_key)
        else:
            context.load_cert_chain(certfile=client_cert)
    return context


class UrllibHTTPTransport:
    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        *,
        timeout: int,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode('utf-8')
        req = urllib_request.Request(
            url,
            data=body,
            headers={
                'content-type': 'application/json',
                'user-agent': 'TeaAgent',
                **headers,
            },
            method='POST',
        )
        try:
            ssl_context = build_ssl_context_from_env()
            request_kwargs: dict[str, Any] = {'timeout': timeout}
            if ssl_context is not None:
                request_kwargs['context'] = ssl_context
            with urllib_request.urlopen(req, **request_kwargs) as response:
                return json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            raise LLMHTTPError(
                f'HTTP {exc.code}: {detail}', status_code=exc.code
            ) from exc
        except URLError as exc:
            raise LLMHTTPError(f'HTTP request failed: {exc.reason}') from exc
