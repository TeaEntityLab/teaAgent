"""Webhook delivery for automation tick results."""

from __future__ import annotations

import hashlib
import hmac
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

from teaagent.automations import AutomationSpec
from teaagent.ergonomics.workspace_defaults import load_workspace_defaults
from teaagent.http_utils import safe_urlopen

_AUTOMATION_WEBHOOK_ENV = 'TEAAGENT_AUTOMATION_WEBHOOK_URL'
_AUTOMATION_WEBHOOK_SECRET_ENV = 'TEAAGENT_AUTOMATION_WEBHOOK_SECRET'


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


def resolve_automation_webhook_secret(root: str | Path = '.') -> Optional[str]:
    """Return the shared secret for HMAC signing, if configured."""
    defaults = load_workspace_defaults(root)
    secret = defaults.get('automation_webhook_secret')
    if secret is None or not str(secret).strip():
        import os

        secret = os.environ.get(_AUTOMATION_WEBHOOK_SECRET_ENV)
    if secret is None or not str(secret).strip():
        return None
    return str(secret).strip()


def sign_webhook_body(secret: str, body: bytes) -> str:
    """GitHub-style HMAC-SHA256 signature header value."""
    digest = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    return f'sha256={digest}'


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
        headers = {
            'Content-Type': 'application/json',
            'Content-Length': str(len(body)),
            'User-Agent': 'TeaAgent-AutomationWebhook/1',
        }
        secret = resolve_automation_webhook_secret(root)
        if secret:
            headers['X-TeaAgent-Signature-256'] = sign_webhook_body(secret, body)
        with safe_urlopen(url, timeout=5, data=body, headers=headers):
            pass  # Connection automatically closed
    except (urllib.error.URLError, OSError, ValueError):
        if raise_on_error:
            raise
        return True
    return True
