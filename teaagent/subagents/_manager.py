from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from teaagent.llm import LLMAdapter
from teaagent.run_store import RunStore
from teaagent.subagents._loader import load_subagent_defs
from teaagent.subagents._types import SubagentDef, SubagentSession


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
        self._root = root
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
    ) -> dict[str, Any]:
        from teaagent.chat_agent import run_chat_agent

        sub_def: Optional[SubagentDef] = None
        if def_name:
            sub_def = self.get_def(def_name)
            if sub_def is None:
                return _error(f'unknown subagent: {def_name}')
            if depth >= sub_def.max_depth:
                return _error(
                    f"subagent '{sub_def.name}' max_depth {sub_def.max_depth} reached"
                )

        resolved_max_iterations = max_iterations or (
            sub_def.max_iterations if sub_def else 5
        )
        resolved_max_tool_calls = max_tool_calls or (
            sub_def.max_tool_calls if sub_def else 5
        )

        sub_config = replace(
            self._parent_config,
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
        )

        task_spec = task
        if sub_def and sub_def.system_prompt.strip():
            task_spec = f'[{sub_def.name} role]\n{sub_def.system_prompt.strip()}\n\n---\n\nTask: {task}'

        registry = self._build_registry_for(sub_def)
        store = RunStore(self._root)
        sub_audit = store.audit_logger()
        started_at = datetime.now(timezone.utc).isoformat()
        sub_result = run_chat_agent(
            task=task_spec,
            adapter=self._parent_adapter,
            config=sub_config,
            audit=sub_audit,
            registry=registry,
            depth=depth + 1,
        )
        store.logger_for_result(sub_result, sub_audit)
        completed_at = datetime.now(timezone.utc).isoformat()
        def_used = sub_def.name if sub_def else 'generic'
        session = SubagentSession(
            session_id=sub_result.run_id,
            def_name=def_used,
            parent_run_id=parent_run_id,
            status=sub_result.status,
            started_at=started_at,
            completed_at=completed_at,
            iterations=sub_result.iterations,
            tool_calls=sub_result.tool_calls,
            final_answer=(
                sub_result.final_answer.content if sub_result.final_answer else ''
            ),
        )
        self._sessions[session.session_id] = session
        return {
            'run_id': session.session_id,
            'status': session.status,
            'iterations': session.iterations,
            'tool_calls': session.tool_calls,
            'final_answer': session.final_answer,
            'message': '',
        }

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


def _error(message: str) -> dict[str, Any]:
    return {
        'run_id': '',
        'status': 'error',
        'iterations': 0,
        'tool_calls': 0,
        'final_answer': '',
        'message': message,
    }
