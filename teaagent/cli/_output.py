"""Shared output utilities for CLI handlers.

All output goes through print_json which applies defense-in-depth redaction
of values under sensitive-sounding keys before serialization.
"""

from __future__ import annotations

import json
from typing import Any

_REDACTED = '***REDACTED***'

_SENSITIVE_KEY_MARKERS: tuple[str, ...] = (
    'password',
    'passwd',
    'secret',
    'api_key',
    'apikey',
    'authorization',
)

_SENSITIVE_EXACT_KEYS: frozenset[str] = frozenset(
    {
        'api_token',
        'api_key_env',
        'authorization',
        'cf_aig_authorization',
        'auth',
    }
)


def _is_sensitive_key(key: str) -> bool:
    """Check whether a dict key suggests the value is sensitive."""
    normalized = key.lower().replace('-', '_')
    if normalized in _SENSITIVE_EXACT_KEYS:
        return True
    # LLM usage counters (*_tokens) are metrics, not credentials.
    if normalized.endswith('_tokens'):
        return False
    # Credential fields use *_token or bare token, not token_budget/token_source.
    if normalized == 'token' or normalized.endswith('_token'):
        return True
    return any(marker in normalized for marker in _SENSITIVE_KEY_MARKERS)


def _redact_value(value: Any) -> Any:
    """Recursively replace values under sensitive-sounding keys with REDACTED.

    This is a defense-in-depth safety net applied to all JSON output.
    Callers that handle sensitive data should implement their own
    domain-specific sanitization upstream — this pass is a last resort.
    """
    if isinstance(value, dict):
        return {
            k: _REDACTED if _is_sensitive_key(str(k)) else _redact_value(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def print_json(value: Any) -> None:
    """Print value as JSON to stdout with sensitive-data redaction.

    Uses ensure_ascii=False for proper Unicode support and sort_keys=True
    for consistent output ordering.

    Args:
        value: The value to print as JSON (typically a dict or list).
    """
    print(json.dumps(_redact_value(value), ensure_ascii=False, sort_keys=True))
