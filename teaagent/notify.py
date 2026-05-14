"""Completion notifications for Ultrawork background workers.

When a background worker stops, ``fire_notification`` delivers an event
payload to a webhook URL and/or executes a shell command.  All delivery
errors are caught and silenced so a failing notification never crashes a run.

Usage::

    from teaagent.notify import NotifyConfig
    from teaagent.ultrawork import UltraworkStore

    notify = NotifyConfig(
        webhook_url='https://hooks.example.com/teaagent',
        shell_command='osascript -e "display notification \\"Worker done\\"..."',
    )
    store = UltraworkStore(root='.', notify_config=notify)
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class NotifyConfig:
    """Delivery targets for worker completion events.

    Parameters
    ----------
    webhook_url:
        HTTP(S) endpoint that receives a POST with a JSON body containing
        ``worker_id``, ``event``, ``pid``, ``started_at``, and ``command``.
    shell_command:
        Shell string executed via ``subprocess.run(shell=True)`` on completion.
        The worker ID is available as the environment variable
        ``TEAAGENT_WORKER_ID``.
    timeout_seconds:
        HTTP request timeout (default 5 s).
    """

    webhook_url: Optional[str] = None
    shell_command: Optional[str] = None
    timeout_seconds: float = 5.0


def fire_notification(
    config: NotifyConfig,
    worker: Any,
    *,
    event: str = 'stopped',
) -> None:
    """Fire all configured notification targets for *worker*.

    Parameters
    ----------
    config:
        Notification targets.
    worker:
        A :class:`~teaagent.ultrawork.WorkerRecord` or any object with a
        ``worker_id`` attribute.
    event:
        Event name string (default: ``'stopped'``).
    """
    payload: dict[str, Any] = {
        'worker_id': getattr(worker, 'worker_id', ''),
        'event': event,
        'pid': getattr(worker, 'pid', None),
        'started_at': getattr(worker, 'started_at', ''),
        'command': getattr(worker, 'command', []),
    }

    if config.webhook_url:
        _deliver_webhook(config.webhook_url, payload, timeout=config.timeout_seconds)

    if config.shell_command:
        _run_shell(config.shell_command, payload)


def _deliver_webhook(url: str, payload: dict[str, Any], *, timeout: float) -> None:
    with contextlib.suppress(Exception):
        body = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                'Content-Type': 'application/json',
                'Content-Length': str(len(body)),
            },
            method='POST',
        )
        urllib.request.urlopen(req, timeout=timeout).close()


def _run_shell(command: str, payload: dict[str, Any]) -> None:
    import os

    env = {**os.environ, 'TEAAGENT_WORKER_ID': str(payload.get('worker_id', ''))}
    with contextlib.suppress(Exception):
        subprocess.run(command, shell=True, env=env, timeout=10)
