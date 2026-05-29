"""Backward-compatible shim for sandbox primitives.

Public sandbox APIs live in :mod:`teaagent.sandbox`. This module remains for
existing imports such as ``from teaagent.git_sandbox import GitBranchSandbox``.
"""

from __future__ import annotations

from teaagent import sandbox as _sandbox
from teaagent.sandbox import *  # noqa: F403

__all__ = _sandbox.__all__
