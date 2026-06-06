from __future__ import annotations

import ast
from typing import Any, Optional

from teaagent.docker_sandbox import DockerSandbox

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
        selected_backend = _resolve_backend_with_fallback(
            backend or ChildProcessCodeModeBackend(),
            audit_logger=audit_logger,
            run_id=run_id,
        )
        return selected_backend.execute(code, safe_inputs, active_sandbox)
    except UnsafeCodeError as exc:
        if audit_logger is not None:
            audit_logger.record(
                'sandbox_violation',
                run_id,
                profile=profile.value if profile is not None else None,
                error=str(exc),
            )
        raise


def _resolve_backend_with_fallback(
    backend: CodeModeBackend,
    *,
    audit_logger: Any | None,
    run_id: str,
) -> CodeModeBackend:
    # Only container docker runtime requires host preflight fallback.
    if not isinstance(backend, ContainerCodeModeBackend):
        return backend
    if backend.runtime != 'docker':
        return backend

    sandbox = DockerSandbox(
        image=backend.image,
        cpu_cores=backend.cpus,
        memory_limit_mb=64.0,
        audit_logger=audit_logger,
        run_id=run_id,
    )
    preflight = sandbox.preflight()
    if preflight.get('status') == 'ok':
        return backend

    if audit_logger is not None:
        reason = preflight.get('reason', 'docker unavailable')
        audit_logger.record(
            'docker_preflight_failed',
            run_id,
            runtime='docker',
            reason=reason,
        )
        audit_logger.record(
            'sandbox_fallback_to_child_process',
            run_id,
            reason=reason,
            backend='child_process',
        )
    # Current fallback implementation uses local restricted backend.
    return ChildProcessCodeModeBackend()


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
