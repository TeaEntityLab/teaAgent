from __future__ import annotations

from typing import Callable, Optional

from teaagent.llm import LLMAdapter, create_llm_adapter

InputFn = Callable[[str], str]
OutputFn = Callable[..., None]
AdapterFactory = Callable[[str, Optional[str]], LLMAdapter]


def default_adapter_factory(provider: str, model: Optional[str]) -> LLMAdapter:
    return create_llm_adapter(provider, model=model)


def _format_budget_cents(value: int | None) -> str:
    if value is None:
        return 'unlimited'
    return f'${value // 100}.{value % 100:02d}'


def _format_remaining_cents(limit: int | None, spent_cents: float) -> str:
    if limit is None:
        return 'unlimited'
    remaining = max(float(limit) - spent_cents, 0.0)
    return f'${int(remaining // 100)}.{int(remaining % 100):02d}'


def _effort_level_for_budget(limit: int | None) -> str:
    if limit is None:
        return 'unlimited'
    if limit == 200:
        return 'low'
    if limit == 1000:
        return 'normal'
    if limit == 5000:
        return 'high'
    return 'custom'
