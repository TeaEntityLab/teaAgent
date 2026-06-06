from __future__ import annotations

import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any

from teaagent.llm import LLMAdapter
from teaagent.subagent_run_context import get_parent_run_id
from teaagent.subagents._isolation import (
    DEFAULT_SUBAGENT_BATCH_TIMEOUT_SECONDS,
    GLOBAL_MAX_SUBAGENT_BATCH_WORKERS,
    resolve_subagent_isolation,
)
from teaagent.subagents._manager import SubagentManager
from teaagent.subagents._team_orchestrator import TeamOrchestrator
from teaagent.subagents._types import DEFAULT_SUBAGENT_ISOLATION
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
        isolation = resolve_subagent_isolation(
            args.get('isolation'), root=manager._root
        )
        if isolation is None:
            return _subagent_error(
                f'unsupported subagent isolation: {args.get("isolation")!r}; '
                'use shared, worktree, directory-snapshot, docker, or auto'
            )
        return manager.run_subagent(
            task=task,
            parent_run_id=get_parent_run_id(),
            depth=depth,
            max_iterations=_as_int(args.get('max_iterations')),
            max_tool_calls=_as_int(args.get('max_tool_calls')),
            isolation=isolation,
        )

    _register(
        registry,
        name='subagent',
        description='Delegate one focused sub-task to a fresh agent run sharing tools and policy. Default isolation is worktree on git repos; pass isolation=shared explicitly for a shared workspace.',
        handler=execute,
    )

    for sub_def in manager.list_defs():
        tool_name = f'subagent_{sub_def.name}'

        def execute_named(
            args: dict[str, Any],
            *,
            def_name: str = sub_def.name,
            def_isolation: str = sub_def.isolation,
        ) -> dict[str, Any]:
            if depth >= config.max_subagent_depth:
                return _subagent_error(
                    f'subagent depth {config.max_subagent_depth} reached'
                )
            task = args.get('task')
            if not isinstance(task, str) or not task.strip():
                return _subagent_error("subagent requires non-empty 'task'")
            isolation = resolve_subagent_isolation(
                args.get('isolation'),
                root=manager._root,
                def_isolation=def_isolation,
            )
            if isolation is None:
                return _subagent_error(
                    f'unsupported subagent isolation: {args.get("isolation")!r}; '
                    'use shared, worktree, directory-snapshot, docker, or auto'
                )
            return manager.run_subagent(
                task=task,
                parent_run_id=get_parent_run_id(),
                depth=depth,
                def_name=def_name,
                max_iterations=_as_int(args.get('max_iterations')),
                max_tool_calls=_as_int(args.get('max_tool_calls')),
                isolation=isolation,
            )

        _register(
            registry,
            name=tool_name,
            description=sub_def.description
            or f'Delegate task to subagent {sub_def.name}.',
            handler=execute_named,
        )

    _register_batch(registry, manager, depth, config)
    _register_team_tool(registry, manager)


