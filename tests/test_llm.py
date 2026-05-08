from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stdout
import unittest
from unittest.mock import patch

from teaagent import LLMMessage, LLMRequest, available_providers, check_llm_configuration, create_llm_adapter
from teaagent.cli import main


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post_json(self, url, headers, payload, *, timeout):
        self.calls.append({"url": url, "headers": headers, "payload": payload, "timeout": timeout})
        return self.response


class LLMAdapterTests(unittest.TestCase):
    def test_available_providers_include_requested_adapters(self) -> None:
        self.assertEqual(
            available_providers(),
            ["claude", "gemini", "gpt", "opencodezen-go", "openrouter"],
        )

    def test_gpt_adapter_uses_openai_chat_completions_shape(self) -> None:
        transport = FakeTransport({"choices": [{"message": {"content": "ok"}}]})
        with patch.dict(os.environ, {"OPENAI_API_KEY": "key"}, clear=True):
            adapter = create_llm_adapter("gpt", transport=transport, model="gpt-test")
            response = adapter.complete(LLMRequest(system="sys", messages=[LLMMessage("user", "hi")]))

        self.assertEqual(response.content, "ok")
        call = transport.calls[0]
        self.assertEqual(call["url"], "https://api.openai.com/v1/chat/completions")
        self.assertEqual(call["headers"]["authorization"], "Bearer key")
        self.assertEqual(call["payload"]["messages"][0], {"role": "system", "content": "sys"})

    def test_openrouter_adapter_uses_openai_compatible_shape(self) -> None:
        transport = FakeTransport({"choices": [{"message": {"content": "ok"}}]})
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "key", "OPENROUTER_APP_TITLE": "TeaAgent"}, clear=True):
            adapter = create_llm_adapter("openrouter", transport=transport)
            adapter.complete(LLMRequest(messages=[LLMMessage("user", "hi")]))

        self.assertEqual(transport.calls[0]["url"], "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(transport.calls[0]["headers"]["X-Title"], "TeaAgent")

    def test_claude_adapter_uses_messages_api_shape(self) -> None:
        transport = FakeTransport({"content": [{"type": "text", "text": "ok"}]})
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key"}, clear=True):
            adapter = create_llm_adapter("claude", transport=transport)
            response = adapter.complete(LLMRequest(system="sys", messages=[LLMMessage("user", "hi")]))

        self.assertEqual(response.content, "ok")
        call = transport.calls[0]
        self.assertEqual(call["url"], "https://api.anthropic.com/v1/messages")
        self.assertEqual(call["headers"]["x-api-key"], "key")
        self.assertEqual(call["payload"]["system"], "sys")

    def test_gemini_adapter_uses_generate_content_shape(self) -> None:
        transport = FakeTransport({"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})
        with patch.dict(os.environ, {"GEMINI_API_KEY": "key"}, clear=True):
            adapter = create_llm_adapter("gemini", transport=transport, model="gemini-test")
            response = adapter.complete(LLMRequest(messages=[LLMMessage("user", "hi")]))

        self.assertEqual(response.content, "ok")
        self.assertEqual(
            transport.calls[0]["url"],
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent?key=key",
        )
        self.assertEqual(transport.calls[0]["payload"]["contents"][0]["parts"][0]["text"], "hi")

    def test_opencodezen_go_is_openai_compatible_and_configurable(self) -> None:
        transport = FakeTransport({"choices": [{"message": {"content": "ok"}}]})
        with patch.dict(os.environ, {"OPENCODEZEN_API_KEY": "key", "OPENCODEZEN_BASE_URL": "https://local.test/v1"}, clear=True):
            adapter = create_llm_adapter("opencodezen-go", transport=transport)
            response = adapter.complete(LLMRequest(messages=[LLMMessage("user", "hi")]))

        self.assertEqual(response.content, "ok")
        self.assertEqual(transport.calls[0]["url"], "https://local.test/v1/chat/completions")

    def test_configuration_check_reports_missing_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            ok, message = check_llm_configuration("gpt")

        self.assertFalse(ok)
        self.assertIn("OPENAI_API_KEY", message)

    def test_cli_lists_model_providers(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["model", "providers"])

        self.assertEqual(exit_code, 0)
        self.assertIn("claude", json.loads(output.getvalue()))


if __name__ == "__main__":
    unittest.main()
