"""Automation run-ticket validation and dry-run planning."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from teaagent.automations import AutomationSpec
from teaagent.skill_loader import (
    discover_skill_index,
    estimate_skill_prompt_tokens,
    load_skills_with_report,
)

_VAGUE_TASK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r'看之前(?:的)?對話', re.IGNORECASE),
    re.compile(r'照你知道的做', re.IGNORECASE),
    re.compile(
        r'continue\s+from\s+(?:our\s+)?(?:last|previous)\s+(?:chat|conversation)',
        re.IGNORECASE,
    ),
    re.compile(r'as\s+we\s+discussed', re.IGNORECASE),
    re.compile(r'like\s+before', re.IGNORECASE),
    re.compile(r'you\s+already\s+know', re.IGNORECASE),
    re.compile(r'use\s+the\s+context\s+from\s+before', re.IGNORECASE),
    re.compile(r'follow\s+up\s+on\s+(?:that|our)\s+(?:chat|thread)', re.IGNORECASE),
)


@dataclass(frozen=True)
class AutomationTicketReport:
    errors: list[str]
    warnings: list[str]
    selected_skills: list[str]
    skill_index_count: int
    estimated_skill_tokens: int
    permission_mode: str
    context_profile: str
    delivery_log_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'errors': list(self.errors),
            'warnings': list(self.warnings),
            'selected_skills': list(self.selected_skills),
            'skill_index_count': self.skill_index_count,
            'estimated_skill_tokens': self.estimated_skill_tokens,
            'permission_mode': self.permission_mode,
            'context_profile': self.context_profile,
            'delivery_log_path': self.delivery_log_path,
            'ready': not self.errors,
        }


def validate_automation_task(task: str) -> list[str]:
    errors: list[str] = []
    normalized = task.strip()
    if not normalized:
        errors.append('automation task cannot be empty')
        return errors
    if len(normalized) < 8:
        errors.append(
            'automation task is too short; describe the goal, inputs, and expected output '
            'without referring to prior chat history'
        )
    for pattern in _VAGUE_TASK_PATTERNS:
        if pattern.search(normalized):
            errors.append(
                f'automation task is not self-contained ({pattern.pattern}); '
                'include explicit files, commands, and acceptance criteria in the prompt'
            )
            break
    return errors


def validate_automation_spec(
    spec: AutomationSpec,
    *,
    root: str,
    require_acceptance_criteria: bool = False,
) -> AutomationTicketReport:
    errors: list[str] = []
    warnings: list[str] = []
    errors.extend(validate_automation_task(spec.task))
    criteria = spec.acceptance_criteria.strip()
    if require_acceptance_criteria and not criteria:
        errors.append(
            'acceptance_criteria is required for automation dry-run; '
            'pass --acceptance-criteria with observable pass/fail checks'
        )
    elif not criteria:
        warnings.append(
            'acceptance_criteria is empty; add --acceptance-criteria before enabling production schedules'
        )

    index = discover_skill_index(root)
    index_names = {entry.name for entry in index}
    selected = list(spec.selected_skills)
    unknown = [name for name in selected if name not in index_names]
    if unknown:
        errors.append(
            'unknown selected_skills: '
            + ', '.join(unknown)
            + f'; available: {", ".join(sorted(index_names)) or "(none)"}'
        )

    selected_set = frozenset(selected)
    skill_report = load_skills_with_report(root, selected_names=selected_set)
    estimated_tokens = estimate_skill_prompt_tokens(skill_report.skills)

    if selected_set and not skill_report.skills:
        errors.append('selected_skills did not load any skill content')

    delivery_log_path = (
        f'.teaagent/background/automation:{spec.automation_id or "<new>"}.log'
    )
    return AutomationTicketReport(
        errors=errors,
        warnings=warnings,
        selected_skills=selected,
        skill_index_count=len(index),
        estimated_skill_tokens=estimated_tokens,
        permission_mode=spec.permission_mode,
        context_profile=spec.context_profile,
        delivery_log_path=delivery_log_path,
    )


def format_automation_ticket_human(
    spec: AutomationSpec, report: AutomationTicketReport
) -> str:
    lines = [
        f'Automation: {spec.name}',
        f'Schedule: {spec.schedule}',
        f'Permission mode: {report.permission_mode}',
        f'Context profile: {report.context_profile}',
        f'Selected skills: {", ".join(report.selected_skills) or "(none — no eager skill prompt bloat)"}',
        f'Skill index discovered: {report.skill_index_count}',
        f'Estimated skill prompt tokens: {report.estimated_skill_tokens}',
        f'Background log path: {report.delivery_log_path}',
        '',
        'Task:',
        spec.task.strip(),
    ]
    if spec.acceptance_criteria.strip():
        lines.extend(['', 'Acceptance criteria:', spec.acceptance_criteria.strip()])
    if report.warnings:
        lines.extend(['', 'Warnings:'])
        lines.extend(f'- {item}' for item in report.warnings)
    if report.errors:
        lines.extend(['', 'Errors:'])
        lines.extend(f'- {item}' for item in report.errors)
    else:
        lines.append('')
        lines.append('Dry-run: ready (no model invocation).')
    return '\n'.join(lines)


def build_automation_dry_run_payload(
    spec: AutomationSpec,
    *,
    root: str,
    human: bool = False,
) -> dict[str, Any]:
    report = validate_automation_spec(spec, root=root, require_acceptance_criteria=True)
    payload: dict[str, Any] = {
        'status': 'dry_run',
        'automation': spec.to_dict(),
        'ticket': report.to_dict(),
    }
    if human:
        payload['human'] = format_automation_ticket_human(spec, report)
    return payload
