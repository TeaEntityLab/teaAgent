"""Tests for expanded provider support."""

from __future__ import annotations

import unittest

from teaagent.llm._config import (
    PROVIDER_CONFIGS,
    available_providers,
    create_llm_adapter,
)


class TestProviderExpansion(unittest.TestCase):
    def test_new_providers_registered(self) -> None:
        providers = available_providers()
        self.assertIn('mistral', providers)
        self.assertIn('deepseek', providers)
        self.assertIn('grok', providers)
        self.assertIn('workers-ai', providers)
        self.assertIn('aigateway', providers)

    def test_mistral_config(self) -> None:
        config = PROVIDER_CONFIGS['mistral']
        self.assertEqual(config.api_key_env, 'MISTRAL_API_KEY')
        self.assertEqual(config.default_model, 'mistral-large-latest')
        self.assertEqual(config.base_url, 'https://api.mistral.ai/v1')

    def test_deepseek_config(self) -> None:
        config = PROVIDER_CONFIGS['deepseek']
        self.assertEqual(config.api_key_env, 'DEEPSEEK_API_KEY')
        self.assertEqual(config.default_model, 'deepseek-chat')
        self.assertEqual(config.base_url, 'https://api.deepseek.com/v1')

    def test_grok_config(self) -> None:
        config = PROVIDER_CONFIGS['grok']
        self.assertEqual(config.api_key_env, 'XAI_API_KEY')
        self.assertEqual(config.default_model, 'grok-3-latest')
        self.assertEqual(config.base_url, 'https://api.x.ai/v1')

    def test_new_providers_use_openai_compatible_adapter(self) -> None:
        from teaagent.llm._adapters import OpenAICompatibleAdapter

        for provider in ('mistral', 'deepseek', 'grok', 'workers-ai', 'aigateway'):
            adapter = create_llm_adapter(provider)
            self.assertIsInstance(
                adapter,
                OpenAICompatibleAdapter,
                f'{provider} should use OpenAICompatibleAdapter',
            )

    def test_total_provider_count(self) -> None:
        """Verify we have at least 12 providers now."""
        self.assertGreaterEqual(len(available_providers()), 12)


if __name__ == '__main__':
    unittest.main()
