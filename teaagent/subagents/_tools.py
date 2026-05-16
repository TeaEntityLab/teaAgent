from __future__ import annotations

from typing import Any

from teaagent.llm import LLMAdapter
from teaagent.subagents._manager import SubagentManager
from teaagent.tools import ToolAnnotations, ToolRegistry


def register_subagent_tools(
    registry: ToolRegistry,
    *,
    adapter: LLMAdapter,
    config: Any,
    depth: int,
    manager: SubagentManager,
) -> None:
    manager.bind_registry(registry)

    def execute(args: dict[str, Any]) -> dict[str, Any]:
        if depth >= config.max_subagent_depth:
            return _subagent_error(
                f'subagent depth {config.max_subagent_depth} reached'
            )
        task = args.get('task')
        if not isinstance(task, str) or not task.strip():
            return _subagent_error("subagent requires non-empty 'task'")
        return manager.run_subagent(
            task=task,
            parent_run_id='',
            depth=depth,
            max_iterations=_as_int(args.get('max_iterations')),
            max_tool_calls=_as_int(args.get('max_tool_calls')),
        )

    _register(
        registry,
        name='subagent',
        description='Delegate one focused sub-task to a fresh agent run sharing tools and policy.',
        handler=execute,
    )

    for sub_def in manager.list_defs():
        tool_name = f'subagent_{sub_def.name}'

        def execute_named(
            args: dict[str, Any], *, def_name: str = sub_def.name
        ) -> dict[str, Any]:
            if depth >= config.max_subagent_depth:
                return _subagent_error(
                    f'subagent depth {config.max_subagent_depth} reached'
                )
            task = args.get('task')
            if not isinstance(task, str) or not task.strip():
                return _subagent_error("subagent requires non-empty 'task'")
            return manager.run_subagent(
                task=task,
                parent_run_id='',
                depth=depth,
                def_name=def_name,
                max_iterations=_as_int(args.get('max_iterations')),
                max_tool_calls=_as_int(args.get('max_tool_calls')),
            )

        _register(
            registry,
            name=tool_name,
            description=sub_def.description
            or f'Delegate task to subagent {sub_def.name}.',
            handler=execute_named,
        )


def _register(
    registry: ToolRegistry, *, name: str, description: str, handler: Any
) -> None:
    registry.register(
        name=name,
        description=description,
        input_schema={
            'type': 'object',
            'properties': {
                'task': {'type': 'string'},
                'max_iterations': {'type': 'integer'},
                'max_tool_calls': {'type': 'integer'},
            },
            'required': ['task'],
        },
        output_schema={
            'type': 'object',
            'properties': {
                'run_id': {'type': 'string'},
                'status': {'type': 'string'},
                'iterations': {'type': 'integer'},
                'tool_calls': {'type': 'integer'},
                'final_answer': {'type': 'string'},
                'message': {'type': 'string'},
            },
            'required': ['status'],
        },
        annotations=ToolAnnotations(
            read_only=False, destructive=False, idempotent=False
        ),
        handler=handler,
    )


def _subagent_error(message: str) -> dict[str, Any]:
    return {
        'run_id': '',
        'status': 'error',
        'iterations': 0,
        'tool_calls': 0,
        'final_answer': '',
        'message': message,
    }


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
