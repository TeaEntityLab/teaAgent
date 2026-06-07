from __future__ import annotations

import multiprocessing
import sys
import traceback
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from ._types import CodeModeResult, CodeModeSandbox
from ._validation import SAFE_BUILTINS, UnsafeCodeError, validate_plain_data

resource: Any = None
with suppress(ImportError):
    import resource  # noqa: F811


@dataclass(frozen=True)
class ChildProcessCodeModeBackend:
    """Fork-based Code Mode for trusted-user inputs only.

    For untrusted or multi-tenant workloads, use ``ContainerCodeModeBackend``.
    """

    trusted_only: bool = True

    def execute(
        self,
        code: str,
        inputs: dict[str, Any],
        sandbox: CodeModeSandbox,
    ) -> CodeModeResult:
        if not self.trusted_only:
            raise ValueError(
                'ChildProcessCodeModeBackend is for trusted inputs only; '
                'use ContainerCodeModeBackend for untrusted workloads'
            )
        ctx: Any = multiprocessing
        with suppress(ValueError):
            # Prefer fork on POSIX to avoid spawn startup overhead in short timeouts.
            ctx = multiprocessing.get_context('fork')
        parent_conn, child_conn = ctx.Pipe(duplex=False)
        process = ctx.Process(
            target=_execute_code_mode_child,
            args=(code, inputs, sandbox, child_conn),
        )
        process.start()
        process.join(sandbox.timeout_seconds)
        if process.is_alive():
            process.terminate()
            process.join()
            raise UnsafeCodeError('Code Mode timed out')

        if parent_conn.poll():
            message = parent_conn.recv()
        else:
            raise UnsafeCodeError('Code Mode sandbox exited without a result')

        if message['status'] == 'error':
            raise UnsafeCodeError(message['error'])
        variables = message['variables']
        validate_plain_data(variables, 'variables')
        return CodeModeResult(variables=variables)


def _execute_code_mode_child(
    code: str,
    inputs: dict[str, Any],
    sandbox: CodeModeSandbox,
    result_pipe: multiprocessing.connection.Connection,
) -> None:
    try:
        _apply_resource_limits(sandbox)
        namespace: dict[str, Any] = {'__builtins__': SAFE_BUILTINS}
        namespace.update(inputs)
        # exec() is sandboxed with SAFE_BUILTINS to restrict dangerous operations
        exec(compile(code, '<teaagent-code-mode>', 'exec'), namespace, namespace)  # noqa: B102
        variables = {
            key: value
            for key, value in namespace.items()
            if key != '__builtins__' and not key.startswith('_')
        }
        validate_plain_data(variables, 'variables')
    except Exception as exc:  # pragma: no cover - exercised through parent process.
        result_pipe.send(
            {
                'status': 'error',
                'error': f'{type(exc).__name__}: {exc}',
                'traceback': traceback.format_exc(),
            }
        )
    else:
        result_pipe.send({'status': 'ok', 'variables': variables})


def _apply_resource_limits(sandbox: CodeModeSandbox) -> None:
    if resource is None:
        return
    _, cpu_hard = resource.getrlimit(resource.RLIMIT_CPU)
    resource.setrlimit(resource.RLIMIT_CPU, (sandbox.cpu_seconds, cpu_hard))
    # RLIMIT_AS is unreliable on macOS and can terminate the child before it
    # initializes, which surfaces as a parent-side timeout for safe snippets.
    if hasattr(resource, 'RLIMIT_AS') and sys.platform != 'darwin':
        _, hard = resource.getrlimit(resource.RLIMIT_AS)
        soft = sandbox.memory_bytes
        if hard != resource.RLIM_INFINITY:
            soft = min(soft, hard)
        with suppress(ValueError):
            resource.setrlimit(resource.RLIMIT_AS, (soft, hard))

    # Limit child processes to prevent fork bombs
    if hasattr(resource, 'RLIMIT_NPROC'):
        try:
            _, nproc_hard = resource.getrlimit(resource.RLIMIT_NPROC)
            # Allow at most 8 child processes (plus the code mode process itself)
            resource.setrlimit(
                resource.RLIMIT_NPROC,
                (
                    8,
                    min(nproc_hard, 16) if nproc_hard != resource.RLIM_INFINITY else 16,
                ),
            )
        except (ValueError, OSError):
            pass  # Platform doesn't support or permission denied
