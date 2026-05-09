from __future__ import annotations

import multiprocessing
import traceback
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from ._types import CodeModeResult, CodeModeSandbox
from ._validation import SAFE_BUILTINS, UnsafeCodeError, validate_plain_data

try:
    import resource
except ImportError:  # pragma: no cover - resource is Unix-only.
    resource = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ChildProcessCodeModeBackend:
    def execute(
        self,
        code: str,
        inputs: dict[str, Any],
        sandbox: CodeModeSandbox,
    ) -> CodeModeResult:
        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
        process = multiprocessing.Process(
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
        exec(compile(code, '<teaagent-code-mode>', 'exec'), namespace, namespace)
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
    if hasattr(resource, 'RLIMIT_AS'):
        _, hard = resource.getrlimit(resource.RLIMIT_AS)
        soft = sandbox.memory_bytes
        if hard != resource.RLIM_INFINITY:
            soft = min(soft, hard)
        with suppress(ValueError):
            resource.setrlimit(resource.RLIMIT_AS, (soft, hard))
