from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from teaagent.skill_lifecycle import (
    SkillLifecycleState,
    SkillLifecycleTracker,
    classify_governance_status,
)
from teaagent.skill_loader import explain_skill_activation


def _install_skill(base: Path, rel_dir: str, name: str, body: str) -> Path:
    skill_dir = base / rel_dir / name
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / 'SKILL.md'
    skill_md.write_text(
        f'---\nname: {name}\ndescription: {name} skill\n---\n{body}\n',
        encoding='utf-8',
    )
    return skill_dir


def _install_candidate_skill(base: Path, rel_dir: str, name: str, body: str) -> Path:
    skill_dir = base / rel_dir / name
    skill_dir.mkdir(parents=True)
    (skill_dir / 'SKILL.md').write_text(
        f'---\nname: {name}\ndescription: {name} skill\n---\n{body}\n',
        encoding='utf-8',
    )
    (skill_dir / 'REFERENCE.md').write_text(f'# {name}\n\nReference\n', encoding='utf-8')
    (skill_dir / 'tool_call_contract.json').write_text(
        json.dumps({
            'schema_version': 1,
            'skill_name': name,
            'allowed_toolsets': ['read-only'],
            'requires_approval_for': ['write', 'shell', 'network'],
        }),
        encoding='utf-8',
    )
    (skill_dir / 'cost_profile.json').write_text(
        json.dumps({'schema_version': 1, 'skill_name': name, 'max_prompt_tokens': 4096, 'profile': 'conservative'}),
        encoding='utf-8',
    )
    (skill_dir / 'interaction_policy.json').write_text(
        json.dumps({
            'schema_version': 1,
            'skill_name': name,
            'trust_level': 'quarantine',
            'auto_invoke': False,
            'user_visible_rationale_required': True,
        }),
        encoding='utf-8',
    )
    (skill_dir / 'provenance.json').write_text(
        json.dumps({
            'schema_version': 1,
            'install_scope': 'project',
            'installed_via': 'candidate',
            'trust_level': 'quarantine',
        }),
        encoding='utf-8',
    )
    # Pre-compute digest for provenance validation
    from teaagent.provenance_gate import PersistenceSubstrate, canonical_content_digest
    from teaagent.skill_candidate_artifacts import candidate_bundle_digest

    provenance_path = skill_dir / 'provenance.json'
    payload = {'schema_version': 1, 'install_scope': 'project', 'installed_via': 'candidate', 'trust_level': 'quarantine'}
    digest = canonical_content_digest(substrate=PersistenceSubstrate.SKILL_CANDIDATE, payload=payload)
    proven = json.loads(provenance_path.read_text(encoding='utf-8'))
    proven['content_digest'] = candidate_bundle_digest(skill_dir)
    proven['gate_content_digest'] = digest
    provenance_path.write_text(json.dumps(proven, indent=2), encoding='utf-8')
    return skill_dir


# ---------------------------------------------------------------------------
# SkillLifecycleState enum
# ---------------------------------------------------------------------------


def test_lifecycle_state_string_values() -> None:
    assert str(SkillLifecycleState.DISCOVERED) == 'discovered'
    assert str(SkillLifecycleState.ACTIVATED) == 'activated'
    assert str(SkillLifecycleState.SUPERSEDED) == 'superseded'
    assert str(SkillLifecycleState.BLOCKED) == 'blocked'


def test_lifecycle_state_equality() -> None:
    assert SkillLifecycleState.DISCOVERED == SkillLifecycleState.DISCOVERED
    assert SkillLifecycleState.ACTIVATED != SkillLifecycleState.BLOCKED


# ---------------------------------------------------------------------------
# SkillLifecycleTracker — audit recording
# ---------------------------------------------------------------------------


def test_tracker_records_transition_via_audit() -> None:
    mock_audit = MagicMock()
    tracker = SkillLifecycleTracker(audit_logger=mock_audit, run_id='run-1')

    tracker.transition('alpha', SkillLifecycleState.DISCOVERED.value, reason='found', source_path='/a/b')

    mock_audit.record.assert_called_once_with(
        'skill_lifecycle_transition',
        'run-1',
        skill_name='alpha',
        from_state='unknown',
        to_state='discovered',
        reason='found',
        source_path='/a/b',
    )


