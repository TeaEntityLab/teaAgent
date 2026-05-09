from __future__ import annotations

import ast
import json
import multiprocessing
import subprocess
import traceback
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Protocol

try:
    import resource
except ImportError:  # pragma: no cover - resource is Unix-only.
    resource = None  # type: ignore[assignment]

ALLOWED_NODES = {
    ast.Add,
    ast.Assign,
    ast.BinOp,
    ast.Call,
    ast.Compare,
    ast.Constant,
    ast.Dict,
    ast.Div,
    ast.Eq,
    ast.Expr,
    ast.For,
    ast.Gt,
    ast.GtE,
    ast.If,
    ast.In,
    ast.List,
    ast.Load,
    ast.Lt,
    ast.LtE,
    ast.Mod,
    ast.Module,
    ast.Mult,
    ast.Name,
    ast.NotEq,
    ast.Store,
    ast.Sub,
    ast.Subscript,
    ast.Tuple,
    ast.UnaryOp,
    ast.USub,
}

SAFE_BUILTINS = {
    'abs': abs,
    'dict': dict,
    'enumerate': enumerate,
    'len': len,
    'list': list,
    'max': max,
    'min': min,
    'range': range,
    'round': round,
    'sorted': sorted,
    'str': str,
    'sum': sum,
}


@dataclass(frozen=True)
class CodeModeResult:
    variables: dict[str, Any]


@dataclass(frozen=True)
class CodeModeSandbox:
    timeout_seconds: float = 2.0
    cpu_seconds: int = 2
    memory_bytes: int = 64 * 1024 * 1024
    max_output_bytes: int = 1 * 1024 * 1024


class CodeModeBackend(Protocol):
    def execute(
        self,
        code: str,
        inputs: dict[str, Any],
        sandbox: CodeModeSandbox,
    ) -> CodeModeResult: ...


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
        _validate_plain_data(variables, 'variables')
        return CodeModeResult(variables=variables)


@dataclass(frozen=True)
class ContainerCodeModeBackend:
    image: str
    runtime: str = 'docker'
    python_executable: str = 'python3'
    network: str = 'none'
    cpus: float = 1.0
    user: str = '65534:65534'
    tmpfs_size_mb: int = 16

    def __post_init__(self) -> None:
        if not self.image:
            raise UnsafeCodeError('Code Mode container image must be configured')
        if self.cpus <= 0:
            raise UnsafeCodeError('Code Mode container cpus must be positive')
        if self.tmpfs_size_mb <= 0:
            raise UnsafeCodeError('Code Mode container tmpfs size must be positive')

    def execute(
        self,
        code: str,
        inputs: dict[str, Any],
        sandbox: CodeModeSandbox,
    ) -> CodeModeResult:
        payload = json.dumps({'code': code, 'inputs': inputs})
        try:
            process = subprocess.Popen(
                self._build_command(sandbox),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            raise UnsafeCodeError(f'Code Mode container runtime failed: {exc}') from exc
        try:
            stdout, stderr = process.communicate(
                payload, timeout=sandbox.timeout_seconds
            )
        except subprocess.TimeoutExpired as exc:
            process.kill()
            with suppress(Exception):
                process.communicate()
            raise UnsafeCodeError('Code Mode timed out') from exc
        if len(stdout) > sandbox.max_output_bytes:
            raise UnsafeCodeError('Code Mode container exceeded output limit')
        if process.returncode != 0:
            detail = (stderr or stdout).strip()
            raise UnsafeCodeError(f'Code Mode container failed: {detail}')
        try:
            message = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise UnsafeCodeError('Code Mode container returned invalid JSON') from exc
        if message.get('status') == 'error':
            raise UnsafeCodeError(str(message.get('error', 'unknown error')))
        variables = message.get('variables')
        _validate_plain_data(variables, 'variables')
        return CodeModeResult(variables=variables)

    def _build_command(self, sandbox: CodeModeSandbox) -> list[str]:
        memory_mb = max(1, sandbox.memory_bytes // (1024 * 1024))
        return [
            self.runtime,
            'run',
            '--rm',
            '--network',
            self.network,
            '--read-only',
            '--cap-drop=ALL',
            '--security-opt=no-new-privileges',
            f'--user={self.user}',
            f'--tmpfs=/tmp:rw,size={self.tmpfs_size_mb}m',
            '--memory',
            f'{memory_mb}m',
            '--memory-swap',
            f'{memory_mb}m',
            '--cpus',
            f'{self.cpus}',
            '--ulimit',
            f'cpu={sandbox.cpu_seconds}:{sandbox.cpu_seconds}',
            '--pids-limit',
            '64',
            '-i',
            self.image,
            self.python_executable,
            '-c',
            CONTAINER_CODE_MODE_SCRIPT,
        ]


class UnsafeCodeError(ValueError):
    pass


def execute_code_mode(
    code: str,
    *,
    inputs: dict[str, Any] | None = None,
    sandbox: CodeModeSandbox | None = None,
    backend: CodeModeBackend | None = None,
) -> CodeModeResult:
    tree = ast.parse(code, mode='exec')
    _validate_tree(tree)
    safe_inputs = dict(inputs or {})
    _validate_plain_data(safe_inputs, 'inputs')

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


CONTAINER_CODE_MODE_SCRIPT = r"""
import json
import sys
import traceback

SAFE_BUILTINS = {
    'abs': abs,
    'dict': dict,
    'enumerate': enumerate,
    'len': len,
    'list': list,
    'max': max,
    'min': min,
    'range': range,
    'round': round,
    'sorted': sorted,
    'str': str,
    'sum': sum,
}

def validate(value, label):
    if value is None or isinstance(value, (bool, int, float, str)):
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            validate(item, f'{label}[{index}]')
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f'{label} contains a non-string key')
            validate(item, f'{label}.{key}')
        return
    raise ValueError(f'{label} contains unsupported value type: {type(value).__name__}')

try:
    payload = json.loads(sys.stdin.read())
    namespace = {'__builtins__': SAFE_BUILTINS}
    namespace.update(payload['inputs'])
    exec(compile(payload['code'], '<teaagent-code-mode>', 'exec'), namespace, namespace)
    variables = {
        key: value
        for key, value in namespace.items()
        if key != '__builtins__' and not key.startswith('_')
    }
    validate(variables, 'variables')
except Exception as exc:
    print(json.dumps({'status': 'error', 'error': f'{type(exc).__name__}: {exc}', 'traceback': traceback.format_exc()}))
else:
    print(json.dumps({'status': 'ok', 'variables': variables}))
"""


def _validate_tree(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if type(node) not in ALLOWED_NODES:
            raise UnsafeCodeError(f'Disallowed syntax: {type(node).__name__}')
        if isinstance(node, ast.Call) and (
            not isinstance(node.func, ast.Name) or node.func.id not in SAFE_BUILTINS
        ):
            raise UnsafeCodeError('Only approved builtin calls are allowed')


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
        _validate_plain_data(variables, 'variables')
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
        # macOS reports RLIMIT_AS but rejects lowering it; wall/CPU limits still
        # keep Code Mode isolated from the parent process.
        with suppress(ValueError):
            resource.setrlimit(resource.RLIMIT_AS, (soft, hard))


def _validate_plain_data(value: Any, label: str) -> None:
    if value is None or isinstance(value, (bool, int, float, str)):
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_plain_data(item, f'{label}[{index}]')
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise UnsafeCodeError(f'{label} contains a non-string key')
            _validate_plain_data(item, f'{label}.{key}')
        return
    raise UnsafeCodeError(
        f'{label} contains unsupported value type: {type(value).__name__}'
    )
