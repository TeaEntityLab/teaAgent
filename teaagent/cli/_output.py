"""Shared output utilities for CLI handlers.

All output goes through print_json which applies defense-in-depth redaction
of values under sensitive-sounding keys before serialization.
"""

from __future__ import annotations

import json
import re
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


_BEARER_PREFIX = 'bearer '

# Known credential prefixes for opaque API keys / tokens. These are distinctive
# enough that a value carrying one is a secret regardless of the key it sits
# under. Deliberately conservative: we do NOT use a generic length/entropy
# heuristic here, because run ids (uuid4 hex), commit SHAs, and similar opaque
# identifiers flow through this sink and must not be redacted.
_SENSITIVE_VALUE_PREFIXES: tuple[str, ...] = (
    'sk-',
    'rk-',
    'pk-',
    'ghp_',
    'gho_',
    'ghu_',
    'ghs_',
    'ghr_',
    'github_pat_',
    'xoxb-',
    'xoxp-',
    'xoxa-',
    'xoxr-',
    'AKIA',
    'ASIA',
)

# JWT: three base64url segments with the common base64url JSON header prefix.
_JWT_RE = re.compile(r'^eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}$')

_TOKEN_STRIP_CHARS = '\'"`,;()[]{}<>'
_BEARER_RE = re.compile(r'(?i)(^|\s)bearer\s+\S+')


def _candidate_tokens(value: str) -> list[str]:
    return [token.strip(_TOKEN_STRIP_CHARS) for token in value.split()]


def _remember_sensitive_value(value: Any, known_sensitive_values: set[str]) -> None:
    if not isinstance(value, str):
        return
    candidate = value.strip()
    if not candidate:
        return
    # Avoid turning benign short enum values such as "none" into global
    # redaction terms when they appear under a defensive sensitive key match.
    if len(candidate) >= 8 or _looks_like_sensitive_value(candidate):
        known_sensitive_values.add(candidate)


def _is_known_sensitive_value(value: str, known_sensitive_values: set[str]) -> bool:
    candidate = value.strip()
    if candidate in known_sensitive_values:
        return True
    return any(
        token in known_sensitive_values for token in _candidate_tokens(candidate)
    )


def _looks_like_sensitive_value(value: str) -> bool:
    """Detect strings whose shape marks them as credentials.

    Defense-in-depth against secrets that leak as values under non-sensitive
    keys (e.g. ``{"message": "Bearer sk-..."}``). Intentionally narrow: only
    well-known credential shapes match, so opaque identifiers such as run ids
    and SHAs pass through unredacted.
    """
    candidate = value.strip()
    if not candidate:
        return False
    if _BEARER_RE.search(candidate):
        return True
    # Credential prefixes apply to opaque token-shaped substrings. This catches
    # both a bare token and an error string such as "request failed: sk-...".
    for token in _candidate_tokens(candidate):
        if token.startswith(_SENSITIVE_VALUE_PREFIXES) or _JWT_RE.match(token):
            return True
    return False


def _redact_value(value: Any, known_sensitive_values: set[str] | None = None) -> Any:
    """Recursively redact values that are sensitive by key OR by shape.

    Two independent defenses are applied:
    1. Key-based: any value under a sensitive-sounding key is redacted.
    2. Value-based: any string whose shape matches a known credential format
       is redacted even under a non-sensitive key.

    Values seen under sensitive keys are also tracked so duplicate appearances
    elsewhere in the same payload are removed. This is a defense-in-depth safety
    net applied to all JSON output. Callers that handle sensitive data should
    implement their own domain-specific sanitization upstream — this pass is a
    last resort.
    """
    if known_sensitive_values is None:
        known_sensitive_values = set()
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                _remember_sensitive_value(item, known_sensitive_values)
                redacted[key] = _REDACTED
            else:
                redacted[key] = _redact_value(item, known_sensitive_values)
        return redacted
    if isinstance(value, list):
        return [_redact_value(item, known_sensitive_values) for item in value]
    if isinstance(value, str) and (
        _is_known_sensitive_value(value, known_sensitive_values)
        or _looks_like_sensitive_value(value)
    ):
        return _REDACTED
    return value


def print_json(value: Any) -> None:
    """Print value as JSON to stdout with sensitive-data redaction.

    Uses ensure_ascii=False for proper Unicode support and sort_keys=True
    for consistent output ordering.

    Args:
        value: The value to print as JSON (typically a dict or list).
    """
    # _redact_value is the defense-in-depth sanitizer: it recursively replaces
    # values under sensitive-sounding keys with _REDACTED before serialization.
    # CodeQL cannot statically prove this custom sanitizer covers all sensitive
    # data, so the alert is suppressed here. Callers handling raw secrets must
    # also sanitize upstream (e.g. _sanitize_doctor_payload in doctor handlers).
    # lgtm[py/clear-text-logging-sensitive-data]
    print(json.dumps(_redact_value(value), ensure_ascii=False, sort_keys=True))
