from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, cast

from teaagent.http_rate_limit import TokenRateLimiter
from teaagent.llm._adapters import (
    ClaudeAdapter,
    GeminiAdapter,
    OpenAICompatibleAdapter,
    WorkersAIAdapter,
)
from teaagent.llm._fake_adapter import FakeLLMAdapter
from teaagent.llm._types import (
    HTTPTransport,
    LLMAdapter,
    LLMConfigurationError,
    ProviderConfig,
)

PROVIDER_CONFIGS = {
    'fake': ProviderConfig(
        name='fake',
        api_key_env='FAKE_API_KEY',
        default_model='fake-model',
        base_url='https://fake.example.com/v1',
        base_url_env='FAKE_BASE_URL',
    ),
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
    'ollama': ProviderConfig(
        name='ollama',
        api_key_env='OLLAMA_API_KEY',
        default_model='llama3.2',
        base_url='http://localhost:11434/v1',
        api_key='ollama',
        base_url_env='OLLAMA_BASE_URL',
    ),
    'vllm': ProviderConfig(
        name='vllm',
        api_key_env='VLLM_API_KEY',
        default_model='meta-llama/Llama-3.1-8B-Instruct',
        base_url='http://localhost:8000/v1',
        api_key='vllm',
        base_url_env='VLLM_BASE_URL',
    ),
    'opencodezen-go': ProviderConfig(
        name='opencodezen-go',
        api_key_env='OPENCODEZEN_API_KEY',
        default_model='deepseek-v4-flash',
        base_url='https://opencode.ai/zen/go/v1',
        base_url_env='OPENCODEZEN_BASE_URL',
    ),
    'opencodezen': ProviderConfig(
        name='opencodezen',
        api_key_env='OPENCODEZEN_API_KEY',
        default_model='deepseek-v4-flash-free',
        base_url='https://opencode.ai/zen/v1',
        base_url_env='OPENCODEZEN_COMPAT_BASE_URL',
    ),
    'mistral': ProviderConfig(
        name='mistral',
        api_key_env='MISTRAL_API_KEY',
        default_model='mistral-large-latest',
        base_url='https://api.mistral.ai/v1',
        base_url_env='MISTRAL_BASE_URL',
    ),
    'deepseek': ProviderConfig(
        name='deepseek',
        api_key_env='DEEPSEEK_API_KEY',
        default_model='deepseek-chat',
        base_url='https://api.deepseek.com/v1',
        base_url_env='DEEPSEEK_BASE_URL',
    ),
    'grok': ProviderConfig(
        name='grok',
        api_key_env='XAI_API_KEY',
        default_model='grok-3-latest',
        base_url='https://api.x.ai/v1',
        base_url_env='XAI_BASE_URL',
    ),
    'workers-ai': ProviderConfig(
        name='workers-ai',
        api_key_env='CLOUDFLARE_API_TOKEN',
        default_model='@cf/meta/llama-3.1-8b-instruct',
        base_url='https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/v1',
        base_url_env='WORKERS_AI_BASE_URL',
    ),
    'aigateway': ProviderConfig(
        name='aigateway',
        api_key_env='CLOUDFLARE_API_TOKEN',
        default_model='openai/gpt-4o-mini',
        base_url='https://gateway.ai.cloudflare.com/v1/{ACCOUNT_ID}/{GATEWAY_ID}/compat',
        base_url_env='AIGATEWAY_BASE_URL',
    ),
}


def is_local_provider(name: str) -> bool:
    """Return True if the provider's default base_url points to localhost.

    Local providers (Ollama, vLLM) run a server on the local machine and
    communicate over loopback — they don't need outbound internet connectivity.
    """
    normalized = name.lower()
    if normalized not in PROVIDER_CONFIGS:
        return False
    base_url = PROVIDER_CONFIGS[normalized].base_url
    return 'localhost' in base_url or '127.0.0.1' in base_url


def available_providers() -> list[str]:
    return sorted(PROVIDER_CONFIGS)


def create_llm_adapter(
    provider: str,
    *,
    transport: Optional[HTTPTransport] = None,
    model: Optional[str] = None,
    rate_limiter: Optional[TokenRateLimiter] = None,
) -> LLMAdapter:
    normalized = provider.lower()
    # Special case for fake adapter used in tests
    if normalized == 'fake':
        return cast(
            LLMAdapter,
            FakeLLMAdapter(provider='fake', model=model or 'fake-model'),
        )
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
        return cast(
            LLMAdapter,
            ClaudeAdapter(config, transport=transport, rate_limiter=rate_limiter),
        )
    if normalized == 'gemini':
        return cast(
            LLMAdapter,
            GeminiAdapter(config, transport=transport, rate_limiter=rate_limiter),
        )
    if normalized == 'workers-ai':
        return cast(
            LLMAdapter,
            WorkersAIAdapter(config, transport=transport, rate_limiter=rate_limiter),
        )
    if normalized == 'aigateway':
        return cast(
            LLMAdapter,
            OpenAICompatibleAdapter(
                config, transport=transport, rate_limiter=rate_limiter
            ),
        )
    return cast(
        LLMAdapter,
        OpenAICompatibleAdapter(config, transport=transport, rate_limiter=rate_limiter),
    )


def check_llm_configuration(provider: str) -> tuple[bool, str]:
    adapter = create_llm_adapter(provider)
    try:
        adapter.config.resolved_api_key()
    except LLMConfigurationError as exc:
        return False, str(exc)
    return True, f'{provider} configuration is available'


