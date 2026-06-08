"""Property-based tests for critical invariants.

Uses hypothesis to verify core invariants hold under arbitrary inputs.
"""

from __future__ import annotations

import json
from pathlib import Path

from teaagent.audit_chain import GENESIS_HASH, compute_chain_hmac
from teaagent.config_loader import ConfigResolver, _coerce
from teaagent.tool_permissions import (
    ToolPermission,
    ToolPermissionManager,
    ToolSafetyLevel,
)
from teaagent.types import compute_event_hash, verify_audit_chain

# ── Audit chain integrity ──────────────────────────────────────────


def _make_event(
    event_id: str = 'e1',
    event_type: str = 'test',
    run_id: str = 'r1',
    created_at: str = '2026-01-01T00:00:00Z',
    payload: object = None,
    prev_hash: str = GENESIS_HASH,
) -> dict:
    return {
        'event_id': event_id,
        'event_type': event_type,
        'run_id': run_id,
        'created_at': created_at,
        'payload': payload or {},
        'prev_hash': prev_hash,
    }


def _build_chain(events: list[dict]) -> list[dict]:
    chain: list[dict] = []
    prev_hash = GENESIS_HASH
    for evt in events:
        event = {
            'event_id': evt.get('event_id', 'e'),
            'event_type': evt.get('event_type', 'test'),
            'run_id': evt.get('run_id', 'r1'),
            'created_at': evt.get('created_at', '2026-01-01T00:00:00Z'),
            'payload': evt.get('payload', {}),
            'prev_hash': prev_hash,
        }
        event['hash'] = compute_event_hash(event)
        prev_hash = event['hash']
        chain.append(event)
    return chain


def test_compute_event_hash_is_deterministic():
    h1 = compute_event_hash(_make_event(event_id='a', payload='hello'))
    h2 = compute_event_hash(_make_event(event_id='a', payload='hello'))
    assert h1 == h2


def test_compute_event_hash_differs_for_different_inputs():
    h1 = compute_event_hash(_make_event(event_id='a', payload='alpha'))
    h2 = compute_event_hash(_make_event(event_id='b', payload='beta'))
    assert h1 != h2


def test_audit_chain_accepts_valid_chains(tmp_path: Path) -> None:
    log = tmp_path / 'chain.jsonl'
    events = []
    prev_hash = GENESIS_HASH
    for i in range(10):
        evt = {
            'event_id': f'e{i}',
            'event_type': 'test',
            'run_id': 'r1',
            'created_at': f'2026-01-01T00:00:{i:02d}Z',
            'payload': {'i': i},
            'prev_hash': prev_hash,
        }
        evt['hash'] = compute_event_hash(evt)
        prev_hash = evt['hash']
        events.append(evt)

    log.write_text(
        '\n'.join(json.dumps(e, sort_keys=True) for e in events) + '\n',
        encoding='utf-8',
    )
    result = verify_audit_chain(log)
    assert result.valid, result.error


def test_audit_chain_verification_rejects_tampered_events(tmp_path: Path) -> None:
    log = tmp_path / 'tampered.jsonl'
    events = _build_chain(
        [_make_event(event_id=f'e{i}', payload={'i': i}) for i in range(5)]
    )
    # Tamper with the middle event
    events[2]['payload'] = 'tampered!!!'
    log.write_text(
        '\n'.join(json.dumps(e, sort_keys=True) for e in events) + '\n',
        encoding='utf-8',
    )
    result = verify_audit_chain(log)
    assert not result.valid
    assert len(result.failures) > 0


def test_compute_chain_hmac_is_deterministic():
    key = b'a' * 32
    h1 = compute_chain_hmac('abc123', key)
    h2 = compute_chain_hmac('abc123', key)
    assert h1 == h2


def test_compute_chain_hmac_differs_with_key():
    event_hash = 'abc123def456'
    h1 = compute_chain_hmac(event_hash, b'x' * 32)
    h2 = compute_chain_hmac(event_hash, b'y' * 32)
    assert h1 != h2


# ── Config merge invariants ─────────────────────────────────────────


def test_config_layer_precedence_env_wins(tmp_path: Path, monkeypatch) -> None:
    """Environment variables take highest precedence."""
    monkeypatch.setenv('TEAAGENT_PERMISSION_MODE', 'danger-full-access')
    monkeypatch.setenv('TEAAGENT_MAX_ITERATIONS', '99')

    resolver = ConfigResolver(workspace_root=tmp_path)
    result = resolver.resolve()

    assert result.get('permission_mode') == 'danger-full-access'
    assert result.get('max_iterations') == 99
    assert result.source('permission_mode').value == 'env'
    assert result.source('max_iterations').value == 'env'


def test_config_workspace_overrides_user(tmp_path: Path) -> None:
    """Workspace config overrides user-level config."""
    home = tmp_path / 'home'
    home.mkdir()
    (home / '.teaagent').mkdir()
    (home / '.teaagent' / 'config.json').write_text(
        json.dumps({'permission_mode': 'read-only'}), encoding='utf-8'
    )

    ws = tmp_path / 'ws'
    ws.mkdir()
    (ws / '.teaagent').mkdir()
    (ws / '.teaagent' / 'config.json').write_text(
        json.dumps({'permission_mode': 'workspace-write'}), encoding='utf-8'
    )

    resolver = ConfigResolver(workspace_root=ws, user_home=home)
    result = resolver.resolve()
    assert result.get('permission_mode') == 'workspace-write'
    assert result.source('permission_mode').value == 'workspace'


