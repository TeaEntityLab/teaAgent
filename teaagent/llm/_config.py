from __future__ import annotations

from typing import Optional

from teaagent.llm._adapters import (
    ClaudeAdapter,
    GeminiAdapter,
    OpenAICompatibleAdapter,
)
from teaagent.llm._types import (
    HTTPTransport,
    LLMAdapter,
    LLMConfigurationError,
    ProviderConfig,
)

PROVIDER_CONFIGS = {
    'claude': ProviderConfig(
        name='claude',
        api_key_env='ANTHROPIC_API_KEY',
        default_model='claude-3-5-sonnet-latest',
        base_url='https://api.anthropic.com/v1',
        base_url_env='ANTHROPIC_BASE_URL',
    ),
    'gpt': ProviderConfig(
        name='gpt',
        api_key_env='OPENAI_API_KEY',
        default_model='gpt-4o-mini',
        base_url='https://api.openai.com/v1',
        base_url_env='OPENAI_BASE_URL',
    ),
    'gemini': ProviderConfig(
        name='gemini',
        api_key_env='GEMINI_API_KEY',
        default_model='gemini-1.5-flash',
        base_url='https://generativelanguage.googleapis.com/v1beta',
        base_url_env='GEMINI_BASE_URL',
    ),
    'openrouter': ProviderConfig(
        name='openrouter',
        api_key_env='OPENROUTER_API_KEY',
        default_model='openai/gpt-4o-mini',
        base_url='https://openrouter.ai/api/v1',
        base_url_env='OPENROUTER_BASE_URL',
    ),
    'opencodezen-go': ProviderConfig(
        name='opencodezen-go',
        api_key_env='OPENCODEZEN_API_KEY',
        default_model='opencodezen-go',
        base_url='https://api.opencodezen.com/v1',
        base_url_env='OPENCODEZEN_BASE_URL',
    ),
}


def available_providers() -> list[str]:
    return sorted(PROVIDER_CONFIGS)


def create_llm_adapter(
    provider: str,
    *,
    transport: Optional[HTTPTransport] = None,
    model: Optional[str] = None,
) -> LLMAdapter:
    normalized = provider.lower()
    if normalized not in PROVIDER_CONFIGS:
        raise LLMConfigurationError(
            f"unknown provider '{provider}'. Available: {', '.join(available_providers())}"
        )
    config = PROVIDER_CONFIGS[normalized]
    if model:
        config = ProviderConfig(
            name=config.name,
            api_key_env=config.api_key_env,
            default_model=config.default_model,
            base_url=config.base_url,
            api_key=config.api_key,
            model=model,
            base_url_env=config.base_url_env,
        )
    if normalized == 'claude':
        return ClaudeAdapter(config, transport=transport)
    if normalized == 'gemini':
        return GeminiAdapter(config, transport=transport)
    return OpenAICompatibleAdapter(config, transport=transport)


def check_llm_configuration(provider: str) -> tuple[bool, str]:
    adapter = create_llm_adapter(provider)
    try:
        adapter.config.resolved_api_key()  # type: ignore[attr-defined]
    except LLMConfigurationError as exc:
        return False, str(exc)
    return True, f'{provider} configuration is available'


PROVIDER_COST_PER_1K_INPUT: dict[str, float] = {
    'claude': 0.003,
    'gpt': 0.00015,
    'gemini': 0.000075,
    'openrouter': 0.0005,
    'opencodezen-go': 0.0005,
}

PROVIDER_COST_PER_1K_OUTPUT: dict[str, float] = {
    'claude': 0.015,
    'gpt': 0.0006,
    'gemini': 0.0003,
    'openrouter': 0.002,
    'opencodezen-go': 0.002,
}


def _estimate_cost(
    provider: str, model: str, input_tokens: int, output_tokens: int
) -> float:
    cost_1k_in = PROVIDER_COST_PER_1K_INPUT.get(provider, 0.001)
    cost_1k_out = PROVIDER_COST_PER_1K_OUTPUT.get(provider, 0.001)
    cost = (input_tokens * cost_1k_in + output_tokens * cost_1k_out) / 1000.0
    return round(cost * 100, 4)


def estimate_cost_preflight(
    provider: str,
    model: str,
    approx_input_chars: int,
    max_output_tokens: int,
) -> float:
    approx_input_tokens = max(1, approx_input_chars // 3)
    cost_1k_in = PROVIDER_COST_PER_1K_INPUT.get(provider, 0.001)
    cost_1k_out = PROVIDER_COST_PER_1K_OUTPUT.get(provider, 0.001)
    cost = (approx_input_tokens * cost_1k_in + max_output_tokens * cost_1k_out) / 1000.0
    return round(cost * 100, 4)
