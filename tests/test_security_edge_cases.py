"""Edge case tests for security fixes."""
from __future__ import annotations

import unittest

from teaagent.governance.tool_lint import fuzz_check_handler_code
from teaagent.policy import PermissionMode
from teaagent.redaction import RedactionConfig


class SSHRedactionEdgeCases(unittest.TestCase):
    def test_nested_ssh_keys(self) -> None:
        """SSH key embedded in JSON should be redacted."""
        text = '{"key": "-----BEGIN OPENSSH PRIVATE KEY-----\\ndata\\n-----END OPENSSH PRIVATE KEY-----"}'
        config = RedactionConfig()
        patterns = config.build_patterns()
        for pattern, replacement in patterns:
            text = pattern.sub(replacement, text)
        self.assertNotIn("BEGIN OPENSSH", text)

    def test_multiple_ssh_keys(self) -> None:
        """Multiple SSH keys in same text should all be redacted."""
        text = "-----BEGIN RSA PRIVATE KEY-----\\nkey1\\n-----END RSA PRIVATE KEY-----\\n-----BEGIN EC PRIVATE KEY-----\\nkey2\\n-----END EC PRIVATE KEY-----"
        config = RedactionConfig()
        patterns = config.build_patterns()
        for pattern, replacement in patterns:
            text = pattern.sub(replacement, text)
        self.assertEqual(text.count("[redacted-ssh-key]"), 2)

    def test_partial_ssh_key_not_redacted(self) -> None:
        """Incomplete SSH key (missing END) should not be redacted."""
        text = "-----BEGIN OPENSSH PRIVATE KEY-----\\ndata\\n"
        config = RedactionConfig()
        patterns = config.build_patterns()
        for pattern, replacement in patterns:
            text = pattern.sub(replacement, text)
        self.assertIn("BEGIN OPENSSH", text)

class PermissionModeEdgeCases(unittest.TestCase):
    def test_hook_permission_mode_isolation(self) -> None:
        """HookPermissionMode should not interfere with policy.PermissionMode."""
        from teaagent.hooks import HookPermissionMode
        self.assertIsNot(HookPermissionMode.ALLOW, PermissionMode.ALLOW)

    def test_hook_permission_mode_string_values(self) -> None:
        """HookPermissionMode values should be strings."""
        from teaagent.hooks import HookPermissionMode
        self.assertEqual(HookPermissionMode.AUTO.value, 'auto')
        self.assertEqual(HookPermissionMode.ASK.value, 'ask')

class ASTFuzzEdgeCases(unittest.TestCase):
    def test_nested_function_calls(self) -> None:
        """Nested write calls should all be detected."""
        code = "def handler():\n    obj.write(obj.save())\n    return"
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn("write()", ops)
        self.assertIn("save()", ops)

    def test_comprehension_with_write(self) -> None:
        """Write in list comprehension should be detected."""
        code = "def handler():\n    [f.write(x) for x in data]\n    return"
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn("write()", ops)

    def test_lambda_with_write(self) -> None:
        """Write in lambda should be detected."""
        code = "def handler():\n    fn = lambda: f.write('x')\n    return"
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn("write()", ops)

    def test_try_except_with_write(self) -> None:
        """Write in try block should be detected."""
        code = "def handler():\n    try:\n        f.write('x')\n    except:\n        pass\n    return"
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn("write()", ops)

    def test_async_function_with_write(self) -> None:
        """Write in async function should be detected."""
        code = "async def handler():\n    await f.write('x')\n    return"
        ops = fuzz_check_handler_code(code, is_read_only=True)
        self.assertIn("write()", ops)
