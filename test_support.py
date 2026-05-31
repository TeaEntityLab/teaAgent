from __future__ import annotations

import socket

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


def skip_if_socket_bind_is_blocked() -> None:
    """Skip tests that require a loopback TCP listener when the environment forbids it."""

    if not can_bind_loopback():
        pytest.skip('sandbox forbids socket.bind() on loopback')