def test_tracker_tracks_from_state_correctly() -> None:
    mock_audit = MagicMock()
    tracker = SkillLifecycleTracker(audit_logger=mock_audit, run_id='run-2')

    tracker.transition('alpha', SkillLifecycleState.DISCOVERED.value)
    tracker.transition('alpha', SkillLifecycleState.ACTIVATED.value, reason='loaded')

    assert mock_audit.record.call_count == 2
    second_call = mock_audit.record.call_args_list[1]
    assert second_call.kwargs['from_state'] == 'discovered'
    assert second_call.kwargs['to_state'] == 'activated'


def test_tracker_no_audit_does_not_raise() -> None:
    tracker = SkillLifecycleTracker(audit_logger=None, run_id='')
    tracker.transition('alpha', SkillLifecycleState.DISCOVERED.value)
    assert tracker.current_state('alpha') == 'discovered'


def test_tracker_set_state_without_event() -> None:
    mock_audit = MagicMock()
    tracker = SkillLifecycleTracker(audit_logger=mock_audit, run_id='run-3')

    tracker.set_state('beta', SkillLifecycleState.DISCOVERED.value)
    assert tracker.current_state('beta') == 'discovered'
    mock_audit.record.assert_not_called()


def test_tracker_current_state_unknown_for_untracked() -> None:
    tracker = SkillLifecycleTracker()
    assert tracker.current_state('nonexistent') == 'unknown'


def test_tracker_all_states_returns_copy() -> None:
    tracker = SkillLifecycleTracker()
    tracker.set_state('alpha', 'discovered')
    tracker.set_state('beta', 'activated')

    states = tracker.all_states()
    assert states == {'alpha': 'discovered', 'beta': 'activated'}
    states['gamma'] = 'blocked'
    assert 'gamma' not in tracker.all_states()


# ---------------------------------------------------------------------------
# Governance status classification (DSK-P0-006)
# ---------------------------------------------------------------------------


def test_governance_candidate_installed(tmp_path: Path) -> None:
    root = tmp_path / 'workspace'
    root.mkdir()
    skill_dir = _install_candidate_skill(root, '.config/agent/skills', 'my-skill', 'Body ' * 20)
    source_dir = skill_dir.parent

    status = classify_governance_status(skill_dir=skill_dir, source_dir=source_dir, root=root)
    assert status == 'candidate_installed'


def test_governance_direct_write_primary_project(tmp_path: Path) -> None:
    root = tmp_path / 'workspace'
    root.mkdir()
    skill_dir = _install_skill(root, '.config/agent/skills', 'my-skill', 'Body ' * 20)
    source_dir = skill_dir.parent

    status = classify_governance_status(skill_dir=skill_dir, source_dir=source_dir, root=root)
    assert status == 'direct_write'


def test_governance_direct_write_opencode_skill(tmp_path: Path) -> None:
    root = tmp_path / 'workspace'
    root.mkdir()
    skill_dir = _install_skill(root, '.opencode/skill', 'my-skill', 'Body ' * 20)
    source_dir = skill_dir.parent

    status = classify_governance_status(skill_dir=skill_dir, source_dir=source_dir, root=root)
    assert status == 'direct_write'


def test_governance_compatibility_path_claude(tmp_path: Path) -> None:
    root = tmp_path / 'workspace'
    root.mkdir()
    skill_dir = _install_skill(root, '.claude/skills', 'my-skill', 'Body ' * 20)
    source_dir = skill_dir.parent

    status = classify_governance_status(skill_dir=skill_dir, source_dir=source_dir, root=root)
    assert status == 'compatibility_path'


def test_governance_compatibility_path_opencode_skills(tmp_path: Path) -> None:
    root = tmp_path / 'workspace'
    root.mkdir()
    skill_dir = _install_skill(root, '.opencode/skills', 'my-skill', 'Body ' * 20)
    source_dir = skill_dir.parent

    status = classify_governance_status(skill_dir=skill_dir, source_dir=source_dir, root=root)
    assert status == 'compatibility_path'


def test_governance_unmanaged_extra_dir(tmp_path: Path) -> None:
    root = tmp_path / 'workspace'
    root.mkdir()
    extra_dir = tmp_path / 'custom-skills'
    extra_dir.mkdir()
    skill_dir = _install_skill(tmp_path, 'custom-skills', 'my-skill', 'Body ' * 20)
    source_dir = extra_dir

    status = classify_governance_status(skill_dir=skill_dir, source_dir=source_dir, root=root)
    assert status == 'unmanaged'


