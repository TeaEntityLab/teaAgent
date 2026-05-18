"""Additional tests for low-coverage modules: llm, telemetry, code_mode."""

from __future__ import annotations

import importlib.util
import unittest
from unittest.mock import MagicMock, patch

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


class TestLLMRetryConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = LLMRetryConfig()
        self.assertEqual(cfg.max_retries, 3)
        self.assertEqual(cfg.base_delay_seconds, 1.0)
        self.assertEqual(cfg.max_delay_seconds, 30.0)
        self.assertIn(429, cfg.retry_on_status)

    def test_delay_increases_with_attempt(self) -> None:
        cfg = LLMRetryConfig(base_delay_seconds=1.0)
        d0 = cfg.delay(0)
        d1 = cfg.delay(1)
        self.assertGreater(d1, d0)

    def test_delay_capped_at_max(self) -> None:
        cfg = LLMRetryConfig(base_delay_seconds=100.0, max_delay_seconds=5.0)
        delay = cfg.delay(10)
        self.assertLessEqual(delay, 5.0)


class TestCallWithRetry(unittest.TestCase):
    def test_success_on_first_try(self) -> None:
        fn = MagicMock(return_value={'ok': True})
        result = _call_with_retry('test', fn, LLMRetryConfig(max_retries=3))
        self.assertEqual(result, {'ok': True})
        fn.assert_called_once()

    def test_retries_on_transient_error(self) -> None:
        fn = MagicMock()
        fn.side_effect = [
            LLMHTTPError(status_code=500, message='server error'),
            {'ok': True},
        ]
        with patch('teaagent.llm._retry.time.sleep', return_value=None):
            result = _call_with_retry('test', fn, LLMRetryConfig(max_retries=3))
        self.assertEqual(result, {'ok': True})
        self.assertEqual(fn.call_count, 2)

    def test_retries_on_429(self) -> None:
        fn = MagicMock()
        fn.side_effect = [
            LLMHTTPError(status_code=429, message='rate limited'),
            {'ok': True},
        ]
        with patch('teaagent.llm._retry.time.sleep', return_value=None):
            result = _call_with_retry('test', fn, LLMRetryConfig(max_retries=3))
        self.assertEqual(result, {'ok': True})

    def test_raises_on_non_transient_error(self) -> None:
        fn = MagicMock(side_effect=LLMHTTPError(status_code=400, message='bad request'))
        with self.assertRaises(LLMHTTPError):
            _call_with_retry('test', fn, LLMRetryConfig(max_retries=3))

    def test_raises_after_max_retries(self) -> None:
        fn = MagicMock(side_effect=LLMHTTPError(status_code=500, message='error'))
        with (
            patch('teaagent.llm._retry.time.sleep', return_value=None),
            self.assertRaises(LLMHTTPError),
        ):
            _call_with_retry('test', fn, LLMRetryConfig(max_retries=1))

    def test_retries_on_network_error(self) -> None:
        fn = MagicMock()
        fn.side_effect = [
            LLMHTTPError(status_code=0, message='network error'),
            {'ok': True},
        ]
        with patch('teaagent.llm._retry.time.sleep', return_value=None):
            result = _call_with_retry('test', fn, LLMRetryConfig(max_retries=3))
        self.assertEqual(result, {'ok': True})


# ---------------------------------------------------------------------------
# LLM Extract Tests
# ---------------------------------------------------------------------------


