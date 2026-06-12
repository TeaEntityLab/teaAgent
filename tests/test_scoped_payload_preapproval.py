"""Tests for scoped payload digest preapproval mechanism (TASK-008)."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

from teaagent import (
    AgentRunner,
    ApprovalPolicy,
    AuditLogger,
    FinalAnswer,
    ToolAnnotations,
    ToolRegistry,
    ToolRequest,
)
from teaagent.ergonomics.approval_store import ApprovalPresetStore
from teaagent.policy import compute_scoped_payload_digest

INPUT_SCHEMA = {
    'type': 'object',
    'properties': {'value': {'type': 'string'}},
    'required': ['value'],
}

OUTPUT_SCHEMA = {
    'type': 'object',
    'properties': {'value': {'type': 'string'}},
    'required': ['value'],
}


def build_registry(*, destructive: bool = False) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        name='pilot_echo',
        description='Return the supplied value for pilot validation.',
        input_schema=INPUT_SCHEMA,
        output_schema=OUTPUT_SCHEMA,
        annotations=ToolAnnotations(
            read_only=not destructive,
            destructive=destructive,
            idempotent=True,
        ),
        handler=lambda args: {'value': args['value']},
    )
    return registry


def test_compute_scoped_payload_digest_determinism() -> None:
    """Digest computation should be deterministic and order-insensitive."""
    tool_name = 'workspace_write_file'
    args1 = {'path': 'calc.py', 'content': 'def add(a, b):\n    return a + b\n'}
    args2 = {'content': 'def add(a, b):\n    return a + b\n', 'path': 'calc.py'}

    digest1 = compute_scoped_payload_digest(tool_name, args1)
    digest2 = compute_scoped_payload_digest(tool_name, args2)

    # Same payload in different dict order should yield same digest
    assert digest1 == digest2
    # Digest should be 64 hex characters (SHA256)
    assert len(digest1) == 64
    assert all(c in '0123456789abcdef' for c in digest1)


def test_compute_scoped_payload_digest_excludes_call_id() -> None:
    """Digest should not include call_id (model-controlled)."""
    tool_name = 'workspace_write_file'
    args = {'path': 'calc.py', 'content': 'def add(a, b):\n    return a + b\n'}

    # The digest should be independent of any call_id
    digest = compute_scoped_payload_digest(tool_name, args)

    # Verify the digest only depends on tool_name and arguments
    # by creating the canonical JSON ourselves
    import hashlib

    canonical = json.dumps(
        {'tool_name': tool_name, 'arguments': args},
        sort_keys=True,
        separators=(',', ':'),
    )
    expected_digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    assert digest == expected_digest


def test_destructive_tool_approved_by_payload_digest(tmp_path: Path) -> None:
    """Runner should approve destructive call whose payload digest is preapproved."""
    tool_name = 'pilot_echo'
    arguments = {'value': 'delete'}

    # Compute the digest for this payload
    digest = compute_scoped_payload_digest(tool_name, arguments)

    # Create approval store and preapprove this digest
    store = ApprovalPresetStore(tmp_path / '.teaagent')
    (store.path.parent).mkdir(parents=True, exist_ok=True)

    # Create a policy with the digest preapproved
    policy = ApprovalPolicy(
        preapproved_payload_digests=frozenset([digest]),
        approval_store=store,
        approval_origin_run_id='run-test',
    )

    audit = AuditLogger()
    runner = AgentRunner(
        registry=build_registry(destructive=True),
        audit=audit,
        approval_policy=policy,
    )

    def decide(context):
        if not context['observations']:
            return ToolRequest(
                tool_name=tool_name,
                arguments=arguments,
                call_id='call-1',  # call_id can be anything
            )
        return FinalAnswer(content='done')

    result = runner.run(task='destructive action', decide=decide, run_id='run-test')

    # Should be approved and completed
    assert result.status == 'completed'
    assert result.final_answer.content == 'done'


def test_destructive_tool_denied_by_wrong_digest(tmp_path: Path) -> None:
    """Runner should deny destructive call whose payload digest is not preapproved."""
    tool_name = 'pilot_echo'
    arguments = {'value': 'delete'}

    # Compute the digest for a DIFFERENT payload
    wrong_digest = compute_scoped_payload_digest(tool_name, {'value': 'different'})

    # Create approval store with wrong digest preapproved
    store = ApprovalPresetStore(tmp_path / '.teaagent')
    (store.path.parent).mkdir(parents=True, exist_ok=True)

    # Create a policy with the wrong digest preapproved
    policy = ApprovalPolicy(
        preapproved_payload_digests=frozenset([wrong_digest]),
        approval_store=store,
        approval_origin_run_id='run-test',
    )

    audit = AuditLogger()
    runner = AgentRunner(
        registry=build_registry(destructive=True),
        audit=audit,
        approval_policy=policy,
    )

    call_count = [0]

    def decide(context):
        call_count[0] += 1
        if call_count[0] == 1:
            return ToolRequest(
                tool_name=tool_name,
                arguments=arguments,
                call_id='call-1',
            )
        return FinalAnswer(content='should not reach here')

    result = runner.run(task='destructive action', decide=decide, run_id='run-test')

    # Should be pending approval (not approved by digest path)
    assert result.status == 'pending_approval'


def test_scoped_digest_approval_no_deprecation_warning(tmp_path: Path) -> None:
    """Digest path should NOT emit DeprecationWarning about preapproved_call_ids."""
    tool_name = 'pilot_echo'
    arguments = {'value': 'delete'}

    # Compute the digest
    digest = compute_scoped_payload_digest(tool_name, arguments)

    # Create approval store and preapprove this digest
    store = ApprovalPresetStore(tmp_path / '.teaagent')
    (store.path.parent).mkdir(parents=True, exist_ok=True)

    # Create a policy with ONLY digest preapproval (no call_ids)
    policy = ApprovalPolicy(
        preapproved_payload_digests=frozenset([digest]),
        approval_store=store,
        approval_origin_run_id='run-test',
    )

    audit = AuditLogger()
    runner = AgentRunner(
        registry=build_registry(destructive=True),
        audit=audit,
        approval_policy=policy,
    )

    def decide(context):
        if not context['observations']:
            return ToolRequest(
                tool_name=tool_name,
                arguments=arguments,
                call_id='call-1',
            )
        return FinalAnswer(content='done')

    # Capture warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        result = runner.run(task='test', decide=decide, run_id='run-test')

        # Check that no DeprecationWarning about preapproved_call_ids was raised
        deprecation_warnings = [
            warning
            for warning in w
            if issubclass(warning.category, DeprecationWarning)
            and 'preapproved_call_ids' in str(warning.message)
        ]
        assert len(deprecation_warnings) == 0, (
            f'Digest path should not emit preapproved_call_ids warning, got: '
            f'{[str(w.message) for w in deprecation_warnings]}'
        )

    # And it should succeed
    assert result.status == 'completed'


def test_cli_parse_approve_scoped_valid() -> None:
    """CLI should parse --approve-scoped TOOL:SHA256 correctly."""
    from teaagent.cli._handlers._agent.run import _parse_approve_scoped

    scoped_approvals = [
        'workspace_write_file:' + 'a' * 64,
        'other_tool:' + 'b' * 64,
    ]
    result = _parse_approve_scoped(scoped_approvals)

    assert len(result) == 2
    assert 'a' * 64 in result
    assert 'b' * 64 in result


def test_cli_parse_approve_scoped_no_colon() -> None:
    """CLI should reject --approve-scoped without colon."""
    from teaagent.cli._handlers._agent.run import _parse_approve_scoped

    scoped_approvals = ['invalid_no_colon']

    try:
        _parse_approve_scoped(scoped_approvals)
        raise AssertionError('Should have raised SystemExit')
    except SystemExit as e:
        assert 'TOOL:SHA256' in str(e)


def test_cli_parse_approve_scoped_short_hash() -> None:
    """CLI should reject --approve-scoped with hash shorter than 64 chars."""
    from teaagent.cli._handlers._agent.run import _parse_approve_scoped

    scoped_approvals = ['workspace_write_file:' + 'a' * 32]  # Too short

    try:
        _parse_approve_scoped(scoped_approvals)
        raise AssertionError('Should have raised SystemExit')
    except SystemExit as e:
        assert '64 hex chars' in str(e)


def test_cli_parse_approve_scoped_non_hex() -> None:
    """CLI should reject --approve-scoped with non-hex characters in digest."""
    from teaagent.cli._handlers._agent.run import _parse_approve_scoped

    scoped_approvals = ['workspace_write_file:' + 'g' * 64]  # 'g' is not hex

    try:
        _parse_approve_scoped(scoped_approvals)
        raise AssertionError('Should have raised SystemExit')
    except SystemExit as e:
        assert '64 hex chars' in str(e)
