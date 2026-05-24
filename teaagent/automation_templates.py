"""Built-in automation templates for teachable dry-run onboarding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from teaagent.automations import AutomationSpec


@dataclass(frozen=True)
class AutomationTemplate:
    name: str
    description: str
    defaults: dict[str, Any]

    def to_spec(self, **overrides: Any) -> AutomationSpec:
        payload = {
            'automation_id': '',
            **self.defaults,
            **overrides,
        }
        return AutomationSpec.from_dict(payload)


_TEMPLATES: dict[str, AutomationTemplate] = {
    'repo-watch': AutomationTemplate(
        name='repo-watch',
        description=(
            'Run a collector to detect new commits; wake the agent only when the '
            'repository changed.'
        ),
        defaults={
            'name': 'repo-watch',
            'task': (
                'When wake_agent is true, read the collector summary and write a '
                'one-paragraph changelog to automation-output.txt in the workspace root.'
            ),
            'schedule': 'every 30m',
            'permission_mode': 'read-only',
            'context_profile': 'lean',
            'acceptance_criteria': (
                'If wake_agent is false, no LLM run is started and no tokens are consumed. '
                'If wake_agent is true, automation-output.txt contains a non-empty summary.'
            ),
            'collector_command': ('python3 -m teaagent.collectors.repo_watch'),
            'allowed_toolsets': ['read-only'],
            'max_cost_cents': 25,
            'max_runtime_seconds': 300,
            'delivery': 'background_log',
        },
    ),
}


def list_automation_templates() -> list[AutomationTemplate]:
    return sorted(_TEMPLATES.values(), key=lambda item: item.name)


def get_automation_template(name: str) -> AutomationTemplate:
    key = name.strip().lower()
    template = _TEMPLATES.get(key)
    if template is None:
        known = ', '.join(sorted(_TEMPLATES)) or '(none)'
        raise KeyError(f"unknown automation template '{name}'; available: {known}")
    return template