def test_governance_unmanaged_codex_dir(tmp_path: Path) -> None:
    root = tmp_path / 'workspace'
    root.mkdir()
    skill_dir = _install_skill(root, '.codex/skills', 'my-skill', 'Body ' * 20)
    source_dir = skill_dir.parent

    status = classify_governance_status(skill_dir=skill_dir, source_dir=source_dir, root=root)
    assert status == 'unmanaged'


# ---------------------------------------------------------------------------
# Integration: explain_skill_activation with lifecycle tracker
# ---------------------------------------------------------------------------


def test_explain_output_includes_lifecycle_state(tmp_path: Path) -> None:
    _install_skill(tmp_path, '.config/agent/skills', 'alpha', 'Alpha ' * 50)
    report = explain_skill_activation(tmp_path, selected_names=frozenset({'alpha'}))
    assert len(report.loaded) == 1
    assert report.loaded[0].lifecycle_state == 'activated'

    d = report.to_dict()
    loaded_list = d['loaded']
    assert isinstance(loaded_list, list)
    assert loaded_list[0]['lifecycle_state'] == 'activated'


def test_explain_with_lifecycle_tracker_emits_transitions(tmp_path: Path) -> None:
    _install_skill(tmp_path, '.config/agent/skills', 'alpha', 'Alpha ' * 50)
    _install_skill(tmp_path, '.claude/skills', 'beta', 'Beta ' * 50)

    mock_audit = MagicMock()
    tracker = SkillLifecycleTracker(audit_logger=mock_audit, run_id='run-int')

    report = explain_skill_activation(
        tmp_path,
        selected_names=frozenset({'alpha', 'beta'}),
        lifecycle_tracker=tracker,
    )
    assert len(report.loaded) == 2

    call_kwargs = [call.kwargs for call in mock_audit.record.call_args_list]

    transition_calls = [
        kw for kw in call_kwargs
        if kw.get('to_state') == 'activated'
    ]
    assert len(transition_calls) == 2  # one per loaded skill


def test_explain_lifecycle_tracker_sets_discovered_and_activated(tmp_path: Path) -> None:
    _install_skill(tmp_path, '.config/agent/skills', 'alpha', 'Alpha ' * 50)

    tracker = SkillLifecycleTracker(audit_logger=None, run_id='')
    explain_skill_activation(
        tmp_path,
        selected_names=frozenset({'alpha'}),
        lifecycle_tracker=tracker,
    )

    assert tracker.current_state('alpha') == 'activated'


def test_explain_governance_status_in_output(tmp_path: Path) -> None:
    _install_skill(tmp_path, '.config/agent/skills', 'alpha', 'Alpha ' * 50)
    _install_skill(tmp_path, '.claude/skills', 'beta', 'Beta ' * 50)

    report = explain_skill_activation(
        tmp_path,
        selected_names=frozenset({'alpha', 'beta'}),
    )
    d = report.to_dict()

    loaded_by_name = {item['name']: item for item in d['loaded']}
    assert loaded_by_name['alpha']['governance_status'] == 'direct_write'
    assert loaded_by_name['beta']['governance_status'] == 'compatibility_path'


def test_explain_governance_candidate_installed_in_output(tmp_path: Path) -> None:
    _install_candidate_skill(tmp_path, '.config/agent/skills', 'managed', 'Managed ' * 20)

    report = explain_skill_activation(
        tmp_path,
        selected_names=frozenset({'managed'}),
    )
    d = report.to_dict()
    assert len(d['loaded']) == 1
    assert d['loaded'][0]['governance_status'] == 'candidate_installed'


def test_explain_governance_unmanaged_in_output(tmp_path: Path) -> None:
    root = tmp_path / 'workspace'
    root.mkdir()
    _install_skill(root, '.codex/skills', 'ext-skill', 'Extended ' * 20)

    report = explain_skill_activation(
        root,
        selected_names=frozenset({'ext-skill'}),
        source_profile='extended',
    )
    d = report.to_dict()
    assert len(d['loaded']) == 1
    assert d['loaded'][0]['governance_status'] == 'unmanaged'


def test_explain_without_tracker_still_reports_lifecycle(tmp_path: Path) -> None:
    _install_skill(tmp_path, '.config/agent/skills', 'alpha', 'Alpha ' * 50)
    report = explain_skill_activation(tmp_path, selected_names=frozenset({'alpha'}))
    assert report.loaded[0].lifecycle_state == 'activated'
