from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
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

    _register_batch(registry, manager, depth, config)


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


def _register_batch(
    registry: ToolRegistry,
    manager: SubagentManager,
    depth: int,
    config: Any,
) -> None:
    """Register a ``subagent_batch`` tool that runs multiple subagents concurrently."""

    def execute_batch(args: dict[str, Any]) -> dict[str, Any]:
        if depth >= config.max_subagent_depth:
            return {
                'status': 'error',
                'results': [],
                'message': f'subagent depth {config.max_subagent_depth} reached',
            }

        tasks = args.get('tasks', [])
        if not isinstance(tasks, list) or not tasks:
            return {
                'status': 'error',
                'results': [],
                'message': "'tasks' must be a non-empty list of subagent task objects",
            }

        max_workers = min(_as_int(args.get('max_workers')) or 4, len(tasks))

        def _run_one(task_obj: dict) -> dict[str, Any]:
            task = task_obj.get('task', '')
            if not isinstance(task, str) or not task.strip():
                return _subagent_error("subagent requires non-empty 'task'")
            def_name = task_obj.get('def_name')
            return manager.run_subagent(
                task=task,
                parent_run_id='',
                depth=depth,
                def_name=def_name if isinstance(def_name, str) else None,
                max_iterations=_as_int(task_obj.get('max_iterations')),
                max_tool_calls=_as_int(task_obj.get('max_tool_calls')),
            )

        results: list[tuple[int, dict[str, Any]]] = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_run_one, t): i for i, t in enumerate(tasks)}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results.append((idx, future.result()))
                except Exception as exc:
                    results.append((idx, _subagent_error(str(exc))))

        results.sort(key=lambda x: x[0])
        ordered = [r for _, r in results]

        ok_count = sum(1 for r in ordered if r.get('status') == 'completed')
        return {
            'status': 'completed' if ok_count == len(ordered) else 'partial',
            'results': ordered,
            'total': len(ordered),
            'completed': ok_count,
        }

    registry.register(
        name='subagent_batch',
        description='Run multiple subagent tasks concurrently. Each task runs in its own isolated agent session.',
        input_schema={
            'type': 'object',
            'properties': {
                'tasks': {
                    'type': 'array',
                    'description': 'List of subagent task objects. Each must have a "task" field (string). Optional: "def_name", "max_iterations", "max_tool_calls".',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'task': {'type': 'string'},
                            'def_name': {'type': 'string'},
                            'max_iterations': {'type': 'integer'},
                            'max_tool_calls': {'type': 'integer'},
                        },
                        'required': ['task'],
                    },
                },
                'max_workers': {
                    'type': 'integer',
                    'description': 'Maximum concurrent subagents (default: 4).',
                },
            },
            'required': ['tasks'],
        },
        output_schema={
            'type': 'object',
            'properties': {
                'status': {'type': 'string'},
                'results': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'run_id': {'type': 'string'},
                            'status': {'type': 'string'},
                            'iterations': {'type': 'integer'},
                            'tool_calls': {'type': 'integer'},
                            'final_answer': {'type': 'string'},
                            'message': {'type': 'string'},
                        },
                    },
                },
                'total': {'type': 'integer'},
                'completed': {'type': 'integer'},
                'message': {'type': 'string'},
            },
            'required': ['status', 'results'],
        },
        annotations=ToolAnnotations(
            read_only=False, destructive=False, idempotent=False
        ),
        handler=execute_batch,
    )
