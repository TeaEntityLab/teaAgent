from __future__ import annotations

import json
import subprocess
import threading
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Optional

from ._types import CodeModeResult, CodeModeSandbox
from ._validation import UnsafeCodeError, validate_plain_data

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


@dataclass(frozen=True)
class ContainerCodeModeBackend:
    image: str
    runtime: str = 'docker'
    python_executable: str = 'python3'
    network: str = 'none'
    cpus: float = 1.0
    user: str = '65534:65534'
    tmpfs_size_mb: int = 16
    require_image_digest: bool = False
    allowed_images: Optional[frozenset[str]] = None
    seccomp_profile: Optional[str] = None
    apparmor_profile: Optional[str] = None
    selinux_label: Optional[str] = None
    oci_runtime: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.image:
            raise UnsafeCodeError('Code Mode container image must be configured')
        if self.require_image_digest and '@sha256:' not in self.image:
            raise UnsafeCodeError('Code Mode container image must be pinned by digest')
        if self.allowed_images is not None and self.image not in self.allowed_images:
            raise UnsafeCodeError('Code Mode container image is not in the allowlist')
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
            )
        except OSError as exc:
            raise UnsafeCodeError(f'Code Mode container runtime failed: {exc}') from exc
        stdout, stderr = _communicate_with_output_limit(
            process,
            payload.encode('utf-8'),
            timeout_seconds=sandbox.timeout_seconds,
            max_output_bytes=sandbox.max_output_bytes,
        )
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
        validate_plain_data(variables, 'variables')
        return CodeModeResult(variables=variables)

    def _build_command(self, sandbox: CodeModeSandbox) -> list[str]:
        memory_mb = max(1, sandbox.memory_bytes // (1024 * 1024))
        cmd = [
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
        ]
        if self.oci_runtime:
            cmd.extend(['--runtime', self.oci_runtime])
        if self.seccomp_profile is not None:
            cmd.append(f'--security-opt=seccomp={self.seccomp_profile}')
        if self.apparmor_profile is not None:
            cmd.append(f'--security-opt=apparmor={self.apparmor_profile}')
        if self.selinux_label is not None:
            cmd.append(f'--security-opt=label={self.selinux_label}')
        cmd.extend(
            [
                '-i',
                self.image,
                self.python_executable,
                '-c',
                CONTAINER_CODE_MODE_SCRIPT,
            ]
        )
        return cmd


def _communicate_with_output_limit(
    process: subprocess.Popen[bytes],
    stdin_payload: bytes,
    *,
    timeout_seconds: float,
    max_output_bytes: int,
) -> tuple[str, str]:
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    total_output_bytes = 0
    output_lock = threading.Lock()
    output_exceeded = threading.Event()

    def read_stream(stream: Any, chunks: list[bytes]) -> None:
        nonlocal total_output_bytes
        while True:
            chunk = stream.read(8192)
            if not chunk:
                return
            with output_lock:
                total_output_bytes += len(chunk)
                if total_output_bytes > max_output_bytes:
                    output_exceeded.set()
                    with suppress(Exception):
                        process.kill()
                    return
            chunks.append(chunk)

    assert process.stdout is not None
    assert process.stderr is not None
    stdout_thread = threading.Thread(
        target=read_stream, args=(process.stdout, stdout_chunks), daemon=True
    )
    stderr_thread = threading.Thread(
        target=read_stream, args=(process.stderr, stderr_chunks), daemon=True
    )
    stdout_thread.start()
    stderr_thread.start()
    try:
        if process.stdin is not None:
            try:
                process.stdin.write(stdin_payload)
                process.stdin.close()
            except OSError:
                pass
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        raise UnsafeCodeError('Code Mode timed out') from exc
    finally:
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        with suppress(Exception):
            if process.stdout is not None:
                process.stdout.close()
        with suppress(Exception):
            if process.stderr is not None:
                process.stderr.close()
    if output_exceeded.is_set():
        with suppress(Exception):
            process.wait(timeout=1)
        raise UnsafeCodeError('Code Mode container exceeded output limit')
    stdout = b''.join(stdout_chunks).decode('utf-8', errors='replace')
    stderr = b''.join(stderr_chunks).decode('utf-8', errors='replace')
    return stdout, stderr