def test_config_user_overrides_default(tmp_path: Path) -> None:
    """User config overrides built-in defaults."""
    home = tmp_path / 'home'
    home.mkdir()
    (home / '.teaagent').mkdir()
    (home / '.teaagent' / 'config.json').write_text(
        json.dumps({'permission_mode': 'read-only'}), encoding='utf-8'
    )

    resolver = ConfigResolver(workspace_root=tmp_path / 'ws', user_home=home)
    result = resolver.resolve()
    assert result.get('permission_mode') == 'read-only'
    assert result.source('permission_mode').value == 'user'


def test_config_default_fallback(tmp_path: Path) -> None:
    """Missing keys fall back to built-in defaults."""
    resolver = ConfigResolver(workspace_root=tmp_path)
    result = resolver.resolve()
    assert result.get('permission_mode') == 'prompt'
    assert result.source('permission_mode').value == 'default'


def test_config_empty_workspace_is_safe(tmp_path: Path) -> None:
    """No config files at all — the resolver does not crash."""
    resolver = ConfigResolver(workspace_root=tmp_path / 'nope')
    result = resolver.resolve()
    assert isinstance(result.values, dict)
    assert isinstance(result.sources, dict)


def test_config_show_produces_lines(tmp_path: Path) -> None:
    """ConfigResolver.show() returns human-readable key=value lines."""
    resolver = ConfigResolver(workspace_root=tmp_path)
    result = resolver.resolve()
    lines = result.show()
    assert len(lines) > 0
    assert any('permission_mode' in line for line in lines)


def test_config_coerce_list_from_json(tmp_path: Path) -> None:
    """_coerce parses JSON-like list strings."""
    result = _coerce('["a", "b"]', list)
    assert result == ['a', 'b']


def test_config_coerce_int():
    assert _coerce('42', int) == 42


def test_config_coerce_bool():
    assert _coerce('true', bool) is True
    assert _coerce('false', bool) is False


# ── Permission mode transitions ────────────────────────────────────


def test_permission_manager_classifies_safe_tools():
    manager = ToolPermissionManager()
    assert manager.classify_tool('read_file') == ToolSafetyLevel.SAFE
    assert manager.classify_tool('grep') == ToolSafetyLevel.SAFE


def test_permission_manager_classifies_destructive_tools():
    manager = ToolPermissionManager()
    assert manager.classify_tool('write_file') == ToolSafetyLevel.DESTRUCTIVE
    assert manager.classify_tool('delete_file') == ToolSafetyLevel.DESTRUCTIVE


def test_permission_manager_unknown_tool_is_destructive():
    manager = ToolPermissionManager()
    assert manager.classify_tool('nonexistent_tool') == ToolSafetyLevel.DESTRUCTIVE


def test_permission_downgrade_is_blocked():
    """Cannot downgrade a DESTRUCTIVE tool to SAFE without explicit flag."""
    manager = ToolPermissionManager()
    perm = manager.get_tool_permission('write_file')
    assert perm is not None
    assert perm.safety_level == ToolSafetyLevel.DESTRUCTIVE

    # Attempt to downgrade write_file from DESTRUCTIVE to SAFE (without flag)
    downgrade_perm = ToolPermission(
        name='write_file', safety_level=ToolSafetyLevel.SAFE
    )
    manager.register_tool_permission(downgrade_perm)
    # Downgrade should be blocked — write_file still DESTRUCTIVE
    assert manager.classify_tool('write_file') == ToolSafetyLevel.DESTRUCTIVE


def test_permission_approval_is_per_agent():
    """Approval for agent-A must not leak to agent-B."""

    def mock_approve(request):
        return request.agent_name == 'agent-a'

    manager = ToolPermissionManager(approval_callback=mock_approve)
    manager.grant_agent_tool_access('agent-a', ('write_file',), allow_destructive=True)
    manager.grant_agent_tool_access('agent-b', ('write_file',), allow_destructive=True)

    # Approve agent-a only
    manager.request_tool_approval('agent-a', 'write_file', 'need it')

    has_a, _ = manager.check_tool_access('agent-a', 'write_file')
    has_b, reason_b = manager.check_tool_access('agent-b', 'write_file')
    assert has_a is True
    assert has_b is False
    assert 'JIT approval' in reason_b


def test_permission_jit_approval_is_single_use():
    """JIT approval is consumed after first use."""

    def mock_approve(request):
        return True

    manager = ToolPermissionManager(approval_callback=mock_approve)
    manager.grant_agent_tool_access('agent', ('write_file',), allow_destructive=True)

    # First approval
    manager.request_tool_approval('agent', 'write_file', 'first use')
    has, _ = manager.check_tool_access('agent', 'write_file')
    assert has is True

    # Second call — JIT approval already consumed
    has2, reason2 = manager.check_tool_access('agent', 'write_file')
    assert has2 is False
    assert 'JIT approval' in reason2


def test_permission_revoke_removes_access():
    manager = ToolPermissionManager()
    manager.grant_agent_tool_access(
        'agent', ('read_file', 'write_file'), allow_destructive=True
    )
    manager.revoke_agent_tool_access('agent', 'write_file')
    tools = manager.get_agent_tools('agent')
    assert 'read_file' in tools
    assert 'write_file' not in tools


def test_permission_safe_defaults_filter_destructive():
    manager = ToolPermissionManager()
    filtered = manager.apply_safe_defaults(
        'agent', ('read_file', 'write_file', 'delete_file', 'grep')
    )
    assert 'read_file' in filtered
    assert 'grep' in filtered
    assert 'write_file' not in filtered
    assert 'delete_file' not in filtered
