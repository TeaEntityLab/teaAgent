from __future__ import annotations

from pathlib import Path

from teaagent.automation_chain import (
    compose_chained_task,
    persist_automation_handoff,
    resolve_chained_task,
    validate_context_from,
)
from teaagent.automations import AutomationSpec, AutomationStore


def test_compose_chained_task_includes_upstream_summary() -> None:
    from teaagent.automation_chain import AutomationHandoff

    handoff = AutomationHandoff(
        automation_id='up-1',
        name='collector',
        last_status='collector_ok',
        summary='new commit abc1234',
        log_tail='',
        collector_summary='new commit abc1234',
    )
    task = compose_chained_task('Write triage notes.', handoff)
    assert 'abc1234' in task
    assert 'Write triage notes.' in task


def test_validate_context_from_requires_existing_automation(tmp_path: Path) -> None:
    spec = AutomationSpec(
        automation_id='down-1',
        name='triage',
        task='triage the upstream output with explicit acceptance checks',
        schedule='every 30m',
        context_from='missing-upstream',
    )
    errors = validate_context_from(spec, root=str(tmp_path))
    assert errors


def test_resolve_chained_task_uses_handoff_file(tmp_path: Path) -> None:
    store = AutomationStore(tmp_path)
    upstream = store.create(
        name='collector',
        task='collect git log and emit JSON summary for downstream automations',
        schedule='every 30m',
        provider=None,
        model=None,
        permission_mode='read-only',
        context_profile='lean',
        max_iterations=3,
        max_tool_calls=3,
    )
    persist_automation_handoff(
        tmp_path,
        upstream,
        collector_summary='commit abc1234 detected',
        summary='commit abc1234 detected',
    )
    downstream = AutomationSpec(
        automation_id='down-1',
        name='triage',
        task='Summarize whether we should wake the agent.',
        schedule='every 1h',
        context_from=upstream.automation_id,
    )
    task, handoff = resolve_chained_task(tmp_path, downstream)
    assert handoff is not None
    assert 'abc1234' in task
