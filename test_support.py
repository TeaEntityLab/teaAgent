from __future__ import annotations

import socket
import threading

import pytest


def can_bind_loopback() -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('127.0.0.1', 0))
    except PermissionError:
        return False
    finally:
        sock.close()
    return True


def can_start_thread() -> bool:
    thread = threading.Thread(target=lambda: None)
    try:
        thread.start()
    except RuntimeError as exc:
        if "can't start new thread" in str(exc):
            return False
        raise
    thread.join(timeout=1.0)
    return True


def skip_if_socket_bind_is_blocked() -> None:
    """Skip tests that require a loopback TCP listener when the environment forbids it."""

    if not can_bind_loopback():
        pytest.skip('sandbox forbids socket.bind() on loopback')


def skip_if_thread_start_is_blocked() -> None:
    """Skip tests that require spawning worker threads when the environment forbids it."""

    if not can_start_thread():
        pytest.skip('environment has thread resource limits')
