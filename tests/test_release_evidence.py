"""Tests for release evidence bundle generation."""

import json

from teaagent.release_evidence import (
    ReleaseEvidenceBundle,
    _check_dynamic_skill,
    _check_human_review,
    _check_loop_goal,
    _check_model_routing,
    _check_precise_memory,
    _check_spec_first,
    _check_synthesis_review,
    _collect_seven_loop_evidence,
    build_release_evidence_bundle,
    write_release_evidence_bundle,
)


def test_build_release_evidence_bundle(tmp_path):
    bundle = build_release_evidence_bundle(profile='counts-only', root=tmp_path)
    assert isinstance(bundle, ReleaseEvidenceBundle)
    # In a bare tmp_path, git fails (no repo) and no loops are verified
    assert bundle.commands_ok is True  # no commands run in counts-only
    assert bundle.collection_ok is False  # no git commit in bare tmp_path
    assert bundle.evidence_complete is False  # no loops verified
    assert bundle.ok is False  # overall: False when collection + evidence fail
    assert bundle.run_profile == 'counts-only'
    assert bundle.repo_root == str(tmp_path.resolve())
    assert 'python_version' in bundle.platform
    assert 'os' in bundle.platform
    assert 'branch' in bundle.git
    assert 'commit' in bundle.git
    assert 'dirty' in bundle.git
    assert 'tags' in bundle.git
    assert isinstance(bundle.pytest_counts, dict)
    assert isinstance(bundle.seven_loop_evidence, dict)
    assert len(bundle.seven_loop_evidence) == 7
    assert isinstance(bundle.commands, list)
    assert isinstance(bundle.artifacts, list)


def test_release_evidence_seven_loop_fields(tmp_path):
    bundle = build_release_evidence_bundle(profile='counts-only', root=tmp_path)
    loops = bundle.seven_loop_evidence

    expected = {
        'spec_first',
        'dynamic_skill',
        'loop_goal',
        'model_routing',
        'synthesis_review',
        'precise_memory',
        'human_review',
    }
    assert set(loops.keys()) == expected

    for name, evidence in loops.items():
        assert evidence['name'] == name
        assert evidence['status'] in ('verified', 'partial', 'not_tested')
        assert isinstance(evidence['receipts'], list)
        assert isinstance(evidence.get('trace_id', ''), str)

def test_seven_loop_spec_first_trace(tmp_path):
    """Verify that _check_spec_first returns a trace_id pointing to the source file."""
    governance = tmp_path / 'docs' / 'governance'
    governance.mkdir(parents=True)
    plan_file = governance / 'plan-gate.md'
    plan_file.write_text('plan gate artifact')
    mtime = plan_file.stat().st_mtime

    result = _check_spec_first(tmp_path)
    assert result['name'] == 'spec_first'
    assert result['status'] in ('partial', 'verified')
    assert f'plan-gate.md:{mtime:.0f}' in result.get('trace_id', '')


def test_seven_loop_dynamic_skill(tmp_path):
    result = _check_dynamic_skill(tmp_path)
    assert result['name'] == 'dynamic_skill'
    assert result['status'] in ('not_tested', 'partial', 'verified')


def test_seven_loop_loop_goal(tmp_path):
    result = _check_loop_goal(tmp_path)
    assert result['name'] == 'loop_goal'
    assert result['status'] in ('not_tested', 'partial', 'verified')


def test_seven_loop_model_routing(tmp_path):
    result = _check_model_routing(tmp_path)
    assert result['name'] == 'model_routing'
    assert result['status'] in ('not_tested', 'partial', 'verified')


def test_seven_loop_synthesis_review(tmp_path):
    governance = tmp_path / 'docs' / 'governance'
    governance.mkdir(parents=True)
    (governance / 'review-checklist.md').write_text('review checklist')

    result = _check_synthesis_review(tmp_path)
    assert result['name'] == 'synthesis_review'
    assert result['status'] in ('partial', 'verified')
    assert any('review' in r.lower() for r in result['receipts'])


def test_seven_loop_precise_memory(tmp_path):
    result = _check_precise_memory(tmp_path)
    assert result['name'] == 'precise_memory'
    assert result['status'] in ('not_tested', 'partial', 'verified')


def test_seven_loop_human_review(tmp_path):
    result = _check_human_review(tmp_path)
    assert result['name'] == 'human_review'
    assert result['status'] in ('not_tested', 'partial', 'verified')


def test_write_release_evidence_bundle(tmp_path):
    bundle = build_release_evidence_bundle(profile='counts-only', root=tmp_path)
    output = tmp_path / 'output' / 'release-evidence.json'
    result = write_release_evidence_bundle(bundle, output)

    assert result == output
    assert result.is_file()

    data = json.loads(output.read_text(encoding='utf-8'))
    assert data['ok'] == bundle.ok
    assert data['commands_ok'] == bundle.commands_ok
    assert data['collection_ok'] == bundle.collection_ok
    assert data['evidence_complete'] == bundle.evidence_complete
    assert data['run_profile'] == bundle.run_profile
    assert data['repo_root'] == bundle.repo_root
    assert len(data['seven_loop_evidence']) == 7


def test_collect_seven_loop_evidence_returns_all_loops(tmp_path):
    result = _collect_seven_loop_evidence(tmp_path)
    assert len(result) == 7
    for name in (
        'spec_first',
        'dynamic_skill',
        'loop_goal',
        'model_routing',
        'synthesis_review',
        'precise_memory',
        'human_review',
    ):
        assert name in result
        assert result[name]['name'] == name
        assert result[name]['status'] in ('verified', 'partial', 'not_tested')


def test_write_bundle_creates_parent_dirs(tmp_path):
    bundle = build_release_evidence_bundle(profile='counts-only', root=tmp_path)
    output = tmp_path / 'deep' / 'nested' / 'dir' / 'evidence.json'
    result = write_release_evidence_bundle(bundle, output)
    assert result.is_file()
    assert json.loads(result.read_text(encoding='utf-8'))['ok'] is False
