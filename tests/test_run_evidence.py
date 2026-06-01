"""Tests for run evidence bundle extraction."""

import tempfile

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