class TestExtractOpenAIContent(unittest.TestCase):
    def test_valid_response(self) -> None:
        response = {'choices': [{'message': {'content': 'hello'}}]}
        result = _extract_openai_content('openai', response)
        self.assertEqual(result, 'hello')

    def test_missing_choices(self) -> None:
        with self.assertRaises(LLMResponseFormatError) as ctx:
            _extract_openai_content('openai', {})
        self.assertIn('missing choices', str(ctx.exception))

    def test_empty_choices(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _extract_openai_content('openai', {'choices': []})

    def test_choice_not_dict(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _extract_openai_content('openai', {'choices': ['not a dict']})

    def test_missing_message(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _extract_openai_content('openai', {'choices': [{}]})

    def test_message_not_dict(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _extract_openai_content('openai', {'choices': [{'message': 'not dict'}]})

    def test_missing_content(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _extract_openai_content('openai', {'choices': [{'message': {}}]})

    def test_empty_content(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _extract_openai_content(
                'openai', {'choices': [{'message': {'content': ''}}]}
            )

    def test_content_not_string(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _extract_openai_content(
                'openai', {'choices': [{'message': {'content': 123}}]}
            )


class TestFirstChoiceDelta(unittest.TestCase):
    def test_valid_delta(self) -> None:
        response = {'choices': [{'delta': {'content': 'hi'}}]}
        result = _first_choice_delta('openai', response)
        self.assertEqual(result['content'], 'hi')

    def test_missing_choices(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _first_choice_delta('openai', {})

    def test_empty_choices(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _first_choice_delta('openai', {'choices': []})

    def test_choice_not_dict(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _first_choice_delta('openai', {'choices': ['bad']})

    def test_delta_not_dict(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _first_choice_delta('openai', {'choices': [{'delta': 'bad'}]})

    def test_default_empty_delta(self) -> None:
        response = {'choices': [{}]}
        result = _first_choice_delta('openai', response)
        self.assertEqual(result, {})


class TestExtractClaudeContent(unittest.TestCase):
    def test_valid_response(self) -> None:
        response = {'content': [{'type': 'text', 'text': 'hello'}]}
        result = _extract_claude_content(response)
        self.assertEqual(result, 'hello')

    def test_multiple_text_blocks(self) -> None:
        response = {
            'content': [
                {'type': 'text', 'text': 'hello '},
                {'type': 'text', 'text': 'world'},
            ]
        }
        result = _extract_claude_content(response)
        self.assertEqual(result, 'hello world')

    def test_missing_content_blocks(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _extract_claude_content({})

    def test_content_not_list(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _extract_claude_content({'content': 'not a list'})

    def test_no_text_content(self) -> None:
        response = {'content': [{'type': 'tool_use', 'name': 'x'}]}
        with self.assertRaises(LLMResponseFormatError):
            _extract_claude_content(response)


class TestExtractGeminiContent(unittest.TestCase):
    def test_valid_response(self) -> None:
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
        self.assertEqual(result, 'hello')

    def test_multiple_parts(self) -> None:
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
        self.assertEqual(result, 'hello world')

    def test_missing_candidates(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _extract_gemini_content({})

    def test_empty_candidates(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _extract_gemini_content({'candidates': []})

    def test_candidate_not_dict(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _extract_gemini_content({'candidates': ['bad']})

    def test_missing_content(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _extract_gemini_content({'candidates': [{}]})

    def test_content_not_dict(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _extract_gemini_content({'candidates': [{'content': 'bad'}]})

    def test_missing_parts(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _extract_gemini_content({'candidates': [{'content': {}}]})

    def test_parts_not_list(self) -> None:
        with self.assertRaises(LLMResponseFormatError):
            _extract_gemini_content({'candidates': [{'content': {'parts': 'bad'}}]})

    def test_no_text(self) -> None:
        response = {
            'candidates': [
                {
                    'content': {
                        'parts': [{'type': 'function_call'}],
                    }
                }
            ]
        }
        with self.assertRaises(LLMResponseFormatError):
            _extract_gemini_content(response)


class TestRaiseProviderError(unittest.TestCase):
    def test_dict_error(self) -> None:
        with self.assertRaises(LLMProviderError) as ctx:
            _raise_provider_error('openai', {'error': {'message': 'bad'}})
        self.assertIn('bad', str(ctx.exception))

    def test_dict_error_with_status(self) -> None:
        with self.assertRaises(LLMProviderError) as ctx:
            _raise_provider_error('openai', {'error': {'status': 'FAILED'}})
        self.assertIn('FAILED', str(ctx.exception))

    def test_dict_error_fallback(self) -> None:
        with self.assertRaises(LLMProviderError) as ctx:
            _raise_provider_error('openai', {'error': {'code': 500}})
        self.assertIn('500', str(ctx.exception))

    def test_string_error(self) -> None:
        with self.assertRaises(LLMProviderError) as ctx:
            _raise_provider_error('openai', {'error': 'something went wrong'})
        self.assertIn('something went wrong', str(ctx.exception))

    def test_prompt_blocked(self) -> None:
        with self.assertRaises(LLMProviderError) as ctx:
            _raise_provider_error(
                'gemini',
                {'promptFeedback': {'blockReason': 'SAFETY'}},
            )
        self.assertIn('SAFETY', str(ctx.exception))

    def test_no_error(self) -> None:
        _raise_provider_error('openai', {'choices': []})


# ---------------------------------------------------------------------------
# Telemetry Transport Tests
# ---------------------------------------------------------------------------

HAS_OTEL = importlib.util.find_spec('opentelemetry') is not None


@unittest.skipUnless(HAS_OTEL, 'opentelemetry not installed')
class TestTracingHTTPTransport(unittest.TestCase):
    def test_success_creates_span(self) -> None:
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

        self.assertEqual(result, {'result': 'ok'})
        inner.post_json.assert_called_once()
        mock_span.set_attribute.assert_any_call('http.url', 'http://example.com')
        mock_span.set_attribute.assert_any_call('http.method', 'POST')
        mock_span.set_status.assert_called()

    def test_error_sets_error_status(self) -> None:
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
        with self.assertRaises(RuntimeError):
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


class TestChildProcessCodeModeBackend(unittest.TestCase):
    def test_execute_simple_code(self) -> None:
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
        self.assertEqual(result.variables['x'], 3)

    def test_execute_with_inputs(self) -> None:
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
        self.assertEqual(result.variables['result'], 30)

    def test_execute_ignores_private_vars(self) -> None:
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
        self.assertNotIn('_private', result.variables)
        self.assertEqual(result.variables['public'], 2)

    def test_execute_timeout(self) -> None:
        backend = ChildProcessCodeModeBackend()
        sandbox = CodeModeSandbox(
            timeout_seconds=1,
            cpu_seconds=5,
            memory_bytes=100_000_000,
        )
        with self.assertRaises(UnsafeCodeError) as ctx:
            backend.execute(
                'while True: pass',
                inputs={},
                sandbox=sandbox,
            )
        self.assertIn('timed out', str(ctx.exception))

    def test_execute_error(self) -> None:
        backend = ChildProcessCodeModeBackend()
        sandbox = CodeModeSandbox(
            timeout_seconds=10,
            cpu_seconds=5,
            memory_bytes=100_000_000,
        )
        with self.assertRaises(UnsafeCodeError):
            backend.execute(
                'raise ValueError("test error")',
                inputs={},
                sandbox=sandbox,
            )

    def test_execute_rejects_non_serializable(self) -> None:
        backend = ChildProcessCodeModeBackend()
        sandbox = CodeModeSandbox(
            timeout_seconds=10,
            cpu_seconds=5,
            memory_bytes=100_000_000,
        )
        with self.assertRaises(UnsafeCodeError):
            backend.execute(
                'import os; x = os',
                inputs={},
                sandbox=sandbox,
            )


class TestApplyResourceLimits(unittest.TestCase):
    def test_no_resource_module(self) -> None:
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
