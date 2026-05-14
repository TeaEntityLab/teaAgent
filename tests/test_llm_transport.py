from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from teaagent.llm._transport import UrllibHTTPTransport, build_ssl_context_from_env


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> '_FakeHTTPResponse':
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode('utf-8')


class LLMTransportTests(unittest.TestCase):
    def test_build_ssl_context_returns_none_without_tls_env(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(build_ssl_context_from_env())

    def test_build_ssl_context_loads_ca_bundle_from_requests_env(self) -> None:
        context = MagicMock()
        with (
            patch.dict(os.environ, {'REQUESTS_CA_BUNDLE': '/tmp/ca.pem'}, clear=True),
            patch(
                'teaagent.llm._transport.ssl.create_default_context',
                return_value=context,
            ),
        ):
            result = build_ssl_context_from_env()

        self.assertIs(result, context)
        context.load_verify_locations.assert_called_once_with(cafile='/tmp/ca.pem')

    def test_build_ssl_context_loads_client_cert_and_key(self) -> None:
        context = MagicMock()
        with (
            patch.dict(
                os.environ,
                {
                    'TEAAGENT_TLS_CLIENT_CERT': '/tmp/client.crt',
                    'TEAAGENT_TLS_CLIENT_KEY': '/tmp/client.key',
                },
                clear=True,
            ),
            patch(
                'teaagent.llm._transport.ssl.create_default_context',
                return_value=context,
            ),
        ):
            result = build_ssl_context_from_env()

        self.assertIs(result, context)
        context.load_cert_chain.assert_called_once_with(
            certfile='/tmp/client.crt', keyfile='/tmp/client.key'
        )

    def test_transport_post_json_passes_ssl_context_when_tls_env_set(self) -> None:
        context = MagicMock()
        transport = UrllibHTTPTransport()

        with (
            patch.dict(os.environ, {'REQUESTS_CA_BUNDLE': '/tmp/ca.pem'}, clear=True),
            patch(
                'teaagent.llm._transport.ssl.create_default_context',
                return_value=context,
            ),
            patch(
                'teaagent.llm._transport.urllib_request.urlopen',
                return_value=_FakeHTTPResponse({'ok': True}),
            ) as mock_urlopen,
        ):
            result = transport.post_json(
                'https://example.com/v1',
                {'authorization': 'Bearer x'},
                {'hello': 'world'},
                timeout=5,
            )

        self.assertEqual(result, {'ok': True})
        _, kwargs = mock_urlopen.call_args
        self.assertEqual(kwargs['timeout'], 5)
        self.assertIs(kwargs['context'], context)


if __name__ == '__main__':
    unittest.main()
