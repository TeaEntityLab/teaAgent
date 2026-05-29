from __future__ import annotations

import json
from typing import Any, Iterator
from unittest.mock import patch

import pytest

from teaagent.llm._adapters import (
    _extract_claude_tool_calls,
    _extract_gemini_safety,
    _extract_gemini_stream_text,
    _extract_gemini_tool_calls,
    _extract_openai_tool_calls,
    _native_tool_calls_to_decision_text,
    _provider_extra_headers,
)
from teaagent.llm._config import _estimate_cost
from teaagent.llm._extract import _extract_openai_content
from teaagent.llm._retry import _call_with_retry
from teaagent.llm._sse import consume_sse_json_chunks, iter_sse_data_lines
from teaagent.llm._transport import build_ssl_context_from_env
from teaagent.llm._types import (
    LLMHTTPError,
    LLMResponseFormatError,
    LLMToolCall,
    SafetyCategory,
)

# ─── _sse.py ────────────────────────────────────────────────────────────────────


class TestIterSseDataLines:
    @staticmethod
    def _iter_bytes(lines: list[str]) -> Iterator[bytes]:
        for line in lines:
            yield line.encode()

    def test_yields_data_lines(self) -> None:
        lines = self._iter_bytes(['data: hello', 'data: world'])
        assert list(iter_sse_data_lines(lines)) == ['hello', 'world']

    def test_skips_non_data_lines(self) -> None:
        lines = self._iter_bytes([':comment', 'event: msg', 'data: payload'])
        assert list(iter_sse_data_lines(lines)) == ['payload']

    def test_done_with_data_prefix_terminates(self) -> None:
        lines = self._iter_bytes(['data: a', 'data: [DONE]', 'data: b'])
        assert list(iter_sse_data_lines(lines)) == ['a']

    def test_handles_str_input(self) -> None:
        lines: Iterator[str] = iter(['data: hello'])
        assert list(iter_sse_data_lines(lines)) == ['hello']

    def test_handles_data_with_colons(self) -> None:
        lines = self._iter_bytes(['data: {"key":"val"}'])
        assert list(iter_sse_data_lines(lines)) == ['{"key":"val"}']

    def test_no_data_lines_returns_nothing(self) -> None:
        lines = self._iter_bytes([':keepalive'])
        assert list(iter_sse_data_lines(lines)) == []


class TestConsumeSseJsonChunks:
    def test_parses_json_chunks(self) -> None:
        chunks: list[dict[str, Any]] = []
        lines: Iterator[bytes] = iter(
            [b'data: {"a":1}', b'data: {"b":2}', b'data: [DONE]']
        )
        consume_sse_json_chunks(lines, on_data=chunks.append)
        assert chunks == [{'a': 1}, {'b': 2}]

    def test_skips_malformed_json(self) -> None:
        chunks: list[dict[str, Any]] = []
        lines: Iterator[bytes] = iter(
            [b'data: {bad json}', b'data: {"ok":1}', b'data: [DONE]']
        )
        consume_sse_json_chunks(lines, on_data=chunks.append)
        assert chunks == [{'ok': 1}]

    def test_empty_input(self) -> None:
        chunks: list[dict[str, Any]] = []
        consume_sse_json_chunks(iter([]), on_data=chunks.append)
        assert chunks == []

    def test_only_done_returns_nothing(self) -> None:
        chunks: list[dict[str, Any]] = []
        consume_sse_json_chunks(iter([b'data: [DONE]']), on_data=chunks.append)
        assert chunks == []


# ─── _adapters.py: tool call extraction ─────────────────────────────────────────


