from __future__ import annotations

import ast
from typing import Any

from ._child_process import ChildProcessCodeModeBackend
from ._container import CONTAINER_CODE_MODE_SCRIPT, ContainerCodeModeBackend
from ._types import CodeModeBackend, CodeModeResult, CodeModeSandbox, SandboxProfile
from ._validation import (
    ALLOWED_NODES,
    SAFE_BUILTINS,
    UnsafeCodeError,
    validate_plain_data,
    validate_tree,
)


def execute_code_mode(
    code: str,
    *,
    inputs: dict[str, Any] | None = None,
    sandbox: CodeModeSandbox | None = None,
    backend: CodeModeBackend | None = None,
) -> CodeModeResult:
    tree = ast.parse(code, mode='exec')
    validate_tree(tree)
    safe_inputs = dict(inputs or {})
    validate_plain_data(safe_inputs, 'inputs')

    active_sandbox = sandbox or CodeModeSandbox()
    if active_sandbox.timeout_seconds <= 0:
        raise UnsafeCodeError('Code Mode timeout must be positive')
    if active_sandbox.cpu_seconds <= 0:
        raise UnsafeCodeError('Code Mode CPU limit must be positive')
    if active_sandbox.memory_bytes <= 0:
        raise UnsafeCodeError('Code Mode memory limit must be positive')

    return (backend or ChildProcessCodeModeBackend()).execute(
        code, safe_inputs, active_sandbox
    )


__all__ = [
    'ALLOWED_NODES',
    'CONTAINER_CODE_MODE_SCRIPT',
    'SAFE_BUILTINS',
    'ChildProcessCodeModeBackend',
    'CodeModeBackend',
    'CodeModeResult',
    'CodeModeSandbox',
    'ContainerCodeModeBackend',
    'UnsafeCodeError',
    'execute_code_mode',
    'SandboxProfile',
]
