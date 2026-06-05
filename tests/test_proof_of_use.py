from teaagent.proof_of_use import (
    ProofOfUse,
    ProofOfUseBundle,
    build_proof_of_use,
    emit_proof_of_use_audit,
)


def test_proof_of_use_to_dict():
    proof = ProofOfUse(
        source_skill_name='p0-agent-harness',
        source_artifact_path='/path/to/SKILL.md',
        tool_call_id='call-123',
        tool_name='execute_skill',
        output_hash='sha256:abcdef',
        verified=True,
        verified_at='2026-06-05T00:00:00+00:00',
    )
    d = proof.to_dict()
    assert d['source_skill_name'] == 'p0-agent-harness'
    assert d['source_artifact_path'] == '/path/to/SKILL.md'
    assert d['tool_call_id'] == 'call-123'
    assert d['tool_name'] == 'execute_skill'
    assert d['output_hash'] == 'sha256:abcdef'
    assert d['verified'] is True
    assert d['verified_at'] == '2026-06-05T00:00:00+00:00'


def test_proof_of_use_defaults():
    proof = ProofOfUse(
        source_skill_name='test-skill',
        source_artifact_path='',
        tool_call_id='c1',
        tool_name='t1',
        output_hash='sha256:1234',
    )
    assert proof.verified is False
    assert proof.verified_at == ''


def test_bundle_to_dict_empty():
    bundle = ProofOfUseBundle()
    d = bundle.to_dict()
    assert d['proofs'] == []
    assert d['final_answer_hash'] == ''
    assert d['final_answer_preview'] == ''


def test_bundle_to_dict_with_proofs():
    bundle = ProofOfUseBundle(
        proofs=[
            ProofOfUse(
                source_skill_name='code-review',
                source_artifact_path='/p/SKILL.md',
                tool_call_id='c1',
                tool_name='review',
                output_hash='sha256:abcd',
            )
        ],
        final_answer_hash='sha256:fa',
        final_answer_preview='All tests passed.',
    )
    d = bundle.to_dict()
    assert len(d['proofs']) == 1
    assert d['final_answer_hash'] == 'sha256:fa'
    assert d['final_answer_preview'] == 'All tests passed.'


def test_build_proof_of_use_empty_events():
    bundle = build_proof_of_use([], 'final answer text')
    assert bundle.proofs == []
    assert bundle.final_answer_hash.startswith('sha256:')
    assert bundle.final_answer_preview == 'final answer text'


def test_build_proof_of_use_with_skill_lifecycle():
    events = [
        {
            'event_type': 'skill_lifecycle_transition',
            'payload': {
                'skill_name': 'p0-agent-harness',
                'from_state': 'activated',
                'to_state': 'used_in_run',
                'source_path': '/skills/p0-agent-harness/SKILL.md',
            },
        },
        {
            'event_type': 'tool_call_completed',
            'payload': {
                'call_id': 'call-1',
                'tool_name': 'p0-agent-harness_check',
                'result': 'OK: all checks passed',
            },
        },
    ]
    bundle = build_proof_of_use(events, 'Answer: harness ready.')
    assert len(bundle.proofs) == 1
    p = bundle.proofs[0]
    assert p.source_skill_name == 'p0-agent-harness'
    assert p.tool_call_id == 'call-1'
    assert p.tool_name == 'p0-agent-harness_check'
    assert p.output_hash.startswith('sha256:')
    assert p.verified is False


def test_build_proof_of_use_output_verified():
    events = [
        {
            'event_type': 'skill_lifecycle_transition',
            'payload': {
                'skill_name': 'testing',
                'from_state': 'activated',
                'to_state': 'used_in_run',
                'source_path': '/skills/testing/SKILL.md',
            },
        },
        {
            'event_type': 'skill_lifecycle_transition',
            'payload': {
                'skill_name': 'testing',
                'from_state': 'used_in_run',
                'to_state': 'output_verified',
                'source_path': '/skills/testing/SKILL.md',
            },
        },
        {
            'event_type': 'tool_call_completed',
            'payload': {
                'call_id': 'call-2',
                'tool_name': 'testing_run',
                'result': '10 passed, 0 failed',
            },
        },
    ]
    bundle = build_proof_of_use(events, 'All tests passed.')
    assert len(bundle.proofs) == 1
    p = bundle.proofs[0]
    assert p.source_skill_name == 'testing'
    assert p.verified is True
    assert p.verified_at != ''


