"""Tests for skill activation record extraction (DSK-P1-002)."""

import tempfile

from teaagent.run_evidence import (
    SkillActivationRecord,
    extract_skill_activations,
)


def _skill_lifecycle_event(
    skill_name: str,
    to_state: str = 'activated',
    *,
    from_state: str = 'discovered',
    reason: str = '',
    source_path: str = '',
    created_at: float = 1717545600.0,
) -> dict:
    return {
        'event_type': 'skill_lifecycle_transition',
        'payload': {
            'skill_name': skill_name,
            'from_state': from_state,
            'to_state': to_state,
            'reason': reason,
            'source_path': source_path,
        },
        'created_at': created_at,
    }


def _skill_activated_event(
    skill_name: str,
    *,
    cause: str = 'explicit',
    source_path: str = '',
    created_at: float = 1717545600.0,
) -> dict:
    return {
        'event_type': 'skill_activated',
        'payload': {
            'skill_name': skill_name,
            'cause': cause,
            'source_path': source_path,
        },
        'created_at': created_at,
    }


def _tool_call_completed_event(
    tool_name: str,
    artifact_path: str = '',
) -> dict:
    result: dict = {}
    if artifact_path:
        result = {'artifact_path': artifact_path}
    return {
        'event_type': 'tool_call_completed',
        'payload': {
            'call_id': 'call-1',
            'tool_name': tool_name,
            'result': result,
        },
        'created_at': 1717545601.0,
    }


class TestExtractSkillActivations:
    def test_from_lifecycle_transitions(self):
        events = [
            _skill_lifecycle_event(
                'code-review',
                reason='first match in search order (eager load)',
                source_path='/skills/code-review/SKILL.md',
            ),
            _skill_lifecycle_event(
                'testing',
                reason='selected explicitly (--skill testing)',
                source_path='/skills/testing/SKILL.md',
            ),
        ]
        records = extract_skill_activations(events)
        assert len(records) == 2
        assert records[0].skill_name == 'code-review'
        assert records[0].activation_cause == 'auto'
        assert records[0].source_path == '/skills/code-review/SKILL.md'
        assert records[1].skill_name == 'testing'
        assert records[1].activation_cause == 'explicit'
        assert records[1].source_path == '/skills/testing/SKILL.md'

    def test_explicit_activation_cause(self):
        events = [
            _skill_lifecycle_event(
                'refactoring', reason='selected explicitly (--skill refactoring)'
            ),
        ]
        records = extract_skill_activations(events)
        assert len(records) == 1
        assert records[0].activation_cause == 'explicit'

    def test_auto_activation_cause(self):
        events = [
            _skill_lifecycle_event(
                'git-workflow', reason='first match in search order (eager load)'
            ),
        ]
        records = extract_skill_activations(events)
        assert len(records) == 1
        assert records[0].activation_cause == 'auto'

    def test_context_activation_cause(self):
        events = [
            _skill_lifecycle_event(
                'mcp-integration', reason='loaded from session context'
            ),
        ]
        records = extract_skill_activations(events)
        assert len(records) == 1
        assert records[0].activation_cause == 'context'

    def test_session_activation_cause(self):
        events = [
            _skill_lifecycle_event(
                'p0-agent-harness', reason='loaded from workspace config'
            ),
        ]
        records = extract_skill_activations(events)
        assert len(records) == 1
        assert records[0].activation_cause == 'session'

    def test_dedup_by_skill_name_first_wins(self):
        events = [
            _skill_lifecycle_event(
                'code-review', reason='eager load', created_at=100.0
            ),
            _skill_lifecycle_event(
                'code-review', reason='explicit selection', created_at=200.0
            ),
        ]
        records = extract_skill_activations(events)
        assert len(records) == 1
        assert records[0].activation_cause == 'auto'

    def test_skips_non_activated_transitions(self):
        events = [
            _skill_lifecycle_event('code-review', to_state='discovered'),
            _skill_lifecycle_event('code-review', to_state='selected'),
            _skill_lifecycle_event(
                'code-review', to_state='activated', reason='eager load'
            ),
        ]
        records = extract_skill_activations(events)
        assert len(records) == 1
        assert records[0].skill_name == 'code-review'

    def test_sku_activated_event_type(self):
        events = [
            _skill_activated_event(
                'custom-skill', cause='explicit', source_path='/custom/skill.md'
            ),
        ]
        records = extract_skill_activations(events)
        assert len(records) == 1
        assert records[0].skill_name == 'custom-skill'
        assert records[0].activation_cause == 'explicit'
        assert records[0].source_path == '/custom/skill.md'

    def test_skill_activated_event_with_cause_from_payload(self):
        events = [
            _skill_activated_event('auto-skill', cause='auto'),
            _skill_activated_event('ctx-skill', cause='context'),
            _skill_activated_event('sess-skill', cause='session'),
        ]
        records = extract_skill_activations(events)
        assert len(records) == 3
        causes = {r.activation_cause for r in records}
        assert causes == {'auto', 'context', 'session'}

    def test_empty_events(self):
        records = extract_skill_activations([])
        assert records == []

    def test_activated_at_is_iso_timestamp(self):
        events = [
            _skill_lifecycle_event(
                'code-review', reason='eager load', created_at=1717545600.0
            ),
        ]
        records = extract_skill_activations(events)
        assert len(records) == 1
        activated_at = records[0].activated_at
        assert 'T' in activated_at
        assert activated_at.endswith('+00:00') or activated_at.endswith('Z')

    def test_with_artifact_link_from_tool_call_completed(self):
        events = [
            _skill_lifecycle_event('code-review', reason='eager load'),
            _tool_call_completed_event(
                'code-review',
                artifact_path='.teaagent/artifacts/tool-results/run-1/call-1.txt',
            ),
        ]
        records = extract_skill_activations(events)
        assert len(records) == 1
        assert (
            records[0].output_artifact_link
            == '.teaagent/artifacts/tool-results/run-1/call-1.txt'
        )

    def test_without_artifact_link_when_no_match(self):
        events = [
            _skill_lifecycle_event('code-review', reason='eager load'),
            _tool_call_completed_event('other-tool', artifact_path='some/path.txt'),
        ]
        records = extract_skill_activations(events)
        assert len(records) == 1
        assert records[0].output_artifact_link is None

    def test_without_artifact_link_when_result_not_dict(self):
        events = [
            _skill_lifecycle_event('code-review', reason='eager load'),
            {
                'event_type': 'tool_call_completed',
                'payload': {
                    'call_id': 'call-1',
                    'tool_name': 'code-review',
                    'result': 'plain string result',
                },
                'created_at': 1717545601.0,
            },
        ]
        records = extract_skill_activations(events)
        assert len(records) == 1
        assert records[0].output_artifact_link is None

    def test_mixed_event_types_both_handled(self):
        events = [
            _skill_lifecycle_event(
                'code-review', reason='eager load', created_at=100.0
            ),
            _skill_activated_event('testing', cause='explicit', created_at=200.0),
        ]
        records = extract_skill_activations(events)
        assert len(records) == 2
        names = {r.skill_name for r in records}
        assert names == {'code-review', 'testing'}

    def test_dedup_across_event_types(self):
        events = [
            _skill_lifecycle_event(
                'code-review', reason='eager load', created_at=100.0
            ),
            _skill_activated_event('code-review', cause='explicit', created_at=200.0),
        ]
        records = extract_skill_activations(events)
        assert len(records) == 1
        assert records[0].activation_cause == 'auto'

    def test_default_activation_cause_is_auto(self):
        events = [
            _skill_lifecycle_event('unknown-skill', reason=''),
        ]
        records = extract_skill_activations(events)
        assert len(records) == 1
        assert records[0].activation_cause == 'auto'