# Base per-provider rates (used when no model-specific rate exists).
# fake/ollama/vllm use nominal non-zero rates so the budget guard fires in tests
# and local-model runs. These are NOT real API prices ($0 for local inference)
# but a sentinel that lets budget accounting remain exercisable.
PROVIDER_COST_PER_1K_INPUT: dict[str, float] = {
    'fake': 0.001,
    'claude': 0.003,
    'gpt': 0.00015,
    'gemini': 0.000075,
    'openrouter': 0.0005,
    'ollama': 0.0001,
    'opencodezen-go': 0.0005,
    'opencodezen': 0.0005,
    'vllm': 0.0001,
    'mistral': 0.002,
    'deepseek': 0.00014,
    'grok': 0.003,
    'workers-ai': 0.0005,
    'aigateway': 0.0005,
}

PROVIDER_COST_PER_1K_OUTPUT: dict[str, float] = {
    'fake': 0.001,
    'claude': 0.015,
    'gpt': 0.0006,
    'gemini': 0.0003,
    'openrouter': 0.002,
    'ollama': 0.0001,
    'opencodezen-go': 0.002,
    'opencodezen': 0.002,
    'vllm': 0.0001,
    'mistral': 0.006,
    'deepseek': 0.00028,
    'grok': 0.015,
    'workers-ai': 0.0015,
    'aigateway': 0.0015,
}

# Model-specific overrides for high-cost models.
# Keyed by model-name prefix (case-insensitive match).
# Values are (input_per_1k, output_per_1k) tuples.
_MODEL_COST_OVERRIDES: dict[str, tuple[float, float]] = {
    'claude-3-opus': (0.015, 0.075),
    'claude-3.5-opus': (0.015, 0.075),
    'claude-3.5-sonnet': (0.003, 0.015),
    'claude-3-haiku': (0.00025, 0.00125),
    'claude-3.5-haiku': (0.00025, 0.00125),
    'gpt-4-turbo': (0.01, 0.03),
    'gpt-4o': (0.0025, 0.01),
    'gpt-4o-mini': (0.00015, 0.0006),
    'o1': (0.015, 0.06),
    'o3': (0.01, 0.04),
    'deepseek-reasoner': (0.00055, 0.00219),
    'gemini-2.0-flash': (0.0001, 0.0004),
    'gemini-1.5-pro': (0.0035, 0.0105),
}


def _model_specific_cost(provider: str, model: str) -> tuple[float, float] | None:
    """Look up model-specific cost override if available."""
    model_lower = model.lower()
    for prefix, (cost_in, cost_out) in _MODEL_COST_OVERRIDES.items():
        if model_lower.startswith(prefix):
            return cost_in, cost_out
    return None


def _lookup_cost_rates(provider: str | None, model: str) -> tuple[float, float]:
    """Look up input/output cost per 1K tokens, checking model-specific overrides first."""
    if not provider:
        return 0.001, 0.001

    normalized_provider = provider.lower()

    # Check model-specific override first
    model_rates = _model_specific_cost(normalized_provider, model)
    if model_rates is not None:
        return model_rates

    # Fall back to provider-level rates
    cost_1k_in = PROVIDER_COST_PER_1K_INPUT.get(normalized_provider, 0.001)
    cost_1k_out = PROVIDER_COST_PER_1K_OUTPUT.get(normalized_provider, 0.001)
    return cost_1k_in, cost_1k_out


def _estimate_cost(
    provider: str, model: str, input_tokens: int, output_tokens: int
) -> float:
    cost_1k_in, cost_1k_out = _lookup_cost_rates(provider, model)
    cost = (input_tokens * cost_1k_in + output_tokens * cost_1k_out) / 1000.0
    return round(cost * 100, 4)


def estimate_cost_preflight(
    provider: str,
    model: str,
    approx_input_chars: int,
    max_output_tokens: int,
) -> float:
    approx_input_tokens = max(1, approx_input_chars // 3)
    cost_1k_in, cost_1k_out = _lookup_cost_rates(provider, model)
    cost = (approx_input_tokens * cost_1k_in + max_output_tokens * cost_1k_out) / 1000.0
    return round(cost * 100, 4)


def load_llm_rate_limiter(
    workspace_root: str = '.',
    *,
    default_max_calls: int = 100,
    default_window: float = 60.0,
) -> Optional[TokenRateLimiter]:
    """Load LLM rate limit configuration from workspace config.

    Reads ``rate_limits`` section from ``<root>/.teaagent/config.json``.
    Returns ``None`` when no rate limits are configured.

    Config format::

        {
          "rate_limits": {
            "enabled": true,
            "default": {"max_calls": 100, "window_seconds": 60},
            "providers": {
              "gpt": {"max_calls": 50, "window_seconds": 60},
              "claude": {"max_calls": 10, "window_seconds": 60}
            }
          }
        }
    """
    try:
        config_path = Path(workspace_root) / '.teaagent' / 'config.json'
        if not config_path.is_file():
            return None
        data = json.loads(config_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None

    rate_cfg = data.get('rate_limits')
    if not isinstance(rate_cfg, dict):
        return None
    if not rate_cfg.get('enabled', False):
        return None

    default_cfg = rate_cfg.get('default')
    if isinstance(default_cfg, dict):
        max_calls = int(default_cfg.get('max_calls', default_max_calls))
        window = float(default_cfg.get('window_seconds', default_window))
    else:
        max_calls = default_max_calls
        window = default_window

    return TokenRateLimiter(max_calls=max_calls, window_seconds=window)
