from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from teaagent import (
    LLMMessage,
    LLMRequest,
    available_providers,
    check_llm_configuration,
    create_llm_adapter,
)
from teaagent.cli import main
from teaagent.llm import LLMConfigurationError


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post_json(self, url, headers, payload, *, timeout):
        self.calls.append(
            {'url': url, 'headers': headers, 'payload': payload, 'timeout': timeout}
        )
        return self.response


class FakeStreamingResponse:
    def __init__(self, lines: list[bytes]) -> None:
        self.lines = lines

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        return iter(self.lines)


class LLMAdapterTests(unittest.TestCase):
    def test_available_providers_include_requested_adapters(self) -> None:
        self.assertEqual(
            available_providers(),
            ['claude', 'gemini', 'gpt', 'opencodezen-go', 'openrouter'],
        )

    def test_gpt_adapter_uses_openai_chat_completions_shape(self) -> None:
        transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'key'}, clear=True):
            adapter = create_llm_adapter('gpt', transport=transport, model='gpt-test')
            response = adapter.complete(
                LLMRequest(system='sys', messages=[LLMMessage('user', 'hi')])
            )

        self.assertEqual(response.content, 'ok')
        call = transport.calls[0]
        self.assertEqual(call['url'], 'https://api.openai.com/v1/chat/completions')
        self.assertEqual(call['headers']['authorization'], 'Bearer key')
        self.assertEqual(
            call['payload']['messages'][0], {'role': 'system', 'content': 'sys'}
        )

    def test_openrouter_adapter_uses_openai_compatible_shape(self) -> None:
        transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
        with patch.dict(
            os.environ,
            {'OPENROUTER_API_KEY': 'key', 'OPENROUTER_APP_TITLE': 'TeaAgent'},
            clear=True,
        ):
            adapter = create_llm_adapter('openrouter', transport=transport)
            adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

        self.assertEqual(
            transport.calls[0]['url'], 'https://openrouter.ai/api/v1/chat/completions'
        )
        self.assertEqual(transport.calls[0]['headers']['X-Title'], 'TeaAgent')

    def test_claude_adapter_uses_messages_api_shape(self) -> None:
        transport = FakeTransport({'content': [{'type': 'text', 'text': 'ok'}]})
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'key'}, clear=True):
            adapter = create_llm_adapter('claude', transport=transport)
            response = adapter.complete(
                LLMRequest(system='sys', messages=[LLMMessage('user', 'hi')])
            )

        self.assertEqual(response.content, 'ok')
        call = transport.calls[0]
        self.assertEqual(call['url'], 'https://api.anthropic.com/v1/messages')
        self.assertEqual(call['headers']['x-api-key'], 'key')
        self.assertEqual(call['payload']['system'], 'sys')

    def test_gemini_adapter_uses_generate_content_shape(self) -> None:
        transport = FakeTransport(
            {'candidates': [{'content': {'parts': [{'text': 'ok'}]}}]}
        )
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'key'}, clear=True):
            adapter = create_llm_adapter(
                'gemini', transport=transport, model='gemini-test'
            )
            response = adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

        self.assertEqual(response.content, 'ok')
        self.assertEqual(
            transport.calls[0]['url'],
            'https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent?key=key',
        )
        self.assertEqual(
            transport.calls[0]['payload']['contents'][0]['parts'][0]['text'], 'hi'
        )

    def test_opencodezen_go_is_openai_compatible_and_configurable(self) -> None:
        transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
        with patch.dict(
            os.environ,
            {
                'OPENCODEZEN_API_KEY': 'key',
                'OPENCODEZEN_BASE_URL': 'https://local.test/v1',
            },
            clear=True,
        ):
            adapter = create_llm_adapter('opencodezen-go', transport=transport)
            response = adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

        self.assertEqual(response.content, 'ok')
        self.assertEqual(
            transport.calls[0]['url'], 'https://local.test/v1/chat/completions'
        )

    def test_configuration_check_reports_missing_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            ok, message = check_llm_configuration('gpt')

        self.assertFalse(ok)
        self.assertIn('OPENAI_API_KEY', message)

    def test_cli_lists_model_providers(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(['model', 'providers'])

        self.assertEqual(exit_code, 0)
        self.assertIn('claude', json.loads(output.getvalue()))

    def test_unknown_provider_raises_configuration_error(self) -> None:
        with self.assertRaises(LLMConfigurationError) as ctx:
            create_llm_adapter('nonexistent-provider')

        self.assertIn('unknown provider', str(ctx.exception))
        self.assertIn('Available:', str(ctx.exception))

    def test_gemini_adapter_sends_system_instruction(self) -> None:
        transport = FakeTransport(
            {'candidates': [{'content': {'parts': [{'text': 'ok'}]}}]}
        )
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'key'}, clear=True):
            adapter = create_llm_adapter(
                'gemini', transport=transport, model='gemini-test'
            )
            response = adapter.complete(
                LLMRequest(
                    system='You are helpful', messages=[LLMMessage('user', 'hi')]
                )
            )

        self.assertEqual(response.content, 'ok')
        call = transport.calls[0]
        self.assertIn('systemInstruction', call['payload'])
        self.assertEqual(
            call['payload']['systemInstruction']['parts'][0]['text'], 'You are helpful'
        )

    def test_openrouter_with_referrer_header(self) -> None:
        transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
        with patch.dict(
            os.environ,
            {
                'OPENROUTER_API_KEY': 'key',
                'OPENROUTER_HTTP_REFERER': 'https://myapp.com',
            },
            clear=True,
        ):
            adapter = create_llm_adapter('openrouter', transport=transport)
            adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

        self.assertEqual(
            transport.calls[0]['headers']['HTTP-Referer'], 'https://myapp.com'
        )

    def test_openai_streaming_reads_sse_lines_incrementally(self) -> None:
        chunks: list[str] = []
        response = FakeStreamingResponse(
            [
                b'data: {"choices":[{"delta":{"content":"he"}}]}\n',
                b'data: {"choices":[{"delta":{"content":"llo"}}],"usage":{"prompt_tokens":2,"completion_tokens":3}}\n',
                b'data: [DONE]\n',
            ]
        )

        with (
            patch.dict(os.environ, {'OPENAI_API_KEY': 'key'}, clear=True),
            patch('teaagent.llm.urllib_request.urlopen', return_value=response),
        ):
            adapter = create_llm_adapter('gpt', model='gpt-test')
            result = adapter.complete(
                LLMRequest(
                    messages=[LLMMessage('user', 'hi')],
                    stream=True,
                    on_chunk=chunks.append,
                )
            )

        self.assertEqual(chunks, ['he', 'llo'])
        self.assertEqual(result.content, 'hello')
        self.assertEqual(result.input_tokens, 2)
        self.assertEqual(result.output_tokens, 3)


if __name__ == '__main__':
    unittest.main()