class TestSkillActivationRecordSerialization:
    def test_to_dict(self):
        record = SkillActivationRecord(
            skill_name='code-review',
            activation_cause='explicit',
            source_path='/skills/code-review/SKILL.md',
            activated_at='2024-06-05T00:00:00+00:00',
            output_artifact_link='.teaagent/artifacts/tool-results/run-1/call-1.txt',
        )
        data = record.to_dict()
        assert data == {
            'skill_name': 'code-review',
            'activation_cause': 'explicit',
            'source_path': '/skills/code-review/SKILL.md',
            'activated_at': '2024-06-05T00:00:00+00:00',
            'output_artifact_link': '.teaagent/artifacts/tool-results/run-1/call-1.txt',
        }

    def test_to_dict_without_optional_fields(self):
        record = SkillActivationRecord(
            skill_name='testing',
            activation_cause='auto',
            source_path='',
            activated_at='2024-06-05T00:00:00+00:00',
        )
        data = record.to_dict()
        assert data['output_artifact_link'] is None


class TestRunEvidenceBundleSkillActivations:
    def test_bundle_includes_skill_activations_in_to_dict(self):
        from teaagent.run_evidence import RunEvidenceBundle

        bundle = RunEvidenceBundle(
            run_id='test-run-1',
            skill_activations=[
                SkillActivationRecord(
                    skill_name='code-review',
                    activation_cause='explicit',
                    source_path='/skills/code-review/SKILL.md',
                    activated_at='2024-06-05T00:00:00+00:00',
                ),
            ],
        )
        data = bundle.to_dict()
        assert 'skill_activations' in data
        assert len(data['skill_activations']) == 1
        assert data['skill_activations'][0]['skill_name'] == 'code-review'

    def test_bundle_build_includes_skill_activations(self):
        from teaagent.run_evidence import build_run_evidence_bundle

        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = build_run_evidence_bundle(tmpdir, 'nonexistent-run')
            assert bundle.skill_activations == []

    def test_bundle_serialization_empty_skill_activations(self):
        from teaagent.run_evidence import RunEvidenceBundle

        bundle = RunEvidenceBundle(run_id='test-run-2')
        data = bundle.to_dict()
        assert 'skill_activations' in data
        assert data['skill_activations'] == []
