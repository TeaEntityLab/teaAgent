from __future__ import annotations

import ast
from typing import Any, Optional

from ._child_process import ChildProcessCodeModeBackend
from ._container import CONTAINER_CODE_MODE_SCRIPT, ContainerCodeModeBackend
from ._isolate import IsolateCodeModeBackend
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
    profile: Optional[SandboxProfile] = None,
    audit_logger: Any | None = None,
    run_id: str = '',
) -> CodeModeResult:
    safe_inputs = dict(inputs or {})

    if profile is not None and sandbox is None:
        active_sandbox = profile.default_sandbox()
    else:
        active_sandbox = sandbox or CodeModeSandbox()

    if active_sandbox.timeout_seconds <= 0:
        raise UnsafeCodeError('Code Mode timeout must be positive')
    if active_sandbox.cpu_seconds <= 0:
        raise UnsafeCodeError('Code Mode CPU limit must be positive')
    if active_sandbox.memory_bytes <= 0:
        raise UnsafeCodeError('Code Mode memory limit must be positive')

    if audit_logger is not None:
        audit_logger.record(
            'sandbox_profile_selected',
            run_id,
            profile=profile.value if profile is not None else None,
            timeout_seconds=active_sandbox.timeout_seconds,
            cpu_seconds=active_sandbox.cpu_seconds,
            memory_bytes=active_sandbox.memory_bytes,
        )

    try:
        tree = ast.parse(code, mode='exec')
        validate_tree(tree)
        validate_plain_data(safe_inputs, 'inputs')
        return (backend or ChildProcessCodeModeBackend()).execute(
            code, safe_inputs, active_sandbox
        )
    except UnsafeCodeError as exc:
        if audit_logger is not None:
            audit_logger.record(
                'sandbox_violation',
                run_id,
                profile=profile.value if profile is not None else None,
                error=str(exc),
            )
        raise


__all__ = [
    'ALLOWED_NODES',
    'CONTAINER_CODE_MODE_SCRIPT',
    'SAFE_BUILTINS',
    'ChildProcessCodeModeBackend',
    'CodeModeBackend',
    'CodeModeResult',
    'CodeModeSandbox',
    'ContainerCodeModeBackend',
    'IsolateCodeModeBackend',
    'UnsafeCodeError',
    'execute_code_mode',
    'SandboxProfile',
]
