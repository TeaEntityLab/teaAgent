"""Additional tests for low-coverage modules: llm, telemetry, code_mode."""

from __future__ import annotations

import importlib.util
from unittest.mock import MagicMock, patch

import pytest

from teaagent.code_mode._child_process import (
    ChildProcessCodeModeBackend,
    _apply_resource_limits,
)
from teaagent.code_mode._types import CodeModeSandbox
from teaagent.code_mode._validation import UnsafeCodeError
from teaagent.llm._extract import (
    _extract_claude_content,
    _extract_gemini_content,
    _extract_openai_content,
    _first_choice_delta,
    _raise_provider_error,
)
from teaagent.llm._retry import LLMRetryConfig, _call_with_retry
from teaagent.llm._types import LLMHTTPError, LLMProviderError, LLMResponseFormatError
from teaagent.telemetry._transport import TracingHTTPTransport

# ---------------------------------------------------------------------------
# LLM Retry Tests
# ---------------------------------------------------------------------------


def test_defaults() -> None:
    cfg = LLMRetryConfig()
    assert cfg.max_retries == 3
    assert cfg.base_delay_seconds == 1.0
    assert cfg.max_delay_seconds == 30.0
    assert 429 in cfg.retry_on_status


def test_delay_increases_with_attempt() -> None:
    cfg = LLMRetryConfig(base_delay_seconds=1.0)
    d0 = cfg.delay(0)
    d1 = cfg.delay(1)
    assert d1 > d0


def test_delay_capped_at_max() -> None:
    cfg = LLMRetryConfig(base_delay_seconds=100.0, max_delay_seconds=5.0)
    delay = cfg.delay(10)
    assert delay <= 5.0


def test_success_on_first_try() -> None:
    fn = MagicMock(return_value={'ok': True})
    result = _call_with_retry('test', fn, LLMRetryConfig(max_retries=3))
    assert result == {'ok': True}
    fn.assert_called_once()


def test_retries_on_transient_error() -> None:
    fn = MagicMock()
    fn.side_effect = [
        LLMHTTPError(status_code=500, message='server error'),
        {'ok': True},
    ]
    with patch('teaagent.llm._retry.time.sleep', return_value=None):
        result = _call_with_retry('test', fn, LLMRetryConfig(max_retries=3))
    assert result == {'ok': True}
    assert fn.call_count == 2


def test_retries_on_429() -> None:
    fn = MagicMock()
    fn.side_effect = [
        LLMHTTPError(status_code=429, message='rate limited'),
        {'ok': True},
    ]
    with patch('teaagent.llm._retry.time.sleep', return_value=None):
        result = _call_with_retry('test', fn, LLMRetryConfig(max_retries=3))
    assert result == {'ok': True}


def test_raises_on_non_transient_error() -> None:
    fn = MagicMock(side_effect=LLMHTTPError(status_code=400, message='bad request'))
    with pytest.raises(LLMHTTPError):
        _call_with_retry('test', fn, LLMRetryConfig(max_retries=3))


def test_raises_after_max_retries() -> None:
    fn = MagicMock(side_effect=LLMHTTPError(status_code=500, message='error'))
    with (
        patch('teaagent.llm._retry.time.sleep', return_value=None),
        pytest.raises(LLMHTTPError),
    ):
        _call_with_retry('test', fn, LLMRetryConfig(max_retries=1))


def test_retries_on_network_error() -> None:
    fn = MagicMock()
    fn.side_effect = [
        LLMHTTPError(status_code=0, message='network error'),
        {'ok': True},
    ]
    with patch('teaagent.llm._retry.time.sleep', return_value=None):
        result = _call_with_retry('test', fn, LLMRetryConfig(max_retries=3))
    assert result == {'ok': True}


# ---------------------------------------------------------------------------
# LLM Extract Tests
# ---------------------------------------------------------------------------


def test_valid_response() -> None:
    response = {'choices': [{'message': {'content': 'hello'}}]}
    result = _extract_openai_content('openai', response)
    assert result == 'hello'


def test_missing_choices() -> None:
    with pytest.raises(LLMResponseFormatError) as ctx:
        _extract_openai_content('openai', {})
    assert 'missing choices' in str(ctx.value)


def test_empty_choices() -> None:
    with pytest.raises(LLMResponseFormatError):
        _extract_openai_content('openai', {'choices': []})


def test_choice_not_dict() -> None:
    with pytest.raises(LLMResponseFormatError):
        _extract_openai_content('openai', {'choices': ['not a dict']})


def test_missing_message() -> None:
    with pytest.raises(LLMResponseFormatError):
        _extract_openai_content('openai', {'choices': [{}]})


def test_message_not_dict() -> None:
    with pytest.raises(LLMResponseFormatError):
        _extract_openai_content('openai', {'choices': [{'message': 'not dict'}]})


def test_missing_content() -> None:
    with pytest.raises(LLMResponseFormatError):
        _extract_openai_content('openai', {'choices': [{'message': {}}]})


