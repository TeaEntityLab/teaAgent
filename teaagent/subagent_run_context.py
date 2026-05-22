from __future__ import annotations

from contextvars import ContextVar, Token

_parent_run_id: ContextVar[str] = ContextVar('subagent_parent_run_id', default='')


def get_parent_run_id() -> str:
    return _parent_run_id.get()


def bind_parent_run_id(run_id: str) -> Token[str]:
    return _parent_run_id.set(run_id)


def reset_parent_run_id(token: Token[str]) -> None:
    _parent_run_id.reset(token)