def _register_team_tool(
    registry: ToolRegistry,
    manager: SubagentManager,
) -> None:
    """Register the ``team`` tool for agent team orchestration."""

    orchestrator = TeamOrchestrator(
        root=manager._root,
        subagent_manager=manager,
    )

    def execute_team(args: dict[str, Any]) -> dict[str, Any]:
        task = args.get('task', '')
        if not isinstance(task, str) or not task.strip():
            return {'status': 'error', 'message': "team requires non-empty 'task'"}
        team_name = args.get('team_name', '')
        return orchestrator.run_team(
            task=task,
            team_name=team_name,
            parent_run_id=get_parent_run_id(),
        )

    registry.register(
        name='team',
        description='Run a multi-agent team: lead agent coordinates specialist subagents in parallel.',
        input_schema={
            'type': 'object',
            'properties': {
                'task': {'type': 'string', 'description': 'Task for the agent team.'},
                'team_name': {
                    'type': 'string',
                    'description': 'Team definition name from .teaagent/teams/.',
                },
            },
            'required': ['task', 'team_name'],
        },
        output_schema={
            'type': 'object',
            'properties': {
                'status': {'type': 'string'},
                'team': {'type': 'string'},
                'specialist_count': {'type': 'integer'},
                'output': {'type': 'string'},
                'message': {'type': 'string'},
            },
            'required': ['status'],
        },
        annotations=ToolAnnotations(
            read_only=False, destructive=False, idempotent=False
        ),
        handler=execute_team,
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
                'isolation': {
                    'type': 'string',
                    'description': (
                        'Workspace isolation mode. Omit for worktree on git repos; '
                        'pass isolation=shared explicitly for a shared workspace.'
                    ),
                },
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
                'cost_cents': {'type': 'number'},
                'final_answer': {'type': 'string'},
                'message': {'type': 'string'},
                'lineage': {
                    'type': 'object',
                    'properties': {
                        'parent_run_id': {'type': 'string'},
                        'def_name': {'type': 'string'},
                        'depth': {'type': 'integer'},
                        'isolation': {'type': 'string'},
                        'batch_index': {'type': 'integer'},
                        'worktree_path': {'type': 'string'},
                        'container_path': {'type': 'string'},
                    },
                },
                'review': {
                    'type': 'object',
                    'properties': {
                        'review_id': {'type': 'string'},
                        'patch_path': {'type': 'string'},
                        'status_path': {'type': 'string'},
                        'changed_files': {
                            'type': 'array',
                            'items': {'type': 'string'},
                        },
                    },
                },
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
                'lineage': [],
                'message': f'subagent depth {config.max_subagent_depth} reached',
            }

        tasks = args.get('tasks', [])
        if not isinstance(tasks, list) or not tasks:
            return {
                'status': 'error',
                'results': [],
                'lineage': [],
                'message': "'tasks' must be a non-empty list of subagent task objects",
            }

        max_workers = min(
            _as_int(args.get('max_workers')) or 4,
            len(tasks),
            GLOBAL_MAX_SUBAGENT_BATCH_WORKERS,
        )
        timeout_seconds = (
            _as_int(args.get('timeout_seconds'))
            or DEFAULT_SUBAGENT_BATCH_TIMEOUT_SECONDS
        )
        parent_run_id = get_parent_run_id()

        def _run_one(task_obj: dict, batch_index: int) -> dict[str, Any]:
            task = task_obj.get('task', '')
            if not isinstance(task, str) or not task.strip():
                return _subagent_error("subagent requires non-empty 'task'")
            def_name = task_obj.get('def_name')
            sub_def = manager.get_def(def_name) if isinstance(def_name, str) else None
            isolation = resolve_subagent_isolation(
                task_obj.get('isolation'),
                root=manager._root,
                def_isolation=sub_def.isolation
                if sub_def
                else DEFAULT_SUBAGENT_ISOLATION,
            )
            if isolation is None:
                return _subagent_error(
                    f'unsupported subagent isolation: {task_obj.get("isolation")!r}; '
                    'use shared, worktree, directory-snapshot, docker, or auto'
                )
            return manager.run_subagent(
                task=task,
                parent_run_id=parent_run_id,
                depth=depth,
                def_name=def_name if isinstance(def_name, str) else None,
                max_iterations=_as_int(task_obj.get('max_iterations')),
                max_tool_calls=_as_int(task_obj.get('max_tool_calls')),
                batch_index=batch_index,
                isolation=isolation,
            )

        results: list[tuple[int, dict[str, Any]]] = []
        deadline = time.monotonic() + max(timeout_seconds, 1)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_run_one, task, index): index
                for index, task in enumerate(tasks)
            }
            pending = set(futures.keys())
            while pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                done, pending = wait(
                    pending,
                    timeout=remaining,
                    return_when=FIRST_COMPLETED,
                )
                for future in done:
                    idx = futures[future]
                    try:
                        results.append((idx, future.result()))
                    except Exception as exc:
                        results.append((idx, _subagent_error(str(exc))))

            for future in pending:
                future.cancel()
                idx = futures[future]
                results.append(
                    (
                        idx,
                        _subagent_error(
                            f'batch timeout after {timeout_seconds}s before task started'
                        ),
                    )
                )

        results.sort(key=lambda x: x[0])
        ordered = [r for _, r in results]

        ok_count = sum(1 for r in ordered if r.get('status') == 'completed')
        timed_out = sum(
            1
            for r in ordered
            if r.get('status') == 'error'
            and 'batch timeout' in str(r.get('message', ''))
        )
        lineage = [
            entry
            for entry in (r.get('lineage') for r in ordered)
            if isinstance(entry, dict)
        ]
        if timed_out:
            status = 'partial'
            message = f'{timed_out} task(s) timed out after {timeout_seconds}s'
        elif ok_count == len(ordered):
            status = 'completed'
            message = ''
        else:
            status = 'partial'
            message = ''
        payload = {
            'status': status,
            'results': ordered,
            'lineage': lineage,
            'total': len(ordered),
            'completed': ok_count,
            'timed_out': timed_out,
            'timeout_seconds': timeout_seconds,
        }
        if message:
            payload['message'] = message
        return payload

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
                            'isolation': {
                                'type': 'string',
                                'description': (
                                    'Per-task isolation. Omit for worktree on git repos; '
                                    'pass isolation=shared explicitly for shared workspace.'
                                ),
                            },
                        },
                        'required': ['task'],
                    },
                },
                'max_workers': {
                    'type': 'integer',
                    'description': 'Maximum concurrent subagents (default: 4).',
                },
                'timeout_seconds': {
                    'type': 'integer',
                    'description': f'Batch deadline in seconds (default: {DEFAULT_SUBAGENT_BATCH_TIMEOUT_SECONDS}).',
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
                            'cost_cents': {'type': 'number'},
                            'final_answer': {'type': 'string'},
                            'message': {'type': 'string'},
                            'lineage': {
                                'type': 'object',
                                'properties': {
                                    'parent_run_id': {'type': 'string'},
                                    'def_name': {'type': 'string'},
                                    'depth': {'type': 'integer'},
                                    'isolation': {'type': 'string'},
                                    'batch_index': {'type': 'integer'},
                                    'worktree_path': {'type': 'string'},
                                    'container_path': {'type': 'string'},
                                },
                            },
                            'review': {
                                'type': 'object',
                                'properties': {
                                    'review_id': {'type': 'string'},
                                    'patch_path': {'type': 'string'},
                                    'status_path': {'type': 'string'},
                                    'changed_files': {
                                        'type': 'array',
                                        'items': {'type': 'string'},
                                    },
                                },
                            },
                        },
                    },
                },
                'total': {'type': 'integer'},
                'completed': {'type': 'integer'},
                'timed_out': {'type': 'integer'},
                'timeout_seconds': {'type': 'integer'},
                'message': {'type': 'string'},
                'lineage': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'parent_run_id': {'type': 'string'},
                            'def_name': {'type': 'string'},
                            'depth': {'type': 'integer'},
                            'isolation': {'type': 'string'},
                            'batch_index': {'type': 'integer'},
                            'worktree_path': {'type': 'string'},
                            'container_path': {'type': 'string'},
                        },
                    },
                },
            },
            'required': ['status', 'results', 'lineage'],
        },
        annotations=ToolAnnotations(
            read_only=False, destructive=False, idempotent=False
        ),
        handler=execute_batch,
    )