def test_build_proof_of_use_multiple_skills():
    events = [
        {
            'event_type': 'skill_lifecycle_transition',
            'payload': {
                'skill_name': 'git-workflow',
                'to_state': 'used_in_run',
                'source_path': '/s/git/SKILL.md',
            },
        },
        {
            'event_type': 'skill_lifecycle_transition',
            'payload': {
                'skill_name': 'testing',
                'to_state': 'used_in_run',
                'source_path': '/s/testing/SKILL.md',
            },
        },
        {
            'event_type': 'tool_call_completed',
            'payload': {
                'call_id': 'call-git',
                'tool_name': 'git-workflow_commit',
                'result': 'committed',
            },
        },
        {
            'event_type': 'tool_call_completed',
            'payload': {
                'call_id': 'call-test',
                'tool_name': 'testing_run',
                'result': 'passed',
            },
        },
    ]
    bundle = build_proof_of_use(events, 'Done.')
    assert len(bundle.proofs) == 2
    names = {p.source_skill_name for p in bundle.proofs}
    assert names == {'git-workflow', 'testing'}


def test_build_proof_of_use_dedup_call_ids():
    events = [
        {
            'event_type': 'skill_lifecycle_transition',
            'payload': {
                'skill_name': 'code-review',
                'to_state': 'used_in_run',
                'source_path': '/s/cr/SKILL.md',
            },
        },
        {
            'event_type': 'tool_call_completed',
            'payload': {
                'call_id': 'call-1',
                'tool_name': 'code-review_check',
                'result': 'ok',
            },
        },
        {
            'event_type': 'tool_call_completed',
            'payload': {
                'call_id': 'call-1',
                'tool_name': 'code-review_check',
                'result': 'ok (duplicate)',
            },
        },
    ]
    bundle = build_proof_of_use(events, 'Reviewed.')
    assert len(bundle.proofs) == 1


def test_build_proof_of_use_no_lifecycle_fallback():
    events = [
        {
            'event_type': 'tool_call_completed',
            'payload': {
                'call_id': 'c1',
                'tool_name': 'execute_skill',
                'result': 'skill output',
            },
        },
    ]
    bundle = build_proof_of_use(events, 'done')
    assert len(bundle.proofs) == 1
    p = bundle.proofs[0]
    assert 'skill' in p.tool_name.lower()


def test_build_proof_of_use_unrelated_tool_ignored():
    events = [
        {
            'event_type': 'skill_lifecycle_transition',
            'payload': {
                'skill_name': 'p0-agent-harness',
                'to_state': 'used_in_run',
                'source_path': '/s/harness/SKILL.md',
            },
        },
        {
            'event_type': 'tool_call_completed',
            'payload': {
                'call_id': 'c1',
                'tool_name': 'workspace_read_file',
                'result': 'file content',
            },
        },
    ]
    bundle = build_proof_of_use(events, 'done')
    assert bundle.proofs == []


def test_emit_proof_of_use_audit():
    bundle = ProofOfUseBundle(
        proofs=[
            ProofOfUse(
                source_skill_name='testing',
                source_artifact_path='/s/testing/SKILL.md',
                tool_call_id='c1',
                tool_name='testing_run',
                output_hash='sha256:abc',
                verified=True,
                verified_at='2026-06-05T00:00:00Z',
            )
        ],
        final_answer_hash='sha256:fa',
        final_answer_preview='All tests passed.',
    )
    payload = emit_proof_of_use_audit(bundle)
    assert payload['proof_count'] == 1
    assert payload['final_answer_hash'] == 'sha256:fa'
    assert payload['final_answer_preview'] == 'All tests passed.'
    assert len(payload['proofs']) == 1


def test_final_answer_hash_consistent():
    content = 'The quick brown fox'
    bundle1 = build_proof_of_use([], content)
    bundle2 = build_proof_of_use([], content)
    assert bundle1.final_answer_hash == bundle2.final_answer_hash


def test_final_answer_preview_truncation():
    long_answer = 'x' * 500
    bundle = build_proof_of_use([], long_answer)
    assert len(bundle.final_answer_preview) == 200
