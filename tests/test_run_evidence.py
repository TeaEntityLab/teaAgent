"""Tests for run evidence bundle extraction."""

import re
import tempfile

from teaagent.redaction import RedactionConfig
from teaagent.run_evidence import (
    ApprovalEvidence,
    CommandEvidence,
    KnownGap,
    RunEvidenceBundle,
    TestEvidence,
    auto_derive_known_gaps,
    build_run_evidence_bundle,
    extract_approvals,
    extract_commands_run,
    extract_tests,
)


def test_extract_commands_run():
    """Test extracting command execution evidence."""
    events = [
        {
            'event_type': 'tool_use',
            'payload': {
                'tool_name': 'exec',
                'input': {'command': 'ls -la'},
            },
            'created_at': 1234567890.0,
        },
        {
            'event_type': 'tool_use',
            'payload': {
                'tool_name': 'shell',
                'input': {'command': 'echo "hello"'},
            },
            'created_at': 1234567891.0,
        },
    ]

    commands = extract_commands_run(events)
    assert len(commands) == 2
    assert commands[0].command == 'ls -la'
    assert commands[0].tool_name == 'exec'
    assert commands[1].command == 'echo "hello"'


def test_extract_tests():
    """Test extracting test execution evidence."""
    events = [
        {
            'event_type': 'test_run',
            'payload': {
                'test_name': 'test_example',
                'test_file': 'tests/test_example.py',
                'status': 'passed',
                'duration_ms': 100.0,
            },
            'created_at': 1234567890.0,
        },
        {
            'event_type': 'test_run',
            'payload': {
                'test_name': 'test_failure',
                'test_file': 'tests/test_failure.py',
                'status': 'failed',
                'error_message': 'AssertionError',
            },
            'created_at': 1234567891.0,
        },
    ]

    tests = extract_tests(events)
    assert len(tests) == 2
    assert tests[0].test_name == 'test_example'
    assert tests[0].status == 'passed'
    assert tests[1].status == 'failed'
    assert tests[1].error_message == 'AssertionError'


def test_extract_approvals():
    """Test extracting approval evidence."""
    events = [
        {
            'event_type': 'approval_requested',
            'payload': {
                'call_id': 'call-123',
                'tool_name': 'workspace_write_file',
                'auto_approved': False,
            },
            'created_at': 1234567890.0,
        },
        {
            'event_type': 'approval_granted',
            'payload': {
                'call_id': 'call-123',
                'tool_name': 'workspace_write_file',
                'auto_approved': False,
            },
            'created_at': 1234567891.0,
        },
    ]

    approvals = extract_approvals(events)
    assert len(approvals) == 1
    assert approvals[0].call_id == 'call-123'
    assert approvals[0].approved is True
    assert approvals[0].auto_approved is False


def test_auto_derive_known_gaps():
    """Test auto-deriving known gaps from events and commands."""
    events = [
        {
            'event_type': 'run_failed',
            'payload': {'message': 'Task failed due to timeout'},
            'created_at': 1234567890.0,
        },
        {
            'event_type': 'tool_error',
            'payload': {'error': 'Tool not found'},
            'created_at': 1234567891.0,
        },
    ]

    commands = [
        CommandEvidence(
            command='invalid_command',
            tool_name='exec',
            exit_code=127,
            timestamp=1234567892.0,
        )
    ]

    gaps = auto_derive_known_gaps(events, commands)
    assert len(gaps) == 3
    assert any(g.category == 'run_failure' for g in gaps)
    assert any(g.category == 'tool_error' for g in gaps)
    assert any(g.category == 'command_failure' for g in gaps)


def test_run_evidence_bundle_serialization():
    """Test RunEvidenceBundle serialization."""
    bundle = RunEvidenceBundle(
        run_id='test-run-123',
        commands_run=[
            CommandEvidence(command='ls', tool_name='exec'),
        ],
        tests=[
            TestEvidence(
                test_name='test_example', test_file='test.py', status='passed'
            ),
        ],
        approvals=[
            ApprovalEvidence(call_id='call-1', tool_name='write', approved=True),
        ],
        known_gaps=[
            KnownGap(category='error', description='Test error', severity='low'),
        ],
    )

    data = bundle.to_dict()
    assert data['run_id'] == 'test-run-123'
    assert len(data['commands_run']) == 1
    assert len(data['tests']) == 1
    assert len(data['approvals']) == 1
    assert len(data['known_gaps']) == 1


