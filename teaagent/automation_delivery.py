"""Webhook delivery for automation tick results."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

from teaagent.automations import AutomationSpec
from teaagent.ergonomics.workspace_defaults import load_workspace_defaults

_AUTOMATION_WEBHOOK_ENV = 'TEAAGENT_AUTOMATION_WEBHOOK_URL'


def resolve_automation_webhook_url(root: str | Path = '.') -> Optional[str]:
    """Return the workspace automation webhook URL, if configured."""
    defaults = load_workspace_defaults(root)
    url = defaults.get('automation_webhook_url')
    if url is None or not str(url).strip():
        import os

        url = os.environ.get(_AUTOMATION_WEBHOOK_ENV)
    if url is None or not str(url).strip():
        return None
    return str(url).strip()


def deliver_automation_tick(
    root: str | Path,
    spec: AutomationSpec,
    *,
    status: str,
    collector: Optional[dict[str, Any]] = None,
    log_tail: str = '',
    run_id: Optional[str] = None,
    raise_on_error: bool = False,
) -> bool:
    """POST a tick result when ``spec.delivery`` is ``webhook``.

    Returns ``True`` when a delivery was attempted, ``False`` when skipped.
    """
    delivery = (spec.delivery or 'background_log').strip()
    if delivery != 'webhook':
        return False
    url = resolve_automation_webhook_url(root)
    if not url:
        return False
    payload: dict[str, Any] = {
        'event': 'automation_tick',
        'automation_id': spec.automation_id,
        'name': spec.name,
        'status': status,
        'schedule': spec.schedule,
        'last_run_id': run_id or spec.last_run_id,
        'collector': collector,
        'log_tail': log_tail,
        'context_from': spec.context_from,
    }
    try:
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
        urllib.request.urlopen(req, timeout=5).close()
    except (urllib.error.URLError, OSError, ValueError):
        if raise_on_error:
            raise
        return True
    return True
