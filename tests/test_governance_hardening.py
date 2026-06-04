"""Tests for governance hardening: SSH redaction, AST fuzz, HMAC queue, PermissionMode."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from teaagent.governance.tool_lint import fuzz_check_handler_code
from teaagent.policy import PermissionMode, _verify_ssh_signature
from teaagent.redaction import RedactionConfig


class SSHKeyRedactionTests(unittest.TestCase):
    """RedactionConfig SSH private key redaction."""

    def _redact(self, text: str, ssh_keys: bool = True) -> str:
        cfg = RedactionConfig(ssh_keys=ssh_keys)
        patterns = cfg.build_patterns()
        result = text
        for pattern, replacement in patterns:
            result = pattern.sub(replacement, result)
        return result

    def test_redacts_openssh_private_key(self) -> None:
        text = '-----BEGIN OPENSSH PRIVATE KEY-----\ndata\n-----END OPENSSH PRIVATE KEY-----'
        result = self._redact(text)
        self.assertNotIn('BEGIN OPENSSH PRIVATE KEY', result)
        self.assertNotIn('data', result)
        self.assertIn('[redacted-ssh-key]', result)

    def test_redacts_rsa_private_key(self) -> None:
        text = '-----BEGIN RSA PRIVATE KEY-----\ndata\n-----END RSA PRIVATE KEY-----'
        result = self._redact(text)
        self.assertNotIn('BEGIN RSA PRIVATE KEY', result)
        self.assertNotIn('data', result)
        self.assertIn('[redacted-ssh-key]', result)

    def test_redacts_ec_private_key(self) -> None:
        text = '-----BEGIN EC PRIVATE KEY-----\ndata\n-----END EC PRIVATE KEY-----'
        result = self._redact(text)
        self.assertNotIn('BEGIN EC PRIVATE KEY', result)
        self.assertNotIn('data', result)
        self.assertIn('[redacted-ssh-key]', result)

    def test_redacts_dsa_private_key(self) -> None:
        text = '-----BEGIN DSA PRIVATE KEY-----\ndata\n-----END DSA PRIVATE KEY-----'
        result = self._redact(text)
        self.assertNotIn('BEGIN DSA PRIVATE KEY', result)
        self.assertNotIn('data', result)
        self.assertIn('[redacted-ssh-key]', result)

    def test_ssh_redaction_disabled(self) -> None:
        text = '-----BEGIN OPENSSH PRIVATE KEY-----\ndata\n-----END OPENSSH PRIVATE KEY-----'
        result = self._redact(text, ssh_keys=False)
        self.assertIn('BEGIN OPENSSH PRIVATE KEY', result)
        self.assertIn('data', result)
        self.assertNotIn('[redacted-ssh-key]', result)

    def test_mixed_content_redaction(self) -> None:
        text = (
            'before\n'
            '-----BEGIN OPENSSH PRIVATE KEY-----\n'
            'secretdata\n'
            '-----END OPENSSH PRIVATE KEY-----\n'
            'after'
        )
        result = self._redact(text)
        self.assertIn('before', result)
        self.assertIn('after', result)
        self.assertNotIn('secretdata', result)
        self.assertIn('[redacted-ssh-key]', result)


class ExpandedASTFuzzTests(unittest.TestCase):
    """Expanded fuzz_check_handler_code for subprocess/os/shutil/eval/exec."""

    def test_detects_subprocess_run(self) -> None:
        code = "def handler():\n    import subprocess\n    subprocess.run(['ls', '-la'])\n    return"
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn('subprocess.run()', ops)

    def test_detects_subprocess_call(self) -> None:
        code = "def handler():\n    import subprocess\n    subprocess.call(['git', 'pull'])\n    return"
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn('subprocess.call()', ops)

    def test_detects_subprocess_popen(self) -> None:
        code = "def handler():\n    import subprocess\n    subprocess.Popen(['make'])\n    return"
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn('subprocess.Popen()', ops)

    def test_detects_eval(self) -> None:
        code = "def handler():\n    eval('print(1)')\n    return"
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn('eval()', ops)

    def test_detects_exec(self) -> None:
        code = "def handler():\n    exec('print(1)')\n    return"
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn('exec()', ops)

    def test_detects_os_system(self) -> None:
        code = "def handler():\n    import os\n    os.system('rm -rf /')\n    return"
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn('os.system()', ops)

    def test_detects_os_remove(self) -> None:
        code = "def handler():\n    import os\n    os.remove('/tmp/foo')\n    return"
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn('os.remove()', ops)

    def test_detects_shutil_rmtree(self) -> None:
        code = "def handler():\n    import shutil\n    shutil.rmtree('/tmp/build')\n    return"
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn('shutil.rmtree()', ops)

    def test_detects_shutil_move(self) -> None:
        code = "def handler():\n    import shutil\n    shutil.move('/src', '/dst')\n    return"
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn('shutil.move()', ops)

    def test_clean_read_only_handler_passes(self) -> None:
        code = "def handler():\n    print('hello')\n    return"
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertEqual(ops, [])

    def test_non_read_only_skips_check(self) -> None:
        code = "def handler():\n    import subprocess\n    subprocess.run(['ls'])\n    return"
        ops = fuzz_check_handler_code(code, is_read_only=False)
        self.assertEqual(ops, [])

    def test_detects_subprocess_string_command(self) -> None:
        code = 'def handler():\n    import subprocess\n    subprocess.run("rm -rf /", shell=True)\n    return'
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn('subprocess.run(string_cmd)', ops)

    def test_detects_eval_dynamic(self) -> None:
        code = 'def handler():\n    eval(user_input)\n    return'
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn('eval(dynamic)', ops)

    def test_detects_exec_dynamic(self) -> None:
        code = 'def handler():\n    exec(code_string)\n    return'
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn('exec(dynamic)', ops)

    def test_allows_eval_literal(self) -> None:
        code = "def handler():\n    eval('2+2')\n    return"
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn('eval()', ops)  # existing generic check still fires
        self.assertNotIn('eval(dynamic)', ops)  # new check does NOT fire for literals

    def test_detects_os_system_string(self) -> None:
        code = "def handler():\n    import os\n    os.system('rm file')\n    return"
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn('os.system(string_cmd)', ops)


class HMACApprovalQueueTests(unittest.TestCase):
    """ApprovalQueueStore HMAC integrity verification (expected after fixes).

    These tests describe the expected API contract after HMAC sealing is
    implemented in ApprovalQueueStore.  They may fail with TypeError if the
    underlying implementation has not landed yet.
    """

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.tmpdir.name)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _make_store(self, hmac_secret: str | None = None) -> 'ApprovalQueueStore':  # noqa: F821
        from teaagent.subagents._approval_queue_store import ApprovalQueueStore

        return ApprovalQueueStore(self.store_path, hmac_secret=hmac_secret)

    def test_save_without_hmac_backward_compatible(self) -> None:
        """Save without hmac_secret, load succeeds (backward compat)."""
        store = self._make_store()
        pid = 'test-no-hmac'
        store.save(pid, {}, {})
        snapshot = store.load(pid)
        self.assertEqual(snapshot.parent_run_id, pid)

    def test_save_with_hmac_includes_signature(self) -> None:
        """Save with hmac_secret, verify ``_hmac`` key in JSON."""
        secret = '0123456789abcdef0123456789abcdef'
        store = self._make_store(hmac_secret=secret)
        pid = 'test-with-hmac'
        store.save(pid, {}, {})
        raw = json.loads(store.queue_path(pid).read_text(encoding='utf-8'))
        self.assertIn('_hmac', raw)

    def test_load_with_valid_hmac(self) -> None:
        """Save with hmac, load with same hmac succeeds."""
        secret = '0123456789abcdef0123456789abcdef'
        store = self._make_store(hmac_secret=secret)
        pid = 'test-valid-hmac'
        store.save(pid, {}, {})
        snapshot = store.load(pid)
        self.assertEqual(snapshot.parent_run_id, pid)

    def test_load_with_invalid_hmac_returns_empty(self) -> None:
        """Save with hmac, tamper file, load returns empty snapshot."""
        secret = '0123456789abcdef0123456789abcdef'
        store = self._make_store(hmac_secret=secret)
        pid = 'test-tamper-hmac'
        store.save(pid, {}, {})

        path = store.queue_path(pid)
        data = json.loads(path.read_text(encoding='utf-8'))
        data['requests']['evil'] = {'status': 'approved'}
        path.write_text(json.dumps(data), encoding='utf-8')

        snapshot = store.load(pid)
        self.assertEqual(snapshot.requests, {})

    def test_load_with_missing_hmac_returns_empty(self) -> None:
        """Save with hmac, remove ``_hmac`` key from file, load returns empty."""
        secret = '0123456789abcdef0123456789abcdef'
        store = self._make_store(hmac_secret=secret)
        pid = 'test-missing-hmac-key'
        store.save(pid, {}, {})

        path = store.queue_path(pid)
        data = json.loads(path.read_text(encoding='utf-8'))
        data.pop('_hmac', None)
        path.write_text(json.dumps(data), encoding='utf-8')

        snapshot = store.load(pid)
        self.assertEqual(snapshot.requests, {})

    def test_default_hmac_secret_from_env(self) -> None:
        """Verify ``default_hmac_secret()`` reads ``TEAAGENT_APPROVAL_HMAC_KEY``."""
        try:
            from teaagent.subagents._approval_queue_store import default_hmac_secret
        except ImportError:
            self.skipTest('default_hmac_secret not yet implemented')

        test_key = 'test-hmac-key-from-env'
        old = os.environ.get('TEAAGENT_APPROVAL_HMAC_KEY')
        try:
            os.environ['TEAAGENT_APPROVAL_HMAC_KEY'] = test_key
            result = default_hmac_secret()
            self.assertEqual(result, test_key)
        finally:
            if old is None:
                os.environ.pop('TEAAGENT_APPROVAL_HMAC_KEY', None)
            else:
                os.environ['TEAAGENT_APPROVAL_HMAC_KEY'] = old


class PermissionModeCollisionTests(unittest.TestCase):
    """HookPermissionMode vs policy.PermissionMode are distinct enums."""

    def test_hook_permission_mode_distinct_from_policy(self) -> None:
        from teaagent.hooks import HookPermissionMode

        self.assertIsNot(HookPermissionMode, PermissionMode)
        self.assertFalse(issubclass(HookPermissionMode, PermissionMode))
        self.assertFalse(issubclass(PermissionMode, HookPermissionMode))

    def test_hook_permission_mode_values(self) -> None:
        from teaagent.hooks import HookPermissionMode

        self.assertTrue(hasattr(HookPermissionMode, 'AUTO'))
        self.assertTrue(hasattr(HookPermissionMode, 'ASK'))
        self.assertTrue(hasattr(HookPermissionMode, 'ALLOW'))
        self.assertTrue(hasattr(HookPermissionMode, 'DENY'))

    def test_policy_permission_mode_values(self) -> None:
        self.assertEqual(PermissionMode.READ_ONLY.value, 'read-only')
        self.assertEqual(PermissionMode.WORKSPACE_WRITE.value, 'workspace-write')
        self.assertEqual(PermissionMode.PROMPT.value, 'prompt')
        self.assertEqual(PermissionMode.ALLOW.value, 'allow')
        self.assertEqual(PermissionMode.DANGER_FULL_ACCESS.value, 'danger-full-access')


class MultiSigPlaceholderTests(unittest.TestCase):
    """Multi-sig SSH placeholder flag and warning."""

    def test_ssh_verification_implemented_flag(self) -> None:
        from teaagent.approval_manager import _SSH_VERIFICATION_IMPLEMENTED

        self.assertTrue(_SSH_VERIFICATION_IMPLEMENTED)

    def test_ssh_verification_dev_hash_when_allowed(self) -> None:
        import hashlib

        pubkey = 'ssh-ed25519 AAAA'
        message = 'request-hash'
        expected = hashlib.sha256((message + pubkey).encode()).hexdigest()
        self.assertTrue(
            _verify_ssh_signature(
                signature=expected,
                message=message,
                ssh_key_id='peer1',
                peer_public_keys={'peer1': pubkey},
                allow_dev_signatures=True,
            )
        )
        self.assertFalse(
            _verify_ssh_signature(
                signature='bad',
                message=message,
                ssh_key_id='peer1',
                peer_public_keys={'peer1': pubkey},
                allow_dev_signatures=True,
            )
        )

    def test_ssh_verification_dev_hash_rejected_by_default(self) -> None:
        import hashlib

        pubkey = 'ssh-ed25519 AAAA'
        message = 'request-hash'
        expected = hashlib.sha256((message + pubkey).encode()).hexdigest()
        self.assertFalse(
            _verify_ssh_signature(
                signature=expected,
                message=message,
                ssh_key_id='peer1',
                peer_public_keys={'peer1': pubkey},
            )
        )


if __name__ == '__main__':
    unittest.main()