def test_build_run_evidence_bundle():
    """Test building complete evidence bundle from run store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # This test requires a real run store with events
        # For now, test that it returns a bundle even for missing runs
        bundle = build_run_evidence_bundle(tmpdir, 'nonexistent-run')
        assert bundle.run_id == 'nonexistent-run'
        assert bundle.commands_run == []
        assert bundle.tests == []
        assert bundle.approvals == []
        assert bundle.known_gaps == []


# ── redaction-related tests ───────────────────────────────────────────


def test_redaction_preserves_evidence_structure():
    """Redacted audit events should not break evidence extraction."""
    events = [
        {
            'event_type': 'tool_use',
            'payload': {
                'tool_name': 'exec',
                'input': {'command': 'export TOKEN=Bearer [redacted]'},
            },
            'created_at': 1234567890.0,
        },
        {
            'event_type': 'tool_use',
            'payload': {
                'tool_name': 'shell',
                'input': {'command': 'echo "hello"'},
            },
            'created_at': 1234567891.0,
        },
    ]

    commands = extract_commands_run(events)
    assert len(commands) == 2
    assert commands[0].command == 'export TOKEN=Bearer [redacted]'


def test_redaction_carries_through_to_bundle_serialization():
    """Redacted content in evidence survives round-trip through to_dict()."""
    bundle = RunEvidenceBundle(
        run_id='redacted-run',
        commands_run=[
            CommandEvidence(
                command='curl -H "Authorization: Bearer [redacted]" https://api.example.com',
                tool_name='exec',
                exit_code=0,
            ),
        ],
        approvals=[
            ApprovalEvidence(
                call_id='call-redacted',
                tool_name='workspace_write_file',
                approved=True,
                authority_type='jit_prompt',
                approved_by='[redacted]',
            ),
        ],
        known_gaps=[
            KnownGap(
                category='secret_leak',
                description='Leaked credential: [redacted-anthropic-key]',
                severity='high',
            ),
        ],
    )

    data = bundle.to_dict()
    assert data['run_id'] == 'redacted-run'
    assert len(data['commands_run']) == 1
    assert '[redacted]' in data['commands_run'][0]['command']
    assert data['approvals'][0]['approved_by'] == '[redacted]'
    assert '[redacted-anthropic-key]' in data['known_gaps'][0]['description']


def test_redaction_marker_patterns():
    """All standard redaction markers should be recognized in evidence output."""
    markers = [
        'Bearer [redacted]',
        '[redacted]',
        '[redacted-JWT]',
        '[redacted-google-key]',
        '[redacted-openai-key]',
        '[redacted-anthropic-key]',
        '[redacted-ssh-key]',
        '[CUSTOM-REDACTED]',
    ]
    marker_pattern = re.compile(
        r'\[redacted[^\]]*\]|Bearer \[redacted\]|\[CUSTOM-REDACTED\]'
    )
    for marker in markers:
        assert marker_pattern.search(marker), f'Marker {marker!r} not matched'


def test_redaction_config_default_all_enabled():
    """Default RedactionConfig enables all pattern groups."""
    cfg = RedactionConfig()
    assert cfg.bearer_tokens is True
    assert cfg.api_keys is True
    assert cfg.jwt_tokens is True
    assert cfg.aws_keys is True
    assert cfg.github_tokens is True
    assert cfg.query_params is True
    assert cfg.google_keys is True
    assert cfg.openai_keys is True
    assert cfg.anthropic_keys is True
    assert cfg.database_urls is True
    assert cfg.ssh_keys is True


def test_redaction_config_build_patterns():
    """RedactionConfig.build_patterns() returns active patterns only."""
    cfg = RedactionConfig(
        bearer_tokens=False,
        api_keys=False,
        jwt_tokens=False,
        aws_keys=False,
        github_tokens=False,
        query_params=False,
        google_keys=False,
        openai_keys=False,
        anthropic_keys=False,
        database_urls=False,
        ssh_keys=False,
    )
    patterns = cfg.build_patterns()
    assert len(patterns) == 0

    cfg_full = RedactionConfig()
    patterns_full = cfg_full.build_patterns()
    assert len(patterns_full) > 0


# ---------------------------------------------------------------------------
# ADR 0032 M6 (FOLD-T001): evidence-bundle fold over the typed event stream
# ---------------------------------------------------------------------------


def _write_run(root: str, run_id: str, events: list[dict]) -> None:
    """Persist raw audit-event dicts as a RunStore JSONL for the run."""
    import json

    from teaagent.run_store import RunStore

    path = RunStore(root).run_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(json.dumps(e) for e in events) + '\n', encoding='utf-8')


def _assert_fold_matches_legacy(events: list[dict], run_id: str) -> RunEvidenceBundle:
    """The typed-stream fold must equal the raw-audit-dict assembly.

    Baselines against ``_assemble_evidence_bundle`` (the raw-dict path) rather
    than ``build_run_evidence_bundle`` — after the M6 FOLD-T002 cutover the
    public builder itself folds through the typed reader, so comparing it to the
    fold would be circular. The invariant that matters is that routing raw audit
    dicts through ``read_run_events_from_audit`` (typed reader) loses no evidence
    versus assembling directly from those dicts.
    """
    from teaagent.run_evidence import (
        _assemble_evidence_bundle,
        build_evidence_from_events,
    )
    from teaagent.runner._events import read_run_events_from_audit

    with tempfile.TemporaryDirectory() as root:
        # Raw-dict assembly (pre-cutover production path) is the baseline.
        legacy = _assemble_evidence_bundle(events, root=root, run_id=run_id)

        # Typed-stream fold (current production path) must match it.
        typed = read_run_events_from_audit(events)
        folded = build_evidence_from_events(typed, root=root, run_id=run_id)

        assert folded.to_dict() == legacy.to_dict()
    return legacy


def test_m6_fold_equals_legacy_on_success_run():
    """Success run with commands, tests, and an approval folds losslessly."""
    events = [
        {
            'event_type': 'run_started',
            'run_id': 'r-ok',
            'payload': {},
            'created_at': '2026-06-13T10:00:00+00:00',
        },
        {
            'event_type': 'tool_use',
            'run_id': 'r-ok',
            'payload': {
                'tool_name': 'workspace_run_shell',
                'input': {'command': 'pytest -q'},
                'call_id': 'c1',
            },
            'created_at': '2026-06-13T10:00:01+00:00',
        },
        {
            'event_type': 'tool_call_completed',
            'run_id': 'r-ok',
            'payload': {
                'tool_name': 'workspace_run_shell',
                'call_id': 'c1',
                'result': {'exit_code': 0, 'stdout': 'ok'},
            },
            'created_at': '2026-06-13T10:00:02+00:00',
        },
        {
            'event_type': 'test_run',
            'run_id': 'r-ok',
            'payload': {
                'test_name': 'unit',
                'test_file': 'tests/test_x.py',
                'passed': True,
            },
            'created_at': '2026-06-13T10:00:03+00:00',
        },
        {
            'event_type': 'approval_requested',
            'run_id': 'r-ok',
            'payload': {'call_id': 'c2', 'tool_name': 'workspace_write_file'},
            'created_at': '2026-06-13T10:00:04+00:00',
        },
        {
            'event_type': 'approval_granted',
            'run_id': 'r-ok',
            'payload': {
                'call_id': 'c2',
                'tool_name': 'workspace_write_file',
                'authority_type': 'jit_prompt',
                'approved_by': 'user',
            },
            'created_at': '2026-06-13T10:00:05+00:00',
        },
        {
            'event_type': 'run_completed',
            'run_id': 'r-ok',
            'payload': {'cost_cents': 1.0},
            'created_at': '2026-06-13T10:00:06+00:00',
        },
    ]
    bundle = _assert_fold_matches_legacy(events, 'r-ok')
    # Guard against a vacuous pass: the fixture must actually carry evidence.
    assert bundle.commands_run and bundle.approvals


def test_m6_fold_equals_legacy_on_failure_run():
    """Failed run with a tool error folds losslessly."""
    events = [
        {
            'event_type': 'run_started',
            'run_id': 'r-fail',
            'payload': {},
            'created_at': '2026-06-13T11:00:00+00:00',
        },
        {
            'event_type': 'tool_use',
            'run_id': 'r-fail',
            'payload': {
                'tool_name': 'workspace_run_shell',
                'input': {'command': 'make build'},
                'call_id': 'c1',
            },
            'created_at': '2026-06-13T11:00:01+00:00',
        },
        {
            'event_type': 'tool_error',
            'run_id': 'r-fail',
            'payload': {
                'tool_name': 'workspace_run_shell',
                'call_id': 'c1',
                'error': 'boom',
            },
            'created_at': '2026-06-13T11:00:02+00:00',
        },
        {
            'event_type': 'run_failed',
            'run_id': 'r-fail',
            'payload': {'error': 'build failed'},
            'created_at': '2026-06-13T11:00:03+00:00',
        },
    ]
    _assert_fold_matches_legacy(events, 'r-fail')


def test_m6_fold_equals_legacy_on_pending_approval_run():
    """Pending-approval run (requested, not resolved) folds losslessly."""
    events = [
        {
            'event_type': 'run_started',
            'run_id': 'r-pend',
            'payload': {},
            'created_at': '2026-06-13T12:00:00+00:00',
        },
        {
            'event_type': 'tool_call_pending_approval',
            'run_id': 'r-pend',
            'payload': {'call_id': 'c1', 'tool_name': 'workspace_write_file'},
            'created_at': '2026-06-13T12:00:01+00:00',
        },
    ]
    _assert_fold_matches_legacy(events, 'r-pend')


def test_m6_fold_preserves_created_at_in_command_timestamps():
    """The typed RunEvent carries created_at, so folded command timestamps
    match the legacy (audit-sourced) timestamps rather than collapsing to None.
    """
    from teaagent.run_evidence import build_evidence_from_events
    from teaagent.run_store import RunStore
    from teaagent.runner._events import read_run_events_from_audit

    events = [
        {
            'event_type': 'tool_use',
            'run_id': 'r-ts',
            'payload': {
                'tool_name': 'workspace_run_shell',
                'input': {'command': 'echo hi'},
                'call_id': 'c1',
            },
            'created_at': '2026-06-13T13:00:01+00:00',
        },
    ]
    with tempfile.TemporaryDirectory() as root:
        _write_run(root, 'r-ts', events)
        typed = read_run_events_from_audit(RunStore(root).show_run('r-ts'))
        assert typed[0].created_at == '2026-06-13T13:00:01+00:00'
        folded = build_evidence_from_events(typed, root=root, run_id='r-ts')
        assert folded.commands_run[0].timestamp == '2026-06-13T13:00:01+00:00'


# Audit event types that the evidence/proof-of-use extractors filter on. After
# the M6 FOLD-T002 cutover, build_run_evidence_bundle routes through
# read_run_events_from_audit, which DROPS any audit event whose type is not in
# RunEventType. So production evidence is lossless ONLY IF every type below is
# typed. This list is the enforced coupling: if you teach an extractor to read a
# NEW audit event type, add it here — the test will then fail until that type is
# also added to RunEventType (otherwise the cutover would silently drop it).
EVIDENCE_EXTRACTOR_AUDIT_TYPES: frozenset[str] = frozenset(
    {
        'run_started',
        'run_failed',
        'tool_use',
        'tool_call_started',
        'tool_call_completed',
        'tool_error',
        'test_run',
        'approval_requested',
        'approval_granted',
        'approval_denied',
        'tool_call_approved',
        'tool_call_denied',
        'tool_call_pending_approval',
        'model_route',
        'provenance_collected',
        'skill_activated',
        'skill_lifecycle_transition',
        'git_sandbox_started',
        'git_sandbox_resolved',
        'undo_applied',
    }
)


def test_m6_every_evidence_extractor_type_is_typed() -> None:
    """Guard the FOLD-T002 cutover: every audit type the evidence extractors read
    must be in RunEventType, or read_run_events_from_audit would silently drop it
    from production evidence (F2 from the post-migration review).
    """
    from teaagent.runner._events import _AUDIT_EVENT_TO_RUN_EVENT_TYPE

    missing = sorted(
        t
        for t in EVIDENCE_EXTRACTOR_AUDIT_TYPES
        if t not in _AUDIT_EVENT_TO_RUN_EVENT_TYPE
    )
    assert not missing, (
        f'evidence extractors read audit types not in RunEventType: {missing}. '
        f'The M6 cutover would silently drop them — add them to RunEventType + '
        f'the audit mapper in teaagent/runner/_events.py.'
    )
