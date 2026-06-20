"""Tests for ADR-0034: approval-queue HMAC mandatory by default.

Covers:
  (a) fresh workspace generates a key,
  (b) forged record is rejected,
  (c) existing valid record still validates after reload,
  (d) mode-0o600 enforcement refuses world-readable keys,
  (e) env var override works,
  (f) legacy accept escape works.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from teaagent.errors import ConfigError
from teaagent.subagents._approval_queue_store import (
    ApprovalQueueStore,
    default_hmac_secret,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Provide a clean workspace directory with no pre-existing key file."""
    ws = tmp_path / 'ws'
    ws.mkdir()
    return ws


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no leftover HMAC env vars leak between tests."""
    monkeypatch.delenv('TEAAGENT_APPROVAL_HMAC_KEY', raising=False)
    monkeypatch.delenv('TEAAGENT_APPROVAL_HMAC_LEGACY_ACCEPT', raising=False)


def _key_path(workspace: Path) -> Path:
    return workspace / '.teaagent' / 'approval_queue.key'


# ---------------------------------------------------------------------------
# (a) Fresh workspace generates a key
# ---------------------------------------------------------------------------


def test_fresh_workspace_generates_key(workspace: Path) -> None:
    """A store created without an explicit key generates and persists one."""
    store = ApprovalQueueStore(workspace)

    # hmac_secret must be set (not None, not empty)
    assert store.hmac_secret is not None
    assert store.hmac_secret != ''

    # Key file must exist with 0o600 permissions
    kp = _key_path(workspace)
    assert kp.is_file()
    mode = kp.stat().st_mode & 0o777
    assert mode == 0o600

    # Key must be 64 hex chars (32 bytes)
    key_hex = kp.read_text(encoding='utf-8').strip()
    assert len(key_hex) == 64
    bytes.fromhex(key_hex)  # must not raise


# ---------------------------------------------------------------------------
# (b) Forged record is rejected
# ---------------------------------------------------------------------------


def test_forged_record_rejected(workspace: Path) -> None:
    """A tampered queue file is rejected — load returns an empty snapshot."""
    store = ApprovalQueueStore(workspace)
    pid = 'run-forged'
    store.save(pid, {}, {})

    # Tamper: add a fake request without updating the HMAC
    path = store.queue_path(pid)
    data = json.loads(path.read_text(encoding='utf-8'))
    data['requests']['evil'] = {'status': 'approved', 'request_id': 'evil'}
    path.write_text(json.dumps(data), encoding='utf-8')

    snapshot = store.load(pid)
    assert snapshot.requests == {}


# ---------------------------------------------------------------------------
# (c) Existing valid record still validates after reload
# ---------------------------------------------------------------------------


def test_valid_record_validates_after_reload(workspace: Path) -> None:
    """A record signed with the persisted key validates on reload."""
    store1 = ApprovalQueueStore(workspace)
    pid = 'run-reload'
    store1.save(pid, {}, {})

    # Simulate a new process: create a fresh store pointing at the same workspace
    store2 = ApprovalQueueStore(workspace)
    assert store2.hmac_secret == store1.hmac_secret

    snapshot = store2.load(pid)
    assert snapshot.parent_run_id == pid


# ---------------------------------------------------------------------------
# (d) Mode-0o600 enforcement refuses world-readable keys
# ---------------------------------------------------------------------------


def test_world_readable_key_refused(workspace: Path) -> None:
    """A key file readable by group/other triggers ConfigError on load."""
    # First generate a valid key
    store = ApprovalQueueStore(workspace)
    assert store.hmac_secret is not None

    # Loosen permissions to world-readable
    kp = _key_path(workspace)
    kp.chmod(0o644)
    mode = kp.stat().st_mode & 0o777
    assert mode & 0o077, 'test precondition: key must be group/other readable'

    # A new store must refuse to load the key
    with pytest.raises(ConfigError) as exc_info:
        ApprovalQueueStore(workspace)

    msg = str(exc_info.value)
    assert str(kp) in msg
    assert 'chmod 0o600' in msg


# ---------------------------------------------------------------------------
# (e) Env var override works
# ---------------------------------------------------------------------------


def test_env_var_override(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TEAAGENT_APPROVAL_HMAC_KEY overrides the generated key."""
    explicit_key = 'my-explicit-key-for-testing'
    monkeypatch.setenv('TEAAGENT_APPROVAL_HMAC_KEY', explicit_key)

    store = ApprovalQueueStore(workspace)
    assert store.hmac_secret == explicit_key

    # Key file must NOT be generated when env var is set
    assert not _key_path(workspace).exists()

    # default_hmac_secret() also returns the env var
    assert default_hmac_secret() == explicit_key


# ---------------------------------------------------------------------------
# (f) Legacy accept escape works
# ---------------------------------------------------------------------------


def test_legacy_accept_escape(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TEAAGENT_APPROVAL_HMAC_LEGACY_ACCEPT=1 accepts pre-HMAC records."""
    # Generate a key and save a record (with HMAC)
    store = ApprovalQueueStore(workspace)
    pid = 'run-legacy'
    store.save(pid, {}, {})

    # Strip the HMAC to simulate a pre-HMAC record
    path = store.queue_path(pid)
    data = json.loads(path.read_text(encoding='utf-8'))
    data.pop('_hmac', None)
    path.write_text(json.dumps(data), encoding='utf-8')

    # Without legacy accept: rejected
    snapshot = store.load(pid)
    assert snapshot.requests == {}

    # With legacy accept: accepted
    monkeypatch.setenv('TEAAGENT_APPROVAL_HMAC_LEGACY_ACCEPT', '1')
    snapshot2 = store.load(pid)
    assert snapshot2.parent_run_id == pid
