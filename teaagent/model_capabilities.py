from __future__ import annotations

from typing import Any

from teaagent.llm._config import PROVIDER_CONFIGS

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


def explain_route(provider: str, model: str | None = None) -> dict[str, Any]:
    row = next(
        (item for item in build_capability_table() if item['provider'] == provider),
        None,
    )
    if row is None:
        raise KeyError(f'unknown provider: {provider}')
    selected_model = model or row['default_model']
    return {
        'provider': provider,
        'model': selected_model,
        'capabilities': row,
        'routing_notes': (
            f'Prefer {row.get("edit_strategy", "patch")} edits; '
            f'cost tier {row.get("cost_tier", "unknown")}; '
            f'structured_output={row.get("structured_output", False)}'
        ),
    }
