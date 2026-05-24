from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from teaagent.policy import PermissionMode

DEFAULT_SUBAGENT_ISOLATION = 'shared'


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
    disallowed_tools: Optional[frozenset[str]] = None
    max_depth: int = 1
    isolation: str = DEFAULT_SUBAGENT_ISOLATION
    background: bool = False
    effort: Optional[str] = None


@dataclass(frozen=True)
class SubagentLineage:
    """Parent-child run relationship for subagent delegation."""

    parent_run_id: str
    def_name: str
    depth: int
    isolation: str = DEFAULT_SUBAGENT_ISOLATION
    batch_index: Optional[int] = None
    worktree_path: Optional[str] = None
    container_path: Optional[str] = None

    def to_dict(self) -> dict[str, str | int]:
        payload: dict[str, str | int] = {
            'parent_run_id': self.parent_run_id,
            'def_name': self.def_name,
            'depth': self.depth,
            'isolation': self.isolation,
        }
        if self.batch_index is not None:
            payload['batch_index'] = self.batch_index
        if self.worktree_path is not None:
            payload['worktree_path'] = self.worktree_path
        if self.container_path is not None:
            payload['container_path'] = self.container_path
        return payload


@dataclass(frozen=True)
class SubagentSession:
    session_id: str
    def_name: str
    parent_run_id: str
    status: str
    started_at: str
    depth: int = 0
    batch_index: Optional[int] = None
    isolation: str = DEFAULT_SUBAGENT_ISOLATION
    worktree_path: Optional[str] = None
    container_path: Optional[str] = None
    completed_at: Optional[str] = None
    iterations: int = 0
    tool_calls: int = 0
    final_answer: str = ''

    @property
    def lineage(self) -> SubagentLineage:
        return SubagentLineage(
            parent_run_id=self.parent_run_id,
            def_name=self.def_name,
            depth=self.depth,
            isolation=self.isolation,
            batch_index=self.batch_index,
            worktree_path=self.worktree_path,
            container_path=self.container_path,
        )
