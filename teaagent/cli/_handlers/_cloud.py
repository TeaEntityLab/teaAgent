"""CLI handlers for ``teaagent cloud`` commands."""

from __future__ import annotations

import json
from argparse import Namespace


def cloud_submit_command(args: Namespace) -> int:
    from teaagent.cloud_tasks import CloudTaskManager, CloudTaskStore

    manager = CloudTaskManager(store=CloudTaskStore(args.root))
    task = manager.submit(args.name, args.task, args.runtime)
    if args.json:
        print(json.dumps(task.to_dict()))
    else:
        print(f'Task {task.task_id} submitted: {task.name} [{task.status}]')
    return 0


def cloud_list_command(args: Namespace) -> int:
    from teaagent.cloud_tasks import CloudTaskManager, CloudTaskStore

    manager = CloudTaskManager(store=CloudTaskStore(args.root, readonly=True))
    tasks = manager.list_tasks(status=args.status, limit=args.limit)
    if args.json:
        print(json.dumps([t.to_dict() for t in tasks]))
    else:
        for t in tasks:
            print(f'{t.task_id[:8]}  {t.name:<20}  {t.status:<12}  {t.runtime}')
    return 0


def cloud_show_command(args: Namespace) -> int:
    from teaagent.cloud_tasks import CloudTaskManager, CloudTaskStore

    manager = CloudTaskManager(store=CloudTaskStore(args.root, readonly=True))
    try:
        task = manager.poll(args.task_id)
    except ValueError as exc:
        print(json.dumps({'status': 'error', 'message': str(exc)}))
        return 1
    if args.json:
        print(json.dumps(task.to_dict()))
    else:
        print(f'ID:        {task.task_id}')
        print(f'Name:      {task.name}')
        print(f'Runtime:   {task.runtime}')
        print(f'Status:    {task.status}')
        print(f'Created:   {task.created_at}')
        if task.result:
            print(f'Result:    {task.result[:500]}')
        if task.error:
            print(f'Error:     {task.error}')
    return 0


def cloud_cancel_command(args: Namespace) -> int:
    from teaagent.cloud_tasks import CloudTaskManager, CloudTaskStore

    manager = CloudTaskManager(store=CloudTaskStore(args.root))
    task = manager.cancel(args.task_id)
    print(f'Task {task.task_id[:8]} cancelled.')
    return 0


def cloud_capabilities_command(args: Namespace) -> int:
    from teaagent.cloud_tasks import CloudTaskManager, CloudTaskStore

    manager = CloudTaskManager(store=CloudTaskStore(args.root, readonly=True))
    caps = manager.capabilities()
    if args.json:
        print(json.dumps(caps))
    else:
        for c in caps or []:
            print(f'{c["name"]:<16}  {c["status"]:<12}  {c.get("install_hint", "")}')
    return 0
