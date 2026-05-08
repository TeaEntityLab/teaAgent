from __future__ import annotations

import ast
import multiprocessing
import queue
import traceback
from dataclasses import dataclass
from typing import Any

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


class UnsafeCodeError(ValueError):
    pass


def execute_code_mode(
    code: str,
    *,
    inputs: dict[str, Any] | None = None,
    sandbox: CodeModeSandbox | None = None,
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

    context = multiprocessing.get_context('spawn')
    result_queue: multiprocessing.Queue[dict[str, Any]] = context.Queue(maxsize=1)
    process = context.Process(
        target=_execute_code_mode_child,
        args=(code, safe_inputs, active_sandbox, result_queue),
    )
    process.start()
    process.join(active_sandbox.timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join()
        raise UnsafeCodeError('Code Mode timed out')

    try:
        message = result_queue.get_nowait()
    except queue.Empty as exc:
        raise UnsafeCodeError('Code Mode sandbox exited without a result') from exc

    if message['status'] == 'error':
        raise UnsafeCodeError(message['error'])
    variables = message['variables']
    _validate_plain_data(variables, 'variables')
    return CodeModeResult(variables=variables)


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
    result_queue: multiprocessing.Queue[dict[str, Any]],
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
        result_queue.put(
            {
                'status': 'error',
                'error': f'{type(exc).__name__}: {exc}',
                'traceback': traceback.format_exc(),
            }
        )
    else:
        result_queue.put({'status': 'ok', 'variables': variables})


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
        try:
            resource.setrlimit(resource.RLIMIT_AS, (soft, hard))
        except ValueError:
            # macOS reports RLIMIT_AS but rejects lowering it; wall/CPU limits still
            # keep Code Mode isolated from the parent process.
            pass


def _validate_plain_data(value: Any, label: str) -> None:
    if value is None or isinstance(value, (bool, int, float, str)):
        return
    if isinstance(value, list) or isinstance(value, tuple):
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