class TestExtractOpenaiToolCalls:
    def test_extracts_single_tool_call(self) -> None:
        response: dict[str, Any] = {
            'choices': [
                {
                    'message': {
                        'tool_calls': [
                            {
                                'id': 'call_1',
                                'function': {
                                    'name': 'get_weather',
                                    'arguments': '{"city":"NYC"}',
                                },
                            }
                        ]
                    }
                }
            ]
        }
        result = _extract_openai_tool_calls(response)
        assert result == [
            LLMToolCall(
                tool_name='get_weather',
                tool_input={'city': 'NYC'},
                call_id='call_1',
            )
        ]

    def test_extracts_multiple_tool_calls(self) -> None:
        response: dict[str, Any] = {
            'choices': [
                {
                    'message': {
                        'tool_calls': [
                            {
                                'id': 'c1',
                                'function': {'name': 'a', 'arguments': '{"x":1}'},
                            },
                            {
                                'id': 'c2',
                                'function': {'name': 'b', 'arguments': '{"y":2}'},
                            },
                        ]
                    }
                }
            ]
        }
        result = _extract_openai_tool_calls(response)
        assert len(result) == 2
        assert result[0].tool_name == 'a'
        assert result[1].tool_name == 'b'

    def test_empty_when_no_choices(self) -> None:
        assert _extract_openai_tool_calls({}) == []

    def test_empty_when_no_tool_calls(self) -> None:
        response: dict[str, Any] = {
            'choices': [{'message': {'content': 'text'}}]
        }
        assert _extract_openai_tool_calls(response) == []

    def test_invalid_json_arguments_uses_empty_dict(self) -> None:
        response: dict[str, Any] = {
            'choices': [
                {
                    'message': {
                        'tool_calls': [
                            {
                                'id': 'c1',
                                'function': {
                                    'name': 'fn',
                                    'arguments': 'not-json',
                                },
                            }
                        ]
                    }
                }
            ]
        }
        result = _extract_openai_tool_calls(response)
        assert result[0].tool_input == {}


class TestExtractClaudeToolCalls:
    def test_extracts_tool_calls(self) -> None:
        response: dict[str, Any] = {
            'content': [
                {'type': 'text', 'text': 'thinking'},
                {
                    'type': 'tool_use',
                    'name': 'read_file',
                    'input': {'path': '/tmp/x'},
                    'id': 'tu_1',
                },
            ]
        }
        result = _extract_claude_tool_calls(response)
        assert result == [
            LLMToolCall(
                tool_name='read_file',
                tool_input={'path': '/tmp/x'},
                call_id='tu_1',
            )
        ]

    def test_empty_when_no_tool_use(self) -> None:
        response: dict[str, Any] = {
            'content': [{'type': 'text', 'text': 'hello'}]
        }
        assert _extract_claude_tool_calls(response) == []

    def test_empty_when_no_content(self) -> None:
        assert _extract_claude_tool_calls({}) == []


class TestExtractGeminiToolCalls:
    def test_extracts_function_calls(self) -> None:
        response: dict[str, Any] = {
            'candidates': [
                {
                    'content': {
                        'parts': [
                            {
                                'functionCall': {
                                    'name': 'search',
                                    'args': {'q': 'weather'},
                                }
                            }
                        ]
                    }
                }
            ]
        }
        result = _extract_gemini_tool_calls(response)
        assert result == [
            LLMToolCall(tool_name='search', tool_input={'q': 'weather'})
        ]

    def test_empty_when_no_candidates(self) -> None:
        assert _extract_gemini_tool_calls({}) == []

    def test_empty_when_no_function_calls(self) -> None:
        response: dict[str, Any] = {
            'candidates': [
                {'content': {'parts': [{'text': 'hello'}]}}
            ]
        }
        assert _extract_gemini_tool_calls(response) == []


class TestNativeToolCallsToDecisionText:
    def test_formats_single_call(self) -> None:
        calls = [LLMToolCall(tool_name='read', tool_input={'file': 'x'})]
        text = _native_tool_calls_to_decision_text(calls)
        parsed = json.loads(text)
        assert parsed['tool_name'] == 'read'
        assert parsed['arguments'] == {'file': 'x'}
        assert parsed['type'] == 'tool'

    def test_only_first_call_is_used(self) -> None:
        calls = [
            LLMToolCall(tool_name='first', tool_input={'a': 1}),
            LLMToolCall(tool_name='second', tool_input={'b': 2}),
        ]
        text = _native_tool_calls_to_decision_text(calls)
        parsed = json.loads(text)
        assert parsed['tool_name'] == 'first'


# ─── _adapters.py: gemini safety ────────────────────────────────────────────────


