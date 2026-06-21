"""Doctor CLI handlers — system health checks, provider diagnostics, config lint."""

from __future__ import annotations

from .model import (
    _doctor_aigateway_wizard,
    _doctor_model_wizard,
    _doctor_providers_wizard,
    doctor_aigateway,
    doctor_graphqlite,
    doctor_model,
    doctor_providers,
)
from .project import (
    _doctor_mcp_wizard,
    _doctor_project_wizard,
    doctor_config,
    doctor_config_lint_command,
    doctor_env_order,
    doctor_mcp,
    doctor_project,
)
from .sanitize import (
    _REDACTED,
    _SENSITIVE_EXACT_KEYS,
    _SENSITIVE_KEY_MARKERS,
    _ensure_log_safe,
    _is_sensitive_key,
    _json_default,
    _looks_like_sensitive_env_name,
    _looks_like_sensitive_string,
    _redact_sensitive_fields,
    _sanitize_doctor_payload,
    _strict_log_sanitize,
)
from .sanitize import (
    print_json as doctor_print_json,
)
from .system import (
    doctor_all,
    doctor_git_sandbox,
    doctor_migration_command,
    doctor_review_institution,
    doctor_selftest_command,
)

# Re-export `print_json` at module level for backward compatibility
# (tests and other modules import from teaagent.cli._handlers._doctor)
print_json = doctor_print_json

__all__ = [
    'doctor_graphqlite',
    'doctor_model',
    'doctor_aigateway',
    'doctor_providers',
    'doctor_project',
    'doctor_mcp',
    'doctor_env_order',
    'doctor_config',
    'doctor_all',
    'doctor_selftest_command',
    'doctor_migration_command',
    'doctor_git_sandbox',
    'doctor_review_institution',
    'doctor_config_lint_command',
    'print_json',
    # Private utilities (used by tests)
    '_doctor_aigateway_wizard',
    '_doctor_model_wizard',
    '_doctor_providers_wizard',
    '_doctor_project_wizard',
    '_doctor_mcp_wizard',
    '_is_sensitive_key',
    '_looks_like_sensitive_string',
    '_redact_sensitive_fields',
    '_sanitize_doctor_payload',
    '_json_default',
    '_looks_like_sensitive_env_name',
    '_ensure_log_safe',
    '_strict_log_sanitize',
    '_REDACTED',
    '_SENSITIVE_KEY_MARKERS',
    '_SENSITIVE_EXACT_KEYS',
]