def test_empty_content() -> None:
    with pytest.raises(LLMResponseFormatError):
        _extract_openai_content('openai', {'choices': [{'message': {'content': ''}}]})


def test_content_not_string() -> None:
    with pytest.raises(LLMResponseFormatError):
        _extract_openai_content('openai', {'choices': [{'message': {'content': 123}}]})


def test_valid_delta() -> None:
    response = {'choices': [{'delta': {'content': 'hi'}}]}
    result = _first_choice_delta('openai', response)
    assert result['content'] == 'hi'


def test_missing_choices_delta() -> None:
    with pytest.raises(LLMResponseFormatError):
        _first_choice_delta('openai', {})


def test_empty_choices_delta() -> None:
    with pytest.raises(LLMResponseFormatError):
        _first_choice_delta('openai', {'choices': []})


def test_choice_not_dict_delta() -> None:
    with pytest.raises(LLMResponseFormatError):
        _first_choice_delta('openai', {'choices': ['bad']})


def test_delta_not_dict() -> None:
    with pytest.raises(LLMResponseFormatError):
        _first_choice_delta('openai', {'choices': [{'delta': 'bad'}]})


def test_default_empty_delta() -> None:
    response = {'choices': [{}]}
    result = _first_choice_delta('openai', response)
    assert result == {}


def test_valid_response_claude() -> None:
    response = {'content': [{'type': 'text', 'text': 'hello'}]}
    result = _extract_claude_content(response)
    assert result == 'hello'


def test_multiple_text_blocks() -> None:
    response = {
        'content': [
            {'type': 'text', 'text': 'hello '},
            {'type': 'text', 'text': 'world'},
        ]
    }
    result = _extract_claude_content(response)
    assert result == 'hello world'


def test_missing_content_blocks() -> None:
    with pytest.raises(LLMResponseFormatError):
        _extract_claude_content({})


def test_content_not_list() -> None:
    with pytest.raises(LLMResponseFormatError):
        _extract_claude_content({'content': 'not a list'})


def test_no_text_content() -> None:
    response = {'content': [{'type': 'tool_use', 'name': 'x'}]}
    with pytest.raises(LLMResponseFormatError):
        _extract_claude_content(response)


def test_valid_response_gemini() -> None:
    response = {
        'candidates': [
            {
                'content': {
                    'parts': [{'text': 'hello'}],
                }
            }
        ]
    }
    result = _extract_gemini_content(response)
    assert result == 'hello'


def test_multiple_parts() -> None:
    response = {
        'candidates': [
            {
                'content': {
                    'parts': [{'text': 'hello '}, {'text': 'world'}],
                }
            }
        ]
    }
    result = _extract_gemini_content(response)
    assert result == 'hello world'


def test_missing_candidates() -> None:
    with pytest.raises(LLMResponseFormatError):
        _extract_gemini_content({})


def test_empty_candidates() -> None:
    with pytest.raises(LLMResponseFormatError):
        _extract_gemini_content({'candidates': []})


def test_candidate_not_dict() -> None:
    with pytest.raises(LLMResponseFormatError):
        _extract_gemini_content({'candidates': ['bad']})


def test_missing_content_gemini() -> None:
    with pytest.raises(LLMResponseFormatError):
        _extract_gemini_content({'candidates': [{}]})


def test_content_not_dict_gemini() -> None:
    with pytest.raises(LLMResponseFormatError):
        _extract_gemini_content({'candidates': [{'content': 'bad'}]})


def test_missing_parts() -> None:
    with pytest.raises(LLMResponseFormatError):
        _extract_gemini_content({'candidates': [{'content': {}}]})


def test_parts_not_list() -> None:
    with pytest.raises(LLMResponseFormatError):
        _extract_gemini_content({'candidates': [{'content': {'parts': 'bad'}}]})


def test_no_text() -> None:
    response = {
        'candidates': [
            {
                'content': {
                    'parts': [{'type': 'function_call'}],
                }
            }
        ]
    }
    with pytest.raises(LLMResponseFormatError):
        _extract_gemini_content(response)


def test_dict_error() -> None:
    with pytest.raises(LLMProviderError) as ctx:
        _raise_provider_error('openai', {'error': {'message': 'bad'}})
    assert 'bad' in str(ctx.value)


def test_dict_error_with_status() -> None:
    with pytest.raises(LLMProviderError) as ctx:
        _raise_provider_error('openai', {'error': {'status': 'FAILED'}})
    assert 'FAILED' in str(ctx.value)


def test_dict_error_fallback() -> None:
    with pytest.raises(LLMProviderError) as ctx:
        _raise_provider_error('openai', {'error': {'code': 500}})
    assert '500' in str(ctx.value)


def test_string_error() -> None:
    with pytest.raises(LLMProviderError) as ctx:
        _raise_provider_error('openai', {'error': 'something went wrong'})
    assert 'something went wrong' in str(ctx.value)


