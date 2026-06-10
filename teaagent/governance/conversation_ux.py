"""General-user conversation UX helpers (WDC-002 / WDC-003)."""

from __future__ import annotations

from typing import Any

CORE_ONBOARDING_CONCEPTS: tuple[str, ...] = ('ask', 'approve', 'undo')

ADVANCED_CONCEPTS: tuple[str, ...] = (
    'receipt',
    'budget',
    'tenant',
    'trust tier',
    'envelope',
    'cockpit',
)


def plain_approval_prompt(tool_name: str, call_id: str) -> str:
    return (
        f'TeaAgent wants to run "{tool_name}" (call {call_id}). '
        'Approve once, approve for session, or deny?'
    )


def plain_run_receipt_summary(*, status: str, goal: str = '') -> str:
    goal_part = f' for "{goal}"' if goal else ''
    return f'Your run{goal_part} finished with status: {status}.'


def progressive_disclosure_sections(*, include_advanced: bool = False) -> list[str]:
    sections = [
        'Core loop: ask → approve → undo',
        '  ask: describe what you want changed',
        '  approve: confirm destructive tool calls',
        '  undo: restore files if something went wrong',
    ]
    if include_advanced:
        sections.append('Advanced (optional): receipts, budgets, tenants, trust tiers')
    return sections


def stranger_concept_count(*, include_advanced: bool = False) -> int:
    return len(CORE_ONBOARDING_CONCEPTS) + (
        len(ADVANCED_CONCEPTS) if include_advanced else 0
    )


def format_approval_prompt_human(
    tool_name: str,
    call_id: str,
    arguments: dict[str, Any] | None = None,
    *,
    json_mode: bool = False,
) -> str:
    if json_mode:
        import json

        payload = {
            'tool_name': tool_name,
            'call_id': call_id,
            'arguments': arguments or {},
        }
        return json.dumps(payload)
    return plain_approval_prompt(tool_name, call_id)
