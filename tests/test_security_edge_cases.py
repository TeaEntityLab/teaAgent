"""Edge case tests for security fixes."""

from __future__ import annotations

from teaagent.governance.tool_lint import fuzz_check_handler_code
from teaagent.redaction import RedactionConfig
from teaagent.types import PermissionMode


def test_nested_ssh_keys() -> None:
    """SSH key embedded in JSON should be redacted."""
    text = '{"key": "-----BEGIN OPENSSH PRIVATE KEY-----\\ndata\\n-----END OPENSSH PRIVATE KEY-----"}'
    config = RedactionConfig()
    patterns = config.build_patterns()
    for pattern, replacement in patterns:
        text = pattern.sub(replacement, text)
    assert 'BEGIN OPENSSH' not in text


def test_multiple_ssh_keys() -> None:
    """Multiple SSH keys in same text should all be redacted."""
    text = '-----BEGIN RSA PRIVATE KEY-----\\nkey1\\n-----END RSA PRIVATE KEY-----\\n-----BEGIN EC PRIVATE KEY-----\\nkey2\\n-----END EC PRIVATE KEY-----'
    config = RedactionConfig()
    patterns = config.build_patterns()
    for pattern, replacement in patterns:
        text = pattern.sub(replacement, text)
    assert text.count('[redacted-ssh-key]') == 2


def test_partial_ssh_key_not_redacted() -> None:
    """Incomplete SSH key (missing END) should not be redacted."""
    text = '-----BEGIN OPENSSH PRIVATE KEY-----\\ndata\\n'
    config = RedactionConfig()
    patterns = config.build_patterns()
    for pattern, replacement in patterns:
        text = pattern.sub(replacement, text)
    assert 'BEGIN OPENSSH' in text


def test_hook_permission_mode_isolation() -> None:
    """HookPermissionMode should not interfere with policy.PermissionMode."""
    from teaagent.hooks import HookPermissionMode

    assert HookPermissionMode.ALLOW is not PermissionMode.ALLOW


def test_hook_permission_mode_string_values() -> None:
    """HookPermissionMode values should be strings."""
    from teaagent.hooks import HookPermissionMode

    assert HookPermissionMode.AUTO.value == 'auto'
    assert HookPermissionMode.ASK.value == 'ask'


def test_nested_function_calls() -> None:
    """Nested write calls should all be detected."""
    code = 'def handler():\n    obj.write(obj.save())\n    return'
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'write()' in ops
    assert 'save()' in ops


def test_comprehension_with_write() -> None:
    """Write in list comprehension should be detected."""
    code = 'def handler():\n    [f.write(x) for x in data]\n    return'
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'write()' in ops


def test_lambda_with_write() -> None:
    """Write in lambda should be detected."""
    code = "def handler():\n    fn = lambda: f.write('x')\n    return"
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'write()' in ops


def test_try_except_with_write() -> None:
    """Write in try block should be detected."""
    code = "def handler():\n    try:\n        f.write('x')\n    except:\n        pass\n    return"
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'write()' in ops


def test_async_function_with_write() -> None:
    """Write in async function should be detected."""
    code = "async def handler():\n    await f.write('x')\n    return"
    ops = fuzz_check_handler_code(code, is_read_only=True)
    assert 'write()' in ops