def test_prompt_blocked() -> None:
    with pytest.raises(LLMProviderError) as ctx:
        _raise_provider_error(
            'gemini',
            {'promptFeedback': {'blockReason': 'SAFETY'}},
        )
    assert 'SAFETY' in str(ctx.value)


def test_no_error() -> None:
    _raise_provider_error('openai', {'choices': []})


# ---------------------------------------------------------------------------
# Telemetry Transport Tests
# ---------------------------------------------------------------------------

HAS_OTEL = importlib.util.find_spec('opentelemetry') is not None


@pytest.mark.skipif(not HAS_OTEL, reason='opentelemetry not installed')
def test_success_creates_span() -> None:
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
        return_value=mock_span
    )
    mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
        return_value=False
    )

    inner = MagicMock()
    inner.post_json.return_value = {'result': 'ok'}

    transport = TracingHTTPTransport(inner, mock_tracer)
    result = transport.post_json(
        'http://example.com',
        {'Authorization': 'Bearer x'},
        {'prompt': 'hello'},
        timeout=30,
    )

    assert result == {'result': 'ok'}
    inner.post_json.assert_called_once()
    mock_span.set_attribute.assert_any_call('http.url', 'http://example.com')
    mock_span.set_attribute.assert_any_call('http.method', 'POST')
    mock_span.set_status.assert_called()


@pytest.mark.skipif(not HAS_OTEL, reason='opentelemetry not installed')
def test_error_sets_error_status() -> None:
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
        return_value=mock_span
    )
    mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
        return_value=False
    )

    inner = MagicMock()
    inner.post_json.side_effect = RuntimeError('connection failed')

    transport = TracingHTTPTransport(inner, mock_tracer)
    with pytest.raises(RuntimeError):
        transport.post_json(
            'http://example.com',
            {},
            {'prompt': 'hello'},
            timeout=30,
        )

    mock_span.set_status.assert_called()
    mock_span.record_exception.assert_called()


# ---------------------------------------------------------------------------
# Code Mode Child Process Tests
# ---------------------------------------------------------------------------


def test_execute_simple_code() -> None:
    backend = ChildProcessCodeModeBackend()
    sandbox = CodeModeSandbox(
        timeout_seconds=10,
        cpu_seconds=5,
        memory_bytes=100_000_000,
    )
    result = backend.execute(
        'x = 1 + 2',
        inputs={},
        sandbox=sandbox,
    )
    assert result.variables['x'] == 3


def test_execute_with_inputs() -> None:
    backend = ChildProcessCodeModeBackend()
    sandbox = CodeModeSandbox(
        timeout_seconds=10,
        cpu_seconds=5,
        memory_bytes=100_000_000,
    )
    result = backend.execute(
        'result = a + b',
        inputs={'a': 10, 'b': 20},
        sandbox=sandbox,
    )
    assert result.variables['result'] == 30


def test_execute_ignores_private_vars() -> None:
    backend = ChildProcessCodeModeBackend()
    sandbox = CodeModeSandbox(
        timeout_seconds=10,
        cpu_seconds=5,
        memory_bytes=100_000_000,
    )
    result = backend.execute(
        '_private = 1\npublic = 2',
        inputs={},
        sandbox=sandbox,
    )
    assert '_private' not in result.variables
    assert result.variables['public'] == 2


def test_execute_timeout() -> None:
    backend = ChildProcessCodeModeBackend()
    sandbox = CodeModeSandbox(
        timeout_seconds=1,
        cpu_seconds=5,
        memory_bytes=100_000_000,
    )
    with pytest.raises(UnsafeCodeError) as ctx:
        backend.execute(
            'while True: pass',
            inputs={},
            sandbox=sandbox,
        )
    assert 'timed out' in str(ctx.value)


def test_execute_error() -> None:
    backend = ChildProcessCodeModeBackend()
    sandbox = CodeModeSandbox(
        timeout_seconds=10,
        cpu_seconds=5,
        memory_bytes=100_000_000,
    )
    with pytest.raises(UnsafeCodeError):
        backend.execute(
            'raise ValueError("test error")',
            inputs={},
            sandbox=sandbox,
        )


def test_execute_rejects_non_serializable() -> None:
    backend = ChildProcessCodeModeBackend()
    sandbox = CodeModeSandbox(
        timeout_seconds=10,
        cpu_seconds=5,
        memory_bytes=100_000_000,
    )
    with pytest.raises(UnsafeCodeError):
        backend.execute(
            'import os; x = os',
            inputs={},
            sandbox=sandbox,
        )


def test_no_resource_module() -> None:
    import teaagent.code_mode._child_process as cp

    original = cp.resource
    cp.resource = None
    try:
        sandbox = CodeModeSandbox(
            timeout_seconds=10,
            cpu_seconds=5,
            memory_bytes=100_000_000,
        )
        _apply_resource_limits(sandbox)
    finally:
        cp.resource = original