class TestExtractGeminiSafety:
    def test_returns_blocked_when_rating_has_blocked_true(self) -> None:
        response: dict[str, Any] = {
            'candidates': [
                {
                    'finishReason': 'SAFETY',
                    'safetyRatings': [
                        {
                            'category': 'HARM_CATEGORY_HARASSMENT',
                            'probability': 'HIGH',
                            'blocked': True,
                        }
                    ],
                }
            ]
        }
        result = _extract_gemini_safety(response)
        assert result is not None
        assert result.blocked is True
        assert result.category == SafetyCategory.HARASSMENT

    def test_returns_blocked_without_category_when_no_blocked_flag(self) -> None:
        response: dict[str, Any] = {
            'candidates': [
                {
                    'finishReason': 'SAFETY',
                    'safetyRatings': [
                        {
                            'category': 'HARM_CATEGORY_HATE_SPEECH',
                            'probability': 'HIGH',
                        }
                    ],
                }
            ]
        }
        result = _extract_gemini_safety(response)
        assert result is not None
        assert result.blocked is True
        assert result.category is None

    def test_returns_none_when_no_safety_block(self) -> None:
        response: dict[str, Any] = {
            'candidates': [{'finishReason': 'STOP'}]
        }
        assert _extract_gemini_safety(response) is None

    def test_returns_none_when_no_candidates(self) -> None:
        assert _extract_gemini_safety({}) is None

    def test_maps_known_categories(self) -> None:
        for category_key, expected in [
            ('HARM_CATEGORY_HATE_SPEECH', SafetyCategory.HATE_SPEECH),
            ('HARM_CATEGORY_SEXUALLY_EXPLICIT', SafetyCategory.SEXUAL),
            ('HARM_CATEGORY_DANGEROUS_CONTENT', SafetyCategory.DANGEROUS),
        ]:
            response: dict[str, Any] = {
                'candidates': [
                    {
                        'finishReason': 'SAFETY',
                        'safetyRatings': [
                            {
                                'category': category_key,
                                'probability': 'HIGH',
                                'blocked': True,
                            }
                        ],
                    }
                ]
            }
            result = _extract_gemini_safety(response)
            assert result is not None
            assert result.category == expected

    def test_returns_other_for_unknown_category(self) -> None:
        response: dict[str, Any] = {
            'candidates': [
                {
                    'finishReason': 'SAFETY',
                    'safetyRatings': [
                        {
                            'category': 'HARM_CATEGORY_UNKNOWN',
                            'probability': 'HIGH',
                            'blocked': True,
                        }
                    ],
                }
            ]
        }
        result = _extract_gemini_safety(response)
        assert result is not None
        assert result.category == SafetyCategory.OTHER


class TestExtractGeminiStreamText:
    def test_extracts_text_from_part(self) -> None:
        parsed: dict[str, Any] = {
            'candidates': [
                {'content': {'parts': [{'text': 'Hello'}]}}
            ]
        }
        assert _extract_gemini_stream_text(parsed) == 'Hello'

    def test_empty_when_no_candidates(self) -> None:
        assert _extract_gemini_stream_text({}) == ''

    def test_empty_when_no_parts(self) -> None:
        parsed: dict[str, Any] = {
            'candidates': [{'content': {'parts': []}}]
        }
        assert _extract_gemini_stream_text(parsed) == ''

    def test_concatenates_multiple_text_parts(self) -> None:
        parsed: dict[str, Any] = {
            'candidates': [
                {
                    'content': {
                        'parts': [{'text': 'Hello'}, {'text': ' World'}]
                    }
                }
            ]
        }
        assert _extract_gemini_stream_text(parsed) == 'Hello World'


# ─── _adapters.py: provider extra headers ──────────────────────────────────────


class TestProviderExtraHeaders:
    def test_workers_ai_extra_headers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            'WORKERS_AI_EXTRA_HEADERS',
            json.dumps({'Authorization': 'Bearer tok', 'X-Custom': 'val'}),
        )
        headers = _provider_extra_headers('workers-ai')
        assert headers.get('Authorization') == 'Bearer tok'
        assert headers.get('X-Custom') == 'val'

    def test_unknown_provider_returns_empty(self) -> None:
        assert _provider_extra_headers('openai') == {}

    def test_no_env_var_returns_empty(self) -> None:
        assert _provider_extra_headers('workers-ai') == {}

    def test_invalid_json_raises(self) -> None:
        import os

        os.environ['WORKERS_AI_EXTRA_HEADERS'] = '{bad json'
        try:
            with pytest.raises(LLMHTTPError):
                _provider_extra_headers('workers-ai')
        finally:
            del os.environ['WORKERS_AI_EXTRA_HEADERS']


# ─── _config.py: cost estimation ────────────────────────────────────────────────


class TestEstimateCost:
    def test_known_provider_returns_cost(self) -> None:
        cost = _estimate_cost('openai', 'gpt-4o', 1000, 500)
        assert isinstance(cost, float)
        assert cost > 0

    def test_unknown_provider_uses_default_rate(self) -> None:
        cost = _estimate_cost('unknown-provider', 'model', 1000, 500)
        assert cost > 0

    def test_zero_tokens_costs_nothing(self) -> None:
        cost = _estimate_cost('openai', 'gpt-4o', 0, 0)
        assert cost == 0.0


