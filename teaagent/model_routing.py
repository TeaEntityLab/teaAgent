from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ModelRoute:
    category: str
    provider: str
    model: Optional[str]
    reason: str

    def to_dict(self) -> dict[str, Optional[str]]:
        return {
            'category': self.category,
            'provider': self.provider,
            'model': self.model,
            'reason': self.reason,
        }


CATEGORY_KEYWORDS = {
    'review': {'review', 'audit', 'risk', 'regression', 'security'},
    'test': {'test', 'tests', 'pytest', 'unittest', 'verify', 'failure', 'failing'},
    'code': {'add', 'build', 'change', 'fix', 'implement', 'refactor', 'update'},
    'docs': {'doc', 'docs', 'documentation', 'readme', 'markdown'},
    'search': {'inspect', 'list', 'read', 'search', 'summarize', 'explain'},
}

PROVIDER_CATEGORY_MODELS = {
    'claude': {
        'review': 'claude-3-5-sonnet-latest',
        'test': 'claude-3-5-sonnet-latest',
        'code': 'claude-3-5-sonnet-latest',
        'docs': 'claude-3-5-haiku-latest',
        'search': 'claude-3-5-haiku-latest',
        'general': 'claude-3-5-sonnet-latest',
    },
    'gpt': {
        'review': 'gpt-4o',
        'test': 'gpt-4o-mini',
        'code': 'gpt-4o',
        'docs': 'gpt-4o-mini',
        'search': 'gpt-4o-mini',
        'general': 'gpt-4o-mini',
    },
    'gemini': {
        'review': 'gemini-1.5-pro',
        'test': 'gemini-1.5-flash',
        'code': 'gemini-1.5-pro',
        'docs': 'gemini-1.5-flash',
        'search': 'gemini-1.5-flash',
        'general': 'gemini-1.5-flash',
    },
    'openrouter': {
        'review': 'anthropic/claude-3.5-sonnet',
        'test': 'openai/gpt-4o-mini',
        'code': 'anthropic/claude-3.5-sonnet',
        'docs': 'openai/gpt-4o-mini',
        'search': 'openai/gpt-4o-mini',
        'general': 'openai/gpt-4o-mini',
    },
    'opencodezen-go': {
        'review': 'opencodezen-go',
        'test': 'opencodezen-go',
        'code': 'opencodezen-go',
        'docs': 'opencodezen-go',
        'search': 'opencodezen-go',
        'general': 'opencodezen-go',
    },
    'opencodezen': {
        'review': 'opencodezen',
        'test': 'opencodezen',
        'code': 'opencodezen',
        'docs': 'opencodezen',
        'search': 'opencodezen',
        'general': 'opencodezen',
    },
}


def classify_task(task: str) -> str:
    tokens = {token.strip('.,:;!?()[]{}"\'').lower() for token in task.split()}
    for category in ('review', 'test', 'docs', 'code', 'search'):
        if tokens & CATEGORY_KEYWORDS[category]:
            return category
    return 'general'


def route_model(task: str, *, provider: str, model: Optional[str] = None) -> ModelRoute:
    category = classify_task(task)
    if model:
        return ModelRoute(
            category=category,
            provider=provider,
            model=model,
            reason='explicit model override',
        )
    provider_models = PROVIDER_CATEGORY_MODELS.get(provider, {})
    routed_model = provider_models.get(category) or provider_models.get('general')
    return ModelRoute(
        category=category,
        provider=provider,
        model=routed_model,
        reason=f'{category} task routed for {provider}',
    )
