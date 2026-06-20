from __future__ import annotations

from typing import Any, Optional

from teaagent.cli._output import _redact_value
from teaagent.wizard import redact_wizard_payload

_REDACTED = '***REDACTED***'
_SENSITIVE_KEY_MARKERS = (
    'token',
    'password',
    'passwd',
    'secret',
    'api_key',
    'apikey',
    'authorization',
    'auth',
)
_SENSITIVE_EXACT_KEYS = {
    'api_token',
    'api_key_env',
    'authorization',
    'cf_aig_authorization',
}


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace('-', '_')
    if normalized in {'token_source'}:
        return False
    if normalized in _SENSITIVE_EXACT_KEYS:
        return True
    return any(marker in normalized for marker in _SENSITIVE_KEY_MARKERS)


def _looks_like_sensitive_string(value: str) -> bool:
    candidate = value.strip()
    if not candidate:
        return False
    lower = candidate.lower()
    if lower.startswith('bearer '):
        return True
    if candidate.startswith(('sk-', 'rk-', 'pk-', 'ghp_', 'xoxb-', 'xoxp-')):
        return True
    # API keys and tokens are continuous strings without spaces;
    # commands, paths, and sentences with spaces are not secrets.
    if ' ' in candidate:
        return False
    return (
        len(candidate) >= 20
        and any(ch.isdigit() for ch in candidate)
        and any(ch.isalpha() for ch in candidate)
    )


def _redact_sensitive_fields(
    value: Any, known_sensitive_values: Optional[set[str]] = None
) -> Any:
    if known_sensitive_values is None:
        known_sensitive_values = set()

    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for k, v in value.items():
            key_str = str(k)
            if _is_sensitive_key(key_str):
                if isinstance(v, str) and v:
                    known_sensitive_values.add(v)
                redacted[k] = _REDACTED
            else:
                redacted[k] = _redact_sensitive_fields(v, known_sensitive_values)
        return redacted
    if isinstance(value, list):
        return [
            _redact_sensitive_fields(item, known_sensitive_values) for item in value
        ]
    if isinstance(value, str) and (
        value in known_sensitive_values or _looks_like_sensitive_string(value)
    ):
        return _REDACTED
    return value


def _sanitize_doctor_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[Any, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            key_upper = key_text.strip().upper()
            if _is_sensitive_key(key):
                sanitized[key] = _REDACTED
                continue
            if key_upper in {'API_TOKEN', 'AUTH', 'AUTHORIZATION'}:
                sanitized[key] = _REDACTED
                continue
            if key_upper in {'ENV', 'API_KEY_ENV'} and isinstance(item, str):
                sanitized[key] = (
                    _REDACTED if _looks_like_sensitive_env_name(item) else item
                )
                continue
            sanitized[key] = _sanitize_doctor_payload(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_doctor_payload(item) for item in value]
    if isinstance(value, str) and _looks_like_sensitive_string(value):
        return _REDACTED
    return value


def _json_default(obj: Any) -> str:
    """Safe fallback for JSON serialization — never expose raw __str__."""
    return f'[{type(obj).__name__}]'


def _looks_like_sensitive_env_name(value: str) -> bool:
    upper = value.strip().upper()
    if not upper or ' ' in upper:
        return False
    sensitive_markers = (
        'KEY',
        'TOKEN',
        'SECRET',
        'PASSWORD',
        'PASSWD',
        'PASS',
        'AUTH',
        'CREDENTIAL',
        'PRIVATE',
    )
    return upper.endswith(tuple(f'_{marker}' for marker in sensitive_markers))


def _ensure_log_safe(value: Any) -> Any:
    if isinstance(value, dict):
        safe: dict[Any, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key) or _looks_like_sensitive_env_name(key_text):
                safe[key] = _REDACTED
                continue
            safe[key] = _ensure_log_safe(item)
        return safe
    if isinstance(value, list):
        return [_ensure_log_safe(item) for item in value]
    if isinstance(value, str) and _looks_like_sensitive_string(value):
        return _REDACTED
    return value


def _strict_log_sanitize(value: Any) -> Any:
    """Final conservative sanitizer before logging JSON."""
    if isinstance(value, dict):
        sanitized: dict[Any, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key) or _looks_like_sensitive_env_name(key_text):
                sanitized[key] = _REDACTED
            else:
                sanitized[key] = _strict_log_sanitize(item)
        return sanitized
    if isinstance(value, list):
        return [_strict_log_sanitize(item) for item in value]
    if isinstance(value, str) and _looks_like_sensitive_string(value):
        return _REDACTED
    return value


def print_json(value: Any) -> None:
    """Doctor-specific JSON output with additional sanitization layers.

    This function applies doctor-specific redaction before delegating to the
    centralized print_json function for final serialization and output.
    """
    if isinstance(value, dict) and value.get('mode') in {'wizard', 'setup'}:
        value = redact_wizard_payload(value)
    value = _sanitize_doctor_payload(value)
    safe_value = _redact_sensitive_fields(value)
    # Final defense-in-depth pass at the logging sink.
    safe_value = _redact_sensitive_fields(_sanitize_doctor_payload(safe_value))
    safe_value = _ensure_log_safe(safe_value)
    safe_value = _strict_log_sanitize(safe_value)
    safe_value = _redact_value(safe_value)
    from teaagent.cli._output import print_json as _centralized_print_json

    _centralized_print_json(safe_value)
