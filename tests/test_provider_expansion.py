"""Tests for expanded provider support."""

from __future__ import annotations

from teaagent.llm._config import (
    PROVIDER_CONFIGS,
    available_providers,
    create_llm_adapter,
)


def test_new_providers_registered() -> None:
    providers = available_providers()
    assert 'mistral' in providers
    assert 'deepseek' in providers
    assert 'grok' in providers
    assert 'workers-ai' in providers
    assert 'aigateway' in providers
    assert 'opencodezen' in providers


def test_mistral_config() -> None:
    config = PROVIDER_CONFIGS['mistral']
    assert config.api_key_env == 'MISTRAL_API_KEY'
    assert config.default_model == 'mistral-large-latest'
    assert config.base_url == 'https://api.mistral.ai/v1'


def test_deepseek_config() -> None:
    config = PROVIDER_CONFIGS['deepseek']
    assert config.api_key_env == 'DEEPSEEK_API_KEY'
    assert config.default_model == 'deepseek-chat'
    assert config.base_url == 'https://api.deepseek.com/v1'


def test_grok_config() -> None:
    config = PROVIDER_CONFIGS['grok']
    assert config.api_key_env == 'XAI_API_KEY'
    assert config.default_model == 'grok-3-latest'
    assert config.base_url == 'https://api.x.ai/v1'


def test_new_providers_use_openai_compatible_adapter() -> None:
    from teaagent.llm._adapters import OpenAICompatibleAdapter

    for provider in (
        'mistral',
        'deepseek',
        'grok',
        'workers-ai',
        'aigateway',
        'opencodezen',
    ):
        adapter = create_llm_adapter(provider)
        assert isinstance(
            adapter,
            OpenAICompatibleAdapter,
        ), f'{provider} should use OpenAICompatibleAdapter'


def test_total_provider_count() -> None:
    """Verify we have at least 13 providers now."""
    assert len(available_providers()) >= 13
