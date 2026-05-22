from __future__ import annotations

from typing import Any

from teaagent.llm._config import PROVIDER_CONFIGS
from teaagent.model_routing import PROVIDER_CATEGORY_MODELS

# Static routing hints separate from wire adapters (Aider-style capability table).
_PROVIDER_CAPABILITIES: dict[str, dict[str, Any]] = {
    'claude': {
        'edit_strategy': 'patch',
        'cost_tier': 'medium',
        'cache_support': True,
        'structured_output': True,
        'tool_calling': True,
        'streaming': True,
    },
    'gpt': {
        'edit_strategy': 'patch',
        'cost_tier': 'medium',
        'cache_support': True,
        'structured_output': True,
        'tool_calling': True,
        'streaming': True,
    },
    'gemini': {
        'edit_strategy': 'whole',
        'cost_tier': 'low',
        'cache_support': True,
        'structured_output': True,
        'tool_calling': True,
        'streaming': True,
    },
    'openrouter': {
        'edit_strategy': 'patch',
        'cost_tier': 'variable',
        'cache_support': False,
        'structured_output': True,
        'tool_calling': True,
        'streaming': True,
    },
    'ollama': {
        'edit_strategy': 'whole',
        'cost_tier': 'local',
        'cache_support': False,
        'structured_output': False,
        'tool_calling': True,
        'streaming': True,
    },
    'vllm': {
        'edit_strategy': 'whole',
        'cost_tier': 'local',
        'cache_support': False,
        'structured_output': False,
        'tool_calling': True,
        'streaming': True,
    },
    'opencodezen-go': {
        'edit_strategy': 'whole',
        'cost_tier': 'low',
        'cache_support': False,
        'structured_output': False,
        'tool_calling': True,
        'streaming': True,
    },
    'opencodezen': {
        'edit_strategy': 'whole',
        'cost_tier': 'low',
        'cache_support': False,
        'structured_output': False,
        'tool_calling': True,
        'streaming': True,
    },
    'mistral': {
        'edit_strategy': 'patch',
        'cost_tier': 'medium',
        'cache_support': False,
        'structured_output': True,
        'tool_calling': True,
        'streaming': True,
    },
    'workers-ai': {
        'edit_strategy': 'whole',
        'cost_tier': 'low',
        'cache_support': False,
        'structured_output': False,
        'tool_calling': True,
        'streaming': True,
    },
    'aigateway': {
        'edit_strategy': 'patch',
        'cost_tier': 'variable',
        'cache_support': False,
        'structured_output': True,
        'tool_calling': True,
        'streaming': True,
    },
    'deepseek': {
        'edit_strategy': 'patch',
        'cost_tier': 'low',
        'cache_support': False,
        'structured_output': True,
        'tool_calling': True,
        'streaming': True,
    },
    'grok': {
        'edit_strategy': 'whole',
        'cost_tier': 'low',
        'cache_support': False,
        'structured_output': True,
        'tool_calling': True,
        'streaming': True,
    },
}


def _models_for_provider(provider: str, config_default: str) -> list[str]:
    routed = PROVIDER_CATEGORY_MODELS.get(provider, {})
    names = {config_default, *routed.values()}
    return sorted(name for name in names if name)


def build_capability_table() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, config in sorted(PROVIDER_CONFIGS.items()):
        caps = dict(_PROVIDER_CAPABILITIES.get(name, {}))
        rows.append(
            {
                'provider': name,
                'default_model': config.default_model,
                'api_key_env': config.api_key_env,
                'base_url_env': config.base_url_env,
                **caps,
            }
        )
    return rows


def build_model_capability_table(
    *, provider: str | None = None, model: str | None = None
) -> list[dict[str, Any]]:
    """Per-model rows (Aider-style) derived from routing tables + provider defaults."""
    rows: list[dict[str, Any]] = []
    providers = [provider] if provider else sorted(PROVIDER_CONFIGS.keys())
    for pname in providers:
        if pname not in PROVIDER_CONFIGS:
            continue
        config = PROVIDER_CONFIGS[pname]
        caps = dict(_PROVIDER_CAPABILITIES.get(pname, {}))
        routed = PROVIDER_CATEGORY_MODELS.get(pname, {})
        for model_name in _models_for_provider(pname, config.default_model):
            if model and model_name != model:
                continue
            categories = [
                cat
                for cat, routed_model in routed.items()
                if routed_model == model_name
            ]
            if model_name == config.default_model and 'default' not in categories:
                categories.append('default')
            rows.append(
                {
                    'provider': pname,
                    'model': model_name,
                    'categories': categories or ['general'],
                    **caps,
                }
            )
    return rows


def explain_route(provider: str, model: str | None = None) -> dict[str, Any]:
    row = next(
        (item for item in build_capability_table() if item['provider'] == provider),
        None,
    )
    if row is None:
        raise KeyError(f'unknown provider: {provider}')
    selected_model = model or row['default_model']
    model_row = next(
        (
            item
            for item in build_model_capability_table(
                provider=provider, model=selected_model
            )
        ),
        None,
    )
    return {
        'provider': provider,
        'model': selected_model,
        'capabilities': model_row or row,
        'routing_notes': (
            f'Prefer {row.get("edit_strategy", "patch")} edits; '
            f'cost tier {row.get("cost_tier", "unknown")}; '
            f'structured_output={row.get("structured_output", False)}'
        ),
    }
