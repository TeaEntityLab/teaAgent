from __future__ import annotations

import socket
import subprocess
import threading
from pathlib import Path
from typing import Any

import pytest


def _git(
    args: list[str], repo_root: Path | None
) -> subprocess.CompletedProcess[str] | None:
    """Run a git command in ``repo_root`` (default: this checkout); None if git cannot run."""
    cwd = repo_root if repo_root is not None else Path(__file__).resolve().parent
    try:
        return subprocess.run(
            ['git', *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None


def repo_is_shallow(repo_root: Path | None = None) -> bool:
    """Return True when the git checkout is shallow; git errors count as not shallow."""
    proc = _git(['rev-parse', '--is-shallow-repository'], repo_root)
    return proc is not None and proc.returncode == 0 and proc.stdout.strip() == 'true'


def commit_exists(sha: str, repo_root: Path | None = None) -> bool:
    """Return True when ``sha`` resolves to a commit present in the checkout."""
    proc = _git(['cat-file', '-e', f'{sha}^{{commit}}'], repo_root)
    return proc is not None and proc.returncode == 0


def can_bind_loopback() -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('127.0.0.1', 0))
    except PermissionError:
        return False
    finally:
        sock.close()
    return True


def can_start_threads(count: int = 1) -> bool:
    threads: list[threading.Thread] = []
    release = threading.Event()
    try:
        for _ in range(count):
            thread = threading.Thread(target=release.wait)
            thread.start()
            threads.append(thread)
    except RuntimeError as exc:
        if "can't start new thread" in str(exc):
            return False
        raise
    finally:
        release.set()
        for thread in threads:
            thread.join(timeout=1.0)
    return True


def skip_if_socket_bind_is_blocked() -> None:
    """Skip tests that require a loopback TCP listener when the environment forbids it."""

    if not can_bind_loopback():
        pytest.skip('sandbox forbids socket.bind() on loopback')


def skip_if_thread_start_is_blocked(count: int = 1) -> None:
    """Skip tests that require spawning worker threads when the environment forbids it."""

    if not can_start_threads(count):
        pytest.skip('environment has thread resource limits')


def mcp_test_governance(root: str | Path, permission_mode: str = 'prompt') -> Any:
    """Build a governed MCP server context (approval policy + run log) under ``root``."""
    from teaagent.mcp_server import MCPGovernance
    from teaagent.policy import PermissionMode

    return MCPGovernance.for_workspace(
        root, permission_mode=PermissionMode(permission_mode), transport='test'
    )
