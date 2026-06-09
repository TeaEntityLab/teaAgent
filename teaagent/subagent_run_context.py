from __future__ import annotations

from contextvars import ContextVar, Token

_parent_run_id: ContextVar[str] = ContextVar('subagent_parent_run_id', default='')
_parent_session_cost_cents: ContextVar[float] = ContextVar(
    'subagent_parent_session_cost_cents', default=0.0
)
_parallel_approval: ContextVar[bool] = ContextVar(
    'subagent_parallel_approval', default=False
)


def get_parent_run_id() -> str:
    return _parent_run_id.get()


def get_parent_session_cost_cents() -> float:
    return _parent_session_cost_cents.get()


def get_parallel_approval_mode() -> bool:
    return _parallel_approval.get()


def bind_parallel_approval_mode(enabled: bool) -> Token[bool]:
    return _parallel_approval.set(enabled)


def bind_parent_run_id(run_id: str) -> Token[str]:
    return _parent_run_id.set(run_id)


def bind_parent_session_cost_cents(cents: float) -> Token[float]:
    return _parent_session_cost_cents.set(float(cents))


def reset_parent_run_id(token: Token[str]) -> None:
    _parent_run_id.reset(token)


def reset_parent_session_cost_cents(token: Token[float]) -> None:
    _parent_session_cost_cents.reset(token)


def reset_parallel_approval_mode(token: Token[bool]) -> None:
    _parallel_approval.reset(token)
