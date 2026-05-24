from __future__ import annotations

from pathlib import Path

from teaagent.automation_ticket import (
    build_automation_dry_run_payload,
    compute_automation_provenance_digest,
    resolve_allowed_toolsets,
    validate_automation_spec,
    validate_automation_task,
)
from teaagent.automations import AutomationSpec


def _spec(**overrides: object) -> AutomationSpec:
    base = {
        'automation_id': 'a1',
        'name': 'doc-check',
        'task': 'Run scripts/refresh_competitive_docs.py --check and report drift.',
        'schedule': 'every 30m',
        'acceptance_criteria': 'Command exits 0 and prints Competitive docs check passed.',
        'selected_skills': (),
    }
    base.update(overrides)
    return AutomationSpec.from_dict(base)


def test_validate_automation_task_rejects_vague_prompt() -> None:
    errors = validate_automation_task('照你知道的做，延續上次對話')
    assert errors


def test_validate_automation_spec_requires_acceptance_criteria_on_dry_run(
    tmp_path: Path,
) -> None:
    spec = _spec(acceptance_criteria='')
    report = validate_automation_spec(
        spec, root=str(tmp_path), require_acceptance_criteria=True
    )
    assert any('acceptance_criteria' in err for err in report.errors)


def test_build_automation_dry_run_payload_marks_ready(tmp_path: Path) -> None:
    payload = build_automation_dry_run_payload(_spec(), root=str(tmp_path))
    assert payload['ticket']['ready'] is True
    assert payload['ticket']['estimated_skill_tokens'] == 0


def test_unknown_selected_skill_fails_dry_run(tmp_path: Path) -> None:
    payload = build_automation_dry_run_payload(
        _spec(selected_skills=('missing-skill',)),
        root=str(tmp_path),
    )
    assert payload['ticket']['ready'] is False
    assert any('unknown selected_skills' in err for err in payload['ticket']['errors'])


def test_resolve_allowed_toolsets_from_permission_mode() -> None:
    spec = _spec(permission_mode='read-only', allowed_toolsets=())
    assert resolve_allowed_toolsets(spec) == ('read-only',)


def test_compute_automation_provenance_digest_is_stable() -> None:
    spec = _spec()
    first = compute_automation_provenance_digest(spec)
    second = compute_automation_provenance_digest(spec)
    assert first == second
    assert first.startswith('sha256:')


def test_compute_automation_provenance_digest_covers_authority_fields() -> None:
    baseline = compute_automation_provenance_digest(_spec())
    variants = [
        _spec(collector_command='python3 collector.py'),
        _spec(no_agent=True),
        _spec(delivery='none'),
        _spec(selected_skills=('security-review',)),
        _spec(context_from='upstream-1'),
        _spec(max_cost_cents=42),
        _spec(max_runtime_seconds=60),
        _spec(requires_subagent=True),
        _spec(permission_mode='allow'),
    ]
    assert all(
        compute_automation_provenance_digest(item) != baseline for item in variants
    )


def test_unknown_allowed_toolset_fails_dry_run(tmp_path: Path) -> None:
    payload = build_automation_dry_run_payload(
        _spec(allowed_toolsets=('not-a-real-toolset',)),
        root=str(tmp_path),
    )
    assert payload['ticket']['ready'] is False
    assert any('unknown allowed_toolsets' in err for err in payload['ticket']['errors'])


def test_collector_policy_fails_dry_run_for_network_command(tmp_path: Path) -> None:
    payload = build_automation_dry_run_payload(
        _spec(collector_command='curl https://example.com/feed.json'),
        root=str(tmp_path),
    )
    assert payload['ticket']['ready'] is False
    assert any('collector_command' in err for err in payload['ticket']['errors'])
