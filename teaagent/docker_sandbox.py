from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from teaagent.resource_monitor import ResourceMonitor


class AuditLogger(Protocol):
    def record(self, event_type: str, run_id: str, **payload: Any) -> None: ...


@dataclass(frozen=True)
class SandboxResult:
    status: str
    container_id: str | None = None
    fallback: str | None = None
    message: str = ''
    stdout: str = ''
    stderr: str = ''
    exit_code: int | None = None


class DockerSandbox:
    def __init__(
        self,
        image: str = 'python:3.11-slim',
        cpu_cores: float = 1.0,
        memory_limit_mb: float = 512.0,
        workspace_mount_path: str | Path = '.',
        *,
        workspace_root: str | Path | None = None,
        audit_logger: AuditLogger | None = None,
        run_id: str = '',
    ) -> None:
        self.image = image
        self.cpu_cores = cpu_cores
        self.memory_limit_mb = memory_limit_mb
        self.workspace_mount = Path(workspace_mount_path)
        self.workspace_root = (
            Path(workspace_root).resolve() if workspace_root is not None else Path.cwd().resolve()
        )
        self.audit_logger = audit_logger
        self.run_id = run_id
        self.container_id: str | None = None
        self._monitor_interval_seconds: float = 2.0

    def _resource_monitor(self) -> ResourceMonitor:
        return ResourceMonitor(
            container_id=self.container_id,
            cpu_limit_cores=self.cpu_cores,
            memory_limit_mb=self.memory_limit_mb,
            check_interval_seconds=self._monitor_interval_seconds,
        )

    def check_resource_limits(self) -> SandboxResult | None:
        """Poll container usage once and abort on critical violations."""
        if not self.container_id:
            return None
        monitor = self._resource_monitor()
        usage = monitor.get_current_usage()
        if usage is None:
            return None
        violations = monitor.check_violations(usage)
        if not any(v.severity == 'critical' for v in violations):
            return None
        self._audit(
            'resource_violation_detected',
            container_id=self.container_id,
            count=len(violations),
        )
        self.abort('resource violation')
        return SandboxResult(
            status='aborted',
            container_id=self.container_id,
            message='resource violation',
        )

    def poll_resource_limits(
        self,
        *,
        duration_seconds: float = 2.0,
        interval_seconds: float | None = None,
    ) -> SandboxResult | None:
        """Poll resource usage until duration elapses or a violation aborts."""
        interval = (
            self._monitor_interval_seconds
            if interval_seconds is None
            else interval_seconds
        )
        deadline = time.time() + duration_seconds
        while time.time() < deadline:
            aborted = self.check_resource_limits()
            if aborted is not None:
                return aborted
            time.sleep(interval)
        return None

    def preflight(self) -> dict[str, str]:
        result = subprocess.run(
            ['docker', 'info'],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return {'status': 'ok', 'runtime': 'docker'}
        return {
            'status': 'fallback',
            'runtime': 'wasm',
            'reason': (result.stderr or result.stdout or 'docker unavailable').strip(),
        }

    def start(self) -> SandboxResult:
        preflight = self.preflight()
        if preflight['status'] != 'ok':
            self._audit(
                'docker_preflight_failed',
                runtime=preflight.get('runtime', 'docker'),
                reason=preflight.get('reason', 'unknown'),
            )
            self._audit(
                'sandbox_fallback_to_wasm',
                reason=preflight.get('reason', 'unknown'),
            )
            return SandboxResult(
                status='fallback',
                fallback='wasm',
                message=preflight.get('reason', 'docker unavailable'),
            )

        resolved_mount = self.workspace_mount.resolve()
        resolved_root = self.workspace_root.resolve()
        try:
            resolved_mount.relative_to(resolved_root)
        except ValueError:
            raise ValueError(
                f'Workspace mount path {resolved_mount} is outside workspace root {resolved_root}'
            ) from None
        mount_spec = f'{resolved_mount}:/workspace'
        result = subprocess.run(
            [
                'docker',
                'run',
                '-d',
                '--rm',
                '--network',
                'none',
                '--cpus',
                str(self.cpu_cores),
                '--memory',
                f'{int(self.memory_limit_mb)}m',
                '--memory-swap',
                f'{int(self.memory_limit_mb)}m',
                '-v',
                mount_spec,
                '-w',
                '/workspace',
                self.image,
                'sleep',
                '3600',
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return SandboxResult(
                status='error',
                message=(result.stderr or result.stdout).strip(),
                exit_code=result.returncode,
            )
        self.container_id = result.stdout.strip()
        self._audit('docker_sandbox_started', container_id=self.container_id)
        self._resource_monitor().start()
        return SandboxResult(status='started', container_id=self.container_id)

    def execute_code(self, code: str, *, timeout_seconds: int = 30) -> SandboxResult:
        if not self.container_id:
            started = self.start()
            if started.status != 'started':
                return started
        assert self.container_id is not None
        result = subprocess.run(
            [
                'docker',
                'exec',
                self.container_id,
                'python3',
                '-c',
                code,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        violation = self.check_resource_limits()
        if violation is not None:
            violation = SandboxResult(
                status=violation.status,
                container_id=violation.container_id,
                message=violation.message,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
            )
            return violation

        return SandboxResult(
            status='completed' if result.returncode == 0 else 'error',
            container_id=self.container_id,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
        )

    def abort(self, reason: str) -> None:
        if not self.container_id:
            return
        subprocess.run(
            ['docker', 'kill', self.container_id],
            check=False,
            capture_output=True,
            text=True,
        )
        self._audit(
            'docker_sandbox_aborted', container_id=self.container_id, reason=reason
        )

    def cleanup(self) -> None:
        if not self.container_id:
            return
        self._resource_monitor().stop()
        subprocess.run(
            ['docker', 'rm', '-f', self.container_id],
            check=False,
            capture_output=True,
            text=True,
        )
        self._audit('docker_sandbox_cleaned', container_id=self.container_id)
        self.container_id = None

    def _audit(self, event_type: str, **payload: Any) -> None:
        if self.audit_logger is None:
            return
        self.audit_logger.record(event_type, self.run_id, **payload)
