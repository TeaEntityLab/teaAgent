from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from teaagent.llm import LLMAdapter
from teaagent.run_store import RunStore
from teaagent.subagent_run_context import get_parallel_approval_mode
from teaagent.subagents._approval_queue import (
    make_centralized_subagent_approval_handler,
    should_use_centralized_approval,
)
from teaagent.subagents._isolation import (
    new_isolation_session_key,
    normalize_subagent_isolation,
    prepare_subagent_isolation,
)
from teaagent.subagents._loader import load_subagent_defs
from teaagent.subagents._review import capture_subagent_review
from teaagent.subagents._types import (
    DEFAULT_SUBAGENT_ISOLATION,
    SubagentDef,
    SubagentLineage,
    SubagentSession,
)


def _lineage_or_none(
    parent_run_id: str,
    def_name: str,
    depth: int,
    batch_index: Optional[int],
    isolation: str,
) -> Optional[SubagentLineage]:
    if not parent_run_id:
        return None
    return SubagentLineage(
        parent_run_id=parent_run_id,
        def_name=def_name,
        depth=depth,
        batch_index=batch_index,
        isolation=isolation,
    )


class SubagentManager:
    def __init__(
        self,
        *,
        root: Path,
        parent_config: Any,
        parent_adapter: LLMAdapter,
    ) -> None:
        self._defs = load_subagent_defs(root)
        self._sessions: dict[str, SubagentSession] = {}
        self._root = root.resolve()
        self._parent_config = parent_config
        self._parent_adapter = parent_adapter
        self._parent_registry: Any = None

    def bind_registry(self, registry: Any) -> None:
        self._parent_registry = registry

    def list_defs(self) -> list[SubagentDef]:
        return sorted(self._defs.values(), key=lambda d: d.name)

    def get_def(self, name: str) -> Optional[SubagentDef]:
        normalized = _normalize_name(name)
        for key, sub_def in self._defs.items():
            if _normalize_name(key) == normalized:
                return sub_def
        return None

    def run_subagent(
        self,
        *,
        task: str,
        parent_run_id: str,
        depth: int,
        def_name: Optional[str] = None,
        max_iterations: Optional[int] = None,
        max_tool_calls: Optional[int] = None,
        batch_index: Optional[int] = None,
        isolation: str = DEFAULT_SUBAGENT_ISOLATION,
    ) -> dict[str, Any]:
        from teaagent.chat_agent import run_chat_agent

        sub_def: Optional[SubagentDef] = None
        if def_name:
            sub_def = self.get_def(def_name)
            if sub_def is None:
                return _error(
                    f'unknown subagent: {def_name}',
                    lineage=_lineage_or_none(
                        parent_run_id,
                        def_name,
                        depth,
                        batch_index,
                        isolation,
                    ),
                )
            if depth >= sub_def.max_depth:
                return _error(
                    f"subagent '{sub_def.name}' max_depth {sub_def.max_depth} reached",
                    lineage=_lineage_or_none(
                        parent_run_id,
                        sub_def.name,
                        depth + 1,
                        batch_index,
                        isolation,
                    ),
                )

        resolved_max_iterations = max_iterations or (
            sub_def.max_iterations if sub_def else 5
        )
        resolved_max_tool_calls = max_tool_calls or (
            sub_def.max_tool_calls if sub_def else 5
        )

        normalized_isolation = normalize_subagent_isolation(isolation)
        if normalized_isolation is None:
            return _error(
                f'unsupported subagent isolation: {isolation!r}; '
                f'use one of: shared, worktree, container',
                lineage=_lineage_or_none(
                    parent_run_id,
                    def_name or 'generic',
                    depth + 1,
                    batch_index,
                    DEFAULT_SUBAGENT_ISOLATION,
                ),
            )
        isolation = normalized_isolation

        def_used = sub_def.name if sub_def else 'generic'
        iso_ctx, iso_error = prepare_subagent_isolation(
            self._root,
            isolation=isolation,
            session_key=new_isolation_session_key(
                parent_run_id=parent_run_id, def_name=def_used
            ),
        )
        if iso_ctx is None:
            return _error(
                iso_error,
                lineage=_lineage_or_none(
                    parent_run_id,
                    def_used,
                    depth + 1,
                    batch_index,
                    isolation,
                ),
            )

        task_spec = task
        if sub_def and sub_def.system_prompt.strip():
            task_spec = f'[{sub_def.name} role]\n{sub_def.system_prompt.strip()}\n\n---\n\nTask: {task}'

        child_depth = depth + 1
        worktree_rel: Optional[str] = None
        container_rel: Optional[str] = None
        if iso_ctx.worktree_path is not None:
            worktree_rel = _path_relative_to_root(iso_ctx.worktree_path, self._root)
        if iso_ctx.container_path is not None:
            container_rel = _path_relative_to_root(iso_ctx.container_path, self._root)

        use_centralized = should_use_centralized_approval(
            parent_run_id=parent_run_id,
            batch_index=batch_index,
            parallel_mode=get_parallel_approval_mode(),
        )
        approval_handler = self._parent_config.approval_handler
        if use_centralized:
            permission_mode = (
                sub_def.permission_mode
                if sub_def and sub_def.permission_mode is not None
                else self._parent_config.permission_mode
            )
            approval_handler = make_centralized_subagent_approval_handler(
                parent_run_id=parent_run_id,
                subagent_id=f'{parent_run_id}:{def_used}:{batch_index or 0}',
                subagent_name=def_used,
                permission_mode=str(
                    getattr(permission_mode, 'value', permission_mode)
                ),
                isolation=isolation,
                batch_index=batch_index,
                worktree_path=worktree_rel,
            )

        sub_config = replace(
            self._parent_config,
            root=iso_ctx.child_root,
            max_iterations=int(resolved_max_iterations),
            max_tool_calls=int(resolved_max_tool_calls),
            model=(
                sub_def.model
                if sub_def and sub_def.model
                else self._parent_config.model
            ),
            permission_mode=(
                sub_def.permission_mode
                if sub_def and sub_def.permission_mode is not None
                else self._parent_config.permission_mode
            ),
            approval_handler=approval_handler,
        )

        lineage = SubagentLineage(
            parent_run_id=parent_run_id,
            def_name=def_used,
            depth=child_depth,
            isolation=isolation,
            batch_index=batch_index,
            worktree_path=worktree_rel,
            container_path=container_rel,
        )

        registry = self._build_registry_for(sub_def)
        store = RunStore(iso_ctx.child_root)
        sub_audit = store.audit_logger()
        started_at = datetime.now(timezone.utc).isoformat()
        try:
            sub_result = run_chat_agent(
                task=task_spec,
                adapter=self._parent_adapter,
                config=sub_config,
                audit=sub_audit,
                registry=registry,
                depth=child_depth,
                initial_context_extra={'subagent_lineage': lineage.to_dict()},
            )
            sub_audit.record(
                'subagent_lineage',
                sub_result.run_id,
                **lineage.to_dict(),
            )
            review = capture_subagent_review(
                parent_root=self._root,
                child_root=iso_ctx.child_root,
                parent_run_id=parent_run_id,
                child_run_id=sub_result.run_id,
                lineage=lineage,
            )
            if review is not None:
                sub_audit.record(
                    'subagent_review_artifact',
                    sub_result.run_id,
                    **review,
                )
            store.logger_for_result(sub_result, sub_audit)
            completed_at = datetime.now(timezone.utc).isoformat()
            session = SubagentSession(
                session_id=sub_result.run_id,
                def_name=def_used,
                parent_run_id=parent_run_id,
                status=sub_result.status,
                started_at=started_at,
                depth=child_depth,
                batch_index=batch_index,
                isolation=isolation,
                worktree_path=worktree_rel,
                container_path=container_rel,
                completed_at=completed_at,
                iterations=sub_result.iterations,
                tool_calls=sub_result.tool_calls,
                final_answer=(
                    sub_result.final_answer.content if sub_result.final_answer else ''
                ),
                review=review,
            )
            self._sessions[session.session_id] = session
            return _success(session)
        finally:
            iso_ctx.cleanup()

    def _build_registry_for(self, sub_def: Optional[SubagentDef]) -> Any:
        if self._parent_registry is None:
            return None
        from teaagent.tools import ToolRegistry

        child = ToolRegistry()
        if sub_def is None or sub_def.tool_whitelist is None:
            source_names = sorted(self._parent_registry._tools.keys())
        else:
            source_names = sorted(sub_def.tool_whitelist)
        for name in source_names:
            if name == 'subagent' or name.startswith('subagent_'):
                continue
            try:
                tool = self._parent_registry.get(name)
            except KeyError:
                continue
            child.register(
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
                output_schema=tool.output_schema,
                annotations=tool.annotations,
                handler=tool.handler,
                rate_limit=tool.rate_limit,
            )
        return child


def _normalize_name(name: str) -> str:
    return name.strip().lower().replace('_', '-').replace(' ', '-')


def _path_relative_to_root(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _success(session: SubagentSession) -> dict[str, Any]:
    payload = {
        'run_id': session.session_id,
        'status': session.status,
        'iterations': session.iterations,
        'tool_calls': session.tool_calls,
        'final_answer': session.final_answer,
        'lineage': session.lineage.to_dict(),
        'message': '',
    }
    if session.review is not None:
        payload['review'] = session.review
        payload['message'] = 'review artifact ready for parent check/apply'
    return payload


def _error(
    message: str,
    *,
    lineage: Optional[SubagentLineage] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'run_id': '',
        'status': 'error',
        'iterations': 0,
        'tool_calls': 0,
        'final_answer': '',
        'message': message,
    }
    if lineage is not None:
        payload['lineage'] = lineage.to_dict()
    return payload
