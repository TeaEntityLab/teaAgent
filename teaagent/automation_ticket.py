"""Automation run-ticket validation and dry-run planning."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from teaagent.automation_chain import validate_context_from
from teaagent.automation_delivery import (
    resolve_automation_webhook_secret,
    resolve_automation_webhook_url,
)
from teaagent.automations import AutomationSpec, AutomationStore
from teaagent.provenance_gate import PersistenceSubstrate, canonical_content_digest
from teaagent.skill_loader import (
    discover_skill_index,
    estimate_skill_prompt_tokens,
    load_skills_with_report,
)

KNOWN_TOOLSETS = frozenset(
    {
        'read-only',
        'workspace-write',
        'shell-read',
        'shell-mutate',
        'network',
        'full',
    }
)
ALLOWED_DELIVERY_MODES = frozenset({'background_log', 'webhook', 'none'})
_PERMISSION_MODE_TOOLSETS: dict[str, tuple[str, ...]] = {
    'read-only': ('read-only',),
    'workspace-write': ('read-only', 'workspace-write'),
    'prompt': ('read-only', 'workspace-write'),
    'allow': ('read-only', 'workspace-write', 'shell-read', 'shell-mutate'),
    'danger-full-access': ('full',),
}

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
    allowed_toolsets: list[str]
    requires_subagent: bool
    max_cost_cents: int
    max_runtime_seconds: int
    delivery: str
    context_from: str
    provenance_digest: str
    upstream_handoff_preview: str

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
            'allowed_toolsets': list(self.allowed_toolsets),
            'requires_subagent': self.requires_subagent,
            'max_cost_cents': self.max_cost_cents,
            'max_runtime_seconds': self.max_runtime_seconds,
            'delivery': self.delivery,
            'context_from': self.context_from,
            'provenance_digest': self.provenance_digest,
            'upstream_handoff_preview': self.upstream_handoff_preview,
            'ready': not self.errors,
        }


def resolve_allowed_toolsets(spec: AutomationSpec) -> tuple[str, ...]:
    if spec.allowed_toolsets:
        return spec.allowed_toolsets
    return _PERMISSION_MODE_TOOLSETS.get(spec.permission_mode, ('read-only',))


def automation_provenance_payload(spec: AutomationSpec) -> dict[str, Any]:
    """Return all durable automation fields that shape authority or execution."""
    return {
        'name': spec.name,
        'task': spec.task,
        'schedule': spec.schedule,
        'provider': spec.provider,
        'model': spec.model,
        'permission_mode': spec.permission_mode,
        'context_profile': spec.context_profile,
        'max_iterations': spec.max_iterations,
        'max_tool_calls': spec.max_tool_calls,
        'auto_propose_skill': spec.auto_propose_skill,
        'selected_skills': list(spec.selected_skills),
        'acceptance_criteria': spec.acceptance_criteria,
        'collector_command': spec.collector_command,
        'no_agent': spec.no_agent,
        'allowed_toolsets': list(resolve_allowed_toolsets(spec)),
        'requires_subagent': spec.requires_subagent,
        'max_cost_cents': spec.max_cost_cents,
        'max_runtime_seconds': spec.max_runtime_seconds,
        'delivery': spec.delivery,
        'context_from': spec.context_from,
    }


def compute_automation_provenance_digest(spec: AutomationSpec) -> str:
    return canonical_content_digest(
        substrate=PersistenceSubstrate.AUTOMATION,
        payload=automation_provenance_payload(spec),
    )


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

    allowed_toolsets = list(resolve_allowed_toolsets(spec))
    unknown_toolsets = [
        name for name in spec.allowed_toolsets if name not in KNOWN_TOOLSETS
    ]
    if unknown_toolsets:
        errors.append(
            'unknown allowed_toolsets: '
            + ', '.join(unknown_toolsets)
            + f'; known: {", ".join(sorted(KNOWN_TOOLSETS))}'
        )
    if spec.max_cost_cents < 0:
        errors.append('max_cost_cents must be >= 0')
    if spec.max_runtime_seconds < 0:
        errors.append('max_runtime_seconds must be >= 0')
    delivery = spec.delivery.strip() or 'background_log'
    if delivery not in ALLOWED_DELIVERY_MODES:
        errors.append(
            f'delivery must be one of {", ".join(sorted(ALLOWED_DELIVERY_MODES))}'
        )
    if delivery == 'webhook' and not resolve_automation_webhook_url(root):
        errors.append(
            'delivery=webhook requires automation_webhook_url in '
            '.teaagent/config.toml or TEAAGENT_AUTOMATION_WEBHOOK_URL'
        )
    if (
        delivery == 'webhook'
        and resolve_automation_webhook_url(root)
        and not resolve_automation_webhook_secret(root)
    ):
        warnings.append(
            'delivery=webhook has no automation_webhook_secret; '
            'set TEAAGENT_AUTOMATION_WEBHOOK_SECRET for HMAC verification'
        )
    if spec.requires_subagent:
        warnings.append(
            'requires_subagent enables the subagent tool on automation agent ticks '
            '(max depth 1)'
        )
    errors.extend(validate_context_from(spec, root=root, store=AutomationStore(root)))
    upstream_handoff_preview = ''
    if spec.context_from.strip():
        from teaagent.automation_chain import load_automation_handoff

        handoff = load_automation_handoff(root, spec.context_from.strip())
        if handoff is None:
            warnings.append(
                f'context_from {spec.context_from.strip()} has no handoff file yet; '
                'run the upstream automation once before the downstream tick'
            )
        else:
            from teaagent.automation_chain import handoff_preview

            upstream_handoff_preview = handoff_preview(handoff)
    if not spec.max_cost_cents:
        warnings.append(
            'max_cost_cents is unset; add --max-cost-cents to cap spend per tick'
        )
    if not spec.max_runtime_seconds:
        warnings.append(
            'max_runtime_seconds is unset; add --max-runtime-seconds to cap wall time'
        )

    delivery_log_path = (
        f'.teaagent/background/automation:{spec.automation_id or "<new>"}.log'
    )
    provenance_digest = (
        spec.provenance_digest.strip() or compute_automation_provenance_digest(spec)
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
        allowed_toolsets=allowed_toolsets,
        requires_subagent=spec.requires_subagent,
        max_cost_cents=spec.max_cost_cents,
        max_runtime_seconds=spec.max_runtime_seconds,
        delivery=delivery,
        context_from=spec.context_from,
        provenance_digest=provenance_digest,
        upstream_handoff_preview=upstream_handoff_preview,
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
        f'Allowed toolsets: {", ".join(report.allowed_toolsets)}',
        f'Requires subagent: {report.requires_subagent}',
        f'Max cost (cents): {report.max_cost_cents or "(unset)"}',
        f'Max runtime (seconds): {report.max_runtime_seconds or "(unset)"}',
        f'Delivery: {report.delivery}',
        f'Provenance digest: {report.provenance_digest}',
        f'Background log path: {report.delivery_log_path}',
        '',
        'Task:',
        spec.task.strip(),
    ]
    if spec.acceptance_criteria.strip():
        lines.extend(['', 'Acceptance criteria:', spec.acceptance_criteria.strip()])
    if spec.context_from.strip():
        lines.extend(['', 'Context from:', spec.context_from.strip()])
    if report.upstream_handoff_preview:
        lines.extend(['', 'Upstream handoff preview:', report.upstream_handoff_preview])
    if spec.collector_command.strip():
        lines.extend(['', 'Collector command:', spec.collector_command.strip()])
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
    template: str = '',
) -> dict[str, Any]:
    report = validate_automation_spec(spec, root=root, require_acceptance_criteria=True)
    automation_payload = {
        **spec.to_dict(),
        'provenance_digest': report.provenance_digest,
        'allowed_toolsets': report.allowed_toolsets,
    }
    payload: dict[str, Any] = {
        'status': 'dry_run',
        'automation': automation_payload,
        'ticket': report.to_dict(),
    }
    if template:
        payload['template'] = template
    if human:
        payload['human'] = format_automation_ticket_human(spec, report)
    return payload
