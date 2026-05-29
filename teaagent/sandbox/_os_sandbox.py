"""OS-level command sandboxing helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Optional


class OSSandbox:
    """OS-level sandboxing for shell command execution.

    Provides process isolation and filesystem restrictions for safe
    execution of agent shell commands.
    """

    def __init__(self, root: str | Path, allowed_paths: Optional[list[str]] = None):
        """Initialize OS-level sandbox.

        Args:
            root: Git repository root path (primary allowed path).
            allowed_paths: Additional allowed paths (e.g., temp directories).
        """
        self._root = Path(root).resolve()
        self._allowed_paths: list[str] = [str(self._root)]
        if allowed_paths:
            self._allowed_paths.extend([str(Path(p).resolve()) for p in allowed_paths])

    def is_path_allowed(self, path: str) -> bool:
        """Check if a path is within allowed sandbox boundaries.

        Args:
            path: Path to check.

        Returns:
            True if path is allowed, False otherwise.
        """
        try:
            resolved_path = Path(path).resolve()
            for allowed in self._allowed_paths:
                allowed_path = Path(allowed).resolve()
                try:
                    resolved_path.relative_to(allowed_path)
                    return True
                except ValueError:
                    continue
            return False
        except (ValueError, OSError):
            return False

    def sanitize_environment(
        self, env: Optional[dict[str, str]] = None
    ) -> dict[str, str]:
        """Sanitize environment variables for safe execution.

        Args:
            env: Original environment (uses os.environ if None).

        Returns:
            Sanitized environment dict.
        """
        import os

        if env is None:
            env = dict(os.environ)

        # Remove sensitive environment variables
        sensitive_keys = [
            'SSH_PRIVATE_KEY',
            'SSH_KEY',
            'AWS_SECRET_ACCESS_KEY',
            'GOOGLE_APPLICATION_CREDENTIALS',
            'GITHUB_TOKEN',
            'API_KEY',
            'SECRET_KEY',
            'PASSWORD',
            'TOKEN',
        ]

        for key in list(env.keys()):
            if any(sensitive in key.upper() for sensitive in sensitive_keys):
                del env[key]

        # Restrict PATH to safe directories
        safe_path = '/usr/bin:/bin:/usr/local/bin'
        env['PATH'] = safe_path

        # Set sandbox indicator
        env['TEAAGENT_SANDBOX'] = '1'

        return env

    def execute_sandboxed(
        self,
        command: list[str],
        cwd: Optional[str] = None,
        timeout: int = 300,
    ) -> dict[str, Any]:
        """Execute command in sandboxed environment.

        Args:
            command: Command and arguments to execute.
            cwd: Working directory (must be within allowed paths).
            timeout: Maximum execution time in seconds.

        Returns:
            Dict with 'success', 'stdout', 'stderr', 'exit_code'.
        """

        if cwd and not self.is_path_allowed(cwd):
            return {
                'success': False,
                'stdout': '',
                'stderr': f'Working directory {cwd} is outside sandbox boundaries',
                'exit_code': -1,
            }

        working_dir = cwd if cwd else str(self._root)

        env = self.sanitize_environment()

        try:
            result = subprocess.run(
                command,
                cwd=working_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'exit_code': result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'stdout': '',
                'stderr': f'Command timed out after {timeout} seconds',
                'exit_code': -1,
            }
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'exit_code': -1,
            }

    def set_resource_limits(self) -> bool:
        """Set resource limits for the current process (Unix only).

        Args:
            None

        Returns:
            True if limits were set successfully, False otherwise.
        """
        try:
            import resource

            # Limit CPU time to 5 minutes
            resource.setrlimit(resource.RLIMIT_CPU, (300, 300))

            # Limit memory to 1GB
            resource.setrlimit(
                resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024)
            )

            # Limit number of processes
            resource.setrlimit(resource.RLIMIT_NPROC, (100, 100))

            return True
        except (ImportError, ValueError, OSError):
            # Not available on Windows or permission denied
            return False
