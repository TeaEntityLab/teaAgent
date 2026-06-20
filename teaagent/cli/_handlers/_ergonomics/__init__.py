"""Ergonomics CLI handlers — approval commands, session management, recipes, permissions."""

from __future__ import annotations

# Re-export the real print_json at the package level so approval._PrintJsonProxy
# (which dispatches through ``_ergonomics.print_json``) resolves it, and so tests
# can patch ``teaagent.cli._handlers._ergonomics.print_json``. Must be the real
# implementation, not the proxy, to avoid recursion.
from teaagent.cli._handlers._misc import print_json

from .approval import (
    _DENIAL_REASON_DESCRIPTIONS,
    _build_explanation_summary,
    _parse_approval_arguments,
    _wrap_approval_store_errors,
    approval_approve_command,
    approval_audit_command,
    approval_check_command,
    approval_deny_command,
    approval_doctor_command,
    approval_explain_command,
    approval_grant_command,
    approval_list_command,
    approval_next_command,
    approval_pending_command,
    approval_preset_command,
    approval_revoke_command,
    approval_why_denied_command,
)
from .permissions import (
    _PERMISSION_MODE_GUIDE,
    permission_explain_command,
)
from .recipes import (
    ci_review_command,
    daily_journal_command,
    guidance_command,
    recipes_list_command,
    recipes_run_command,
    watch_command,
)
from .session import (
    _truncate_string,
    background_list_command,
    background_show_command,
    recall_command,
    session_list_command,
    session_resume_command,
    session_show_command,
    status_short_command,
    yesterday_command,
)

__all__ = [
    'approval_approve_command',
    'approval_audit_command',
    'approval_check_command',
    'approval_deny_command',
    'approval_doctor_command',
    'approval_explain_command',
    'approval_grant_command',
    'approval_list_command',
    'approval_next_command',
    'approval_pending_command',
    'approval_preset_command',
    'approval_revoke_command',
    'approval_why_denied_command',
    'background_list_command',
    'background_show_command',
    'ci_review_command',
    'daily_journal_command',
    'guidance_command',
    'permission_explain_command',
    'recall_command',
    'recipes_list_command',
    'recipes_run_command',
    'session_list_command',
    'session_resume_command',
    'session_show_command',
    'status_short_command',
    'watch_command',
    'yesterday_command',
    # Private utilities (may be imported by tests)
    '_truncate_string',
    '_parse_approval_arguments',
    '_wrap_approval_store_errors',
    '_build_explanation_summary',
    '_DENIAL_REASON_DESCRIPTIONS',
    '_PERMISSION_MODE_GUIDE',
    'print_json',
]
