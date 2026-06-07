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


_PERMISSION_COLORS = {
    'read-only': '\033[32m',  # green
    'prompt': '\033[33m',  # yellow
    'workspace-write': '\033[36m',  # cyan
    'full-access': '\033[31m',  # red
}
_RESET = '\033[0m'


def format_status_bar(
    *,
    permission_mode: str,
    pending_approvals: int = 0,
    run_status: str = 'idle',
    memory_mb: float | None = None,
    use_color: bool = True,
) -> str:
    """Compact one-line status for the TUI footer."""
    mode_color = _PERMISSION_COLORS.get(permission_mode, '') if use_color else ''
    reset = _RESET if use_color else ''
    mode_label = (
        f'{mode_color}{permission_mode}{reset}' if use_color else permission_mode
    )
    parts = [f'mode={mode_label}', f'run={run_status}']
    if pending_approvals:
        parts.append(f'pending={pending_approvals}')
    if memory_mb is not None:
        parts.append(f'mem={memory_mb:.1f}MB')
    return ' | '.join(parts)
