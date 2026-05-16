from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from teaagent.policy import PermissionMode


@dataclass(frozen=True)
class SubagentDef:
    name: str
    description: str = ''
    system_prompt: str = ''
    model: Optional[str] = None
    permission_mode: Optional[PermissionMode] = None
    max_iterations: int = 5
    max_tool_calls: int = 8
    tool_whitelist: Optional[frozenset[str]] = None
    max_depth: int = 1


@dataclass(frozen=True)
class SubagentSession:
    session_id: str
    def_name: str
    parent_run_id: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    iterations: int = 0
    tool_calls: int = 0
    final_answer: str = ''
