"""Tests for governance hardening: SSH redaction, AST fuzz, HMAC queue, PermissionMode."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from teaagent.governance.tool_lint import fuzz_check_handler_code
from teaagent.policy import _verify_ssh_signature
from teaagent.redaction import RedactionConfig
from teaagent.types import PermissionMode


def _redact(text: str, ssh_keys: bool = True) -> str:
    cfg = RedactionConfig(ssh_keys=ssh_keys)
    patterns = cfg.build_patterns()
    result = text
    for pattern, replacement in patterns:
        result = pattern.sub(replacement, result)
    return result


def test_redacts_openssh_private_key() -> None:
    text = (
        '-----BEGIN OPENSSH PRIVATE KEY-----\ndata\n-----END OPENSSH PRIVATE KEY-----'
    )
    result = _redact(text)
    assert 'BEGIN OPENSSH PRIVATE KEY' not in result
    assert 'data' not in result
    assert '[redacted-ssh-key]' in result


def test_redacts_rsa_private_key() -> None:
    text = '-----BEGIN RSA PRIVATE KEY-----\ndata\n-----END RSA PRIVATE KEY-----'
    result = _redact(text)
    assert 'BEGIN RSA PRIVATE KEY' not in result
    assert 'data' not in result
    assert '[redacted-ssh-key]' in result


def test_redacts_ec_private_key() -> None:
    text = '-----BEGIN EC PRIVATE KEY-----\ndata\n-----END EC PRIVATE KEY-----'
    result = _redact(text)
    assert 'BEGIN EC PRIVATE KEY' not in result
    assert 'data' not in result
    assert '[redacted-ssh-key]' in result


def test_redacts_dsa_private_key() -> None:
    text = '-----BEGIN DSA PRIVATE KEY-----\ndata\n-----END DSA PRIVATE KEY-----'
    result = _redact(text)
    assert 'BEGIN DSA PRIVATE KEY' not in result
    assert 'data' not in result
    assert '[redacted-ssh-key]' in result


def test_ssh_redaction_disabled() -> None:
    text = (
        '-----BEGIN OPENSSH PRIVATE KEY-----\ndata\n-----END OPENSSH PRIVATE KEY-----'
    )
    result = _redact(text, ssh_keys=False)
    assert 'BEGIN OPENSSH PRIVATE KEY' in result
    assert 'data' in result
    assert '[redacted-ssh-key]' not in result


def test_mixed_content_redaction() -> None:
    text = (
        'before\n'
        '-----BEGIN OPENSSH PRIVATE KEY-----\n'
        'secretdata\n'
        '-----END OPENSSH PRIVATE KEY-----\n'
        'after'
    )
    result = _redact(text)
    assert 'before' in result
    assert 'after' in result
    assert 'secretdata' not in result
    assert '[redacted-ssh-key]' in result


def test_detects_subprocess_run() -> None:
    code = "def handler():\n    import subprocess\n    subprocess.run(['ls', '-la'])\n    return"
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'subprocess.run()' in ops


def test_detects_subprocess_call() -> None:
    code = "def handler():\n    import subprocess\n    subprocess.call(['git', 'pull'])\n    return"
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'subprocess.call()' in ops


def test_detects_subprocess_popen() -> None:
    code = "def handler():\n    import subprocess\n    subprocess.Popen(['make'])\n    return"
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'subprocess.Popen()' in ops


def test_detects_eval() -> None:
    code = "def handler():\n    eval('print(1)')\n    return"
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'eval()' in ops


def test_detects_exec() -> None:
    code = "def handler():\n    exec('print(1)')\n    return"
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'exec()' in ops


def test_detects_os_system() -> None:
    code = "def handler():\n    import os\n    os.system('rm -rf /')\n    return"
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'os.system()' in ops


def test_detects_os_remove() -> None:
    code = "def handler():\n    import os\n    os.remove('/tmp/foo')\n    return"
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'os.remove()' in ops


def test_detects_shutil_rmtree() -> None:
    code = (
        "def handler():\n    import shutil\n    shutil.rmtree('/tmp/build')\n    return"
    )
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'shutil.rmtree()' in ops


def test_detects_shutil_move() -> None:
    code = (
        "def handler():\n    import shutil\n    shutil.move('/src', '/dst')\n    return"
    )
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'shutil.move()' in ops


def test_clean_read_only_handler_passes() -> None:
    code = "def handler():\n    print('hello')\n    return"
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert ops == []


def test_non_read_only_skips_check() -> None:
    code = (
        "def handler():\n    import subprocess\n    subprocess.run(['ls'])\n    return"
    )
    ops = fuzz_check_handler_code(code, is_read_only=False)
    assert ops == []


def test_detects_subprocess_string_command() -> None:
    code = 'def handler():\n    import subprocess\n    subprocess.run("rm -rf /", shell=True)\n    return'
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'subprocess.run(string_cmd)' in ops


def test_detects_eval_dynamic() -> None:
    code = 'def handler():\n    eval(user_input)\n    return'
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'eval(dynamic)' in ops


def test_detects_exec_dynamic() -> None:
    code = 'def handler():\n    exec(code_string)\n    return'
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'exec(dynamic)' in ops


def test_allows_eval_literal() -> None:
    code = "def handler():\n    eval('2+2')\n    return"
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'eval()' in ops  # existing generic check still fires
    assert 'eval(dynamic)' not in ops  # new check does NOT fire for literals


def test_detects_os_system_string() -> None:
    code = "def handler():\n    import os\n    os.system('rm file')\n    return"
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'os.system(string_cmd)' in ops


@pytest.fixture
def store_path():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


def _make_store(
    store_path: Path, hmac_secret: str | None = None
) -> 'ApprovalQueueStore':  # type: ignore[name-defined]  # noqa: F821
    from teaagent.approval import ApprovalQueueStore

    return ApprovalQueueStore(store_path, hmac_secret=hmac_secret)


def test_save_without_hmac_backward_compatible(store_path: Path) -> None:
    """Save without hmac_secret, load succeeds (backward compat)."""
    store = _make_store(store_path)
    pid = 'test-no-hmac'
    store.save(pid, {}, {})
    snapshot = store.load(pid)
    assert snapshot.parent_run_id == pid


def test_save_with_hmac_includes_signature(store_path: Path) -> None:
    """Save with hmac_secret, verify ``_hmac`` key in JSON."""
    secret = '0123456789abcdef0123456789abcdef'
    store = _make_store(store_path, hmac_secret=secret)
    pid = 'test-with-hmac'
    store.save(pid, {}, {})
    raw = json.loads(store.queue_path(pid).read_text(encoding='utf-8'))
    assert '_hmac' in raw


def test_load_with_valid_hmac(store_path: Path) -> None:
    """Save with hmac, load with same hmac succeeds."""
    secret = '0123456789abcdef0123456789abcdef'
    store = _make_store(store_path, hmac_secret=secret)
    pid = 'test-valid-hmac'
    store.save(pid, {}, {})
    snapshot = store.load(pid)
    assert snapshot.parent_run_id == pid


def test_load_with_invalid_hmac_returns_empty(store_path: Path) -> None:
    """Save with hmac, tamper file, load returns empty snapshot."""
    secret = '0123456789abcdef0123456789abcdef'
    store = _make_store(store_path, hmac_secret=secret)
    pid = 'test-tamper-hmac'
    store.save(pid, {}, {})

    path = store.queue_path(pid)
    data = json.loads(path.read_text(encoding='utf-8'))
    data['requests']['evil'] = {'status': 'approved'}
    path.write_text(json.dumps(data), encoding='utf-8')

    snapshot = store.load(pid)
    assert snapshot.requests == {}


def test_load_with_missing_hmac_returns_empty(store_path: Path) -> None:
    """Save with hmac, remove ``_hmac`` key from file, load returns empty."""
    secret = '0123456789abcdef0123456789abcdef'
    store = _make_store(store_path, hmac_secret=secret)
    pid = 'test-missing-hmac-key'
    store.save(pid, {}, {})

    path = store.queue_path(pid)
    data = json.loads(path.read_text(encoding='utf-8'))
    data.pop('_hmac', None)
    path.write_text(json.dumps(data), encoding='utf-8')

    snapshot = store.load(pid)
    assert snapshot.requests == {}


def test_default_hmac_secret_from_env() -> None:
    """Verify ``default_hmac_secret()`` reads ``TEAAGENT_APPROVAL_HMAC_KEY``."""
    try:
        from teaagent.subagents._approval_queue_store import default_hmac_secret
    except ImportError:
        pytest.skip('default_hmac_secret not yet implemented')

    test_key = 'test-hmac-key-from-env'
    old = os.environ.get('TEAAGENT_APPROVAL_HMAC_KEY')
    try:
        os.environ['TEAAGENT_APPROVAL_HMAC_KEY'] = test_key
        result = default_hmac_secret()
        assert result == test_key
    finally:
        if old is None:
            os.environ.pop('TEAAGENT_APPROVAL_HMAC_KEY', None)
        else:
            os.environ['TEAAGENT_APPROVAL_HMAC_KEY'] = old


def test_hook_permission_mode_distinct_from_policy() -> None:
    from teaagent.hooks import HookPermissionMode

    assert HookPermissionMode is not PermissionMode
    assert not issubclass(HookPermissionMode, PermissionMode)
    assert not issubclass(PermissionMode, HookPermissionMode)


def test_hook_permission_mode_values() -> None:
    from teaagent.hooks import HookPermissionMode

    assert hasattr(HookPermissionMode, 'AUTO')
    assert hasattr(HookPermissionMode, 'ASK')
    assert hasattr(HookPermissionMode, 'ALLOW')
    assert hasattr(HookPermissionMode, 'DENY')


def test_policy_permission_mode_values() -> None:
    assert PermissionMode.READ_ONLY.value == 'read-only'
    assert PermissionMode.WORKSPACE_WRITE.value == 'workspace-write'
    assert PermissionMode.PROMPT.value == 'prompt'
    assert PermissionMode.ALLOW.value == 'allow'
    assert PermissionMode.DANGER_FULL_ACCESS.value == 'danger-full-access'


def test_ssh_verification_implemented_flag() -> None:
    from teaagent.approval_manager import _SSH_VERIFICATION_IMPLEMENTED

    assert _SSH_VERIFICATION_IMPLEMENTED


def test_ssh_verification_dev_hash_when_allowed() -> None:
    import hashlib

    pubkey = 'ssh-ed25519 AAAA'
    message = 'request-hash'
    expected = hashlib.sha256((message + pubkey).encode()).hexdigest()
    assert _verify_ssh_signature(
        signature=expected,
        message=message,
        ssh_key_id='peer1',
        peer_public_keys={'peer1': pubkey},
        allow_dev_signatures=True,
    )
    assert not _verify_ssh_signature(
        signature='bad',
        message=message,
        ssh_key_id='peer1',
        peer_public_keys={'peer1': pubkey},
        allow_dev_signatures=True,
    )


def test_ssh_verification_dev_hash_rejected_by_default() -> None:
    import hashlib

    pubkey = 'ssh-ed25519 AAAA'
    message = 'request-hash'
    expected = hashlib.sha256((message + pubkey).encode()).hexdigest()
    assert not _verify_ssh_signature(
        signature=expected,
        message=message,
        ssh_key_id='peer1',
        peer_public_keys={'peer1': pubkey},
    )