# ─── _extract.py: openai content edge cases ────────────────────────────────────


class TestExtractOpenaiContentEdgeCases:
    def test_top_level_output_text_requires_choices(self) -> None:
        with pytest.raises(LLMResponseFormatError):
            _extract_openai_content('openai', {'output_text': 'direct text'})

    def test_output_text_fallback_when_choices_have_no_text(self) -> None:
        response: dict[str, Any] = {
            'choices': [{'message': {'content': ''}}],
            'output_text': 'fallback text',
        }
        assert _extract_openai_content('openai', response) == 'fallback text'

    def test_nested_result_fallback(self) -> None:
        response: dict[str, Any] = {
            'choices': [{'message': {'content': ''}}],
            'result': {'output_text': 'result text'},
        }
        assert _extract_openai_content('openai', response) == 'result text'

    def test_nested_result_content_fallback(self) -> None:
        response: dict[str, Any] = {
            'choices': [{'message': {'content': ''}}],
            'result': {'content': 'nested content'},
        }
        assert _extract_openai_content('openai', response) == 'nested content'


# ─── _transport.py ─────────────────────────────────────────────────────────────


class TestBuildSslContextFromEnv:
    def test_returns_none_without_env_vars(self) -> None:
        assert build_ssl_context_from_env() is None

    def test_ssl_cert_file_returns_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('SSL_CERT_FILE', '/nonexistent/cert.pem')
        with patch('ssl.create_default_context') as mock_ctx:
            mock_ctx.return_value = mock_ctx
            ctx = build_ssl_context_from_env()
            assert ctx is not None
            mock_ctx.load_verify_locations.assert_called_once_with(
                cafile='/nonexistent/cert.pem'
            )

    def test_requests_ca_bundle_returns_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('REQUESTS_CA_BUNDLE', '/some/ca.pem')
        with patch('ssl.create_default_context') as mock_ctx:
            mock_ctx.return_value = mock_ctx
            ctx = build_ssl_context_from_env()
            assert ctx is not None
            mock_ctx.load_verify_locations.assert_called_once_with(
                cafile='/some/ca.pem'
            )

    def test_client_cert_without_ca_returns_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('TEAAGENT_TLS_CLIENT_CERT', '/some/cert.pem')
        with patch('ssl.create_default_context') as mock_ctx:
            mock_ctx.return_value = mock_ctx
            ctx = build_ssl_context_from_env()
            assert ctx is not None
            mock_ctx.load_cert_chain.assert_called_once_with(
                certfile='/some/cert.pem'
            )

    def test_client_cert_and_key_returns_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('TEAAGENT_TLS_CLIENT_CERT', '/some/cert.pem')
        monkeypatch.setenv('TEAAGENT_TLS_CLIENT_KEY', '/some/key.pem')
        with patch('ssl.create_default_context') as mock_ctx:
            mock_ctx.return_value = mock_ctx
            ctx = build_ssl_context_from_env()
            assert ctx is not None
            mock_ctx.load_cert_chain.assert_called_once_with(
                certfile='/some/cert.pem', keyfile='/some/key.pem'
            )

    def test_requests_ca_bundle_preferred_over_ssl_cert_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('REQUESTS_CA_BUNDLE', '/ca.pem')
        monkeypatch.setenv('SSL_CERT_FILE', '/ssl.pem')
        with patch('ssl.create_default_context') as mock_ctx:
            mock_ctx.return_value = mock_ctx
            build_ssl_context_from_env()
            mock_ctx.load_verify_locations.assert_called_once_with(cafile='/ca.pem')


# ─── _retry.py: edge cases ──────────────────────────────────────────────────────


class TestCallWithRetryEdgeCases:
    def test_raises_on_non_transient_status(self) -> None:
        from teaagent.llm._retry import DEFAULT_RETRY_CONFIG

        def _transport_fn() -> dict[str, Any]:
            raise LLMHTTPError('bad request', status_code=400)

        with pytest.raises(LLMHTTPError, match='bad request'):
            _call_with_retry('test', _transport_fn, DEFAULT_RETRY_CONFIG)

    def test_raises_on_network_error(self) -> None:
        from teaagent.llm._retry import DEFAULT_RETRY_CONFIG

        def _transport_fn() -> dict[str, Any]:
            raise LLMHTTPError('connection failed', status_code=0)

        with pytest.raises(LLMHTTPError, match='connection failed'):
            _call_with_retry('test', _transport_fn, DEFAULT_RETRY_CONFIG)
