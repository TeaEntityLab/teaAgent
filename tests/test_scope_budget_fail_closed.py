"""Tests for S-P1-1: ``check_scope_budget`` fail-closed behaviour."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from teaagent.tool_permissions import ToolPermissionManager


class _Result:
    def __init__(self, allowed: bool, reason: str = '') -> None:
        self.allowed = allowed
        self.reason = reason


class _CrashingEnforcer:
    """A scope-budget enforcer that always raises."""

    def check_tool(self, tool_name: str, tool_args: dict[str, Any]) -> list[_Result]:
        raise RuntimeError('enforcer internal error')


class _AllowingEnforcer:
    """A scope-budget enforcer that allows everything."""

    def check_tool(self, tool_name: str, tool_args: dict[str, Any]) -> list[_Result]:
        return [_Result(allowed=True)]


class _DenyingEnforcer:
    """A scope-budget enforcer that denies everything."""

    def check_tool(self, tool_name: str, tool_args: dict[str, Any]) -> list[_Result]:
        return [_Result(allowed=False, reason='out of scope')]


@pytest.fixture(autouse=True)
def _clear_fail_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure ``TEAAGENT_SCOPE_FAIL_OPEN`` is unset for every test."""
    monkeypatch.delenv('TEAAGENT_SCOPE_FAIL_OPEN', raising=False)


def test_enforcer_exception_denies_by_default() -> None:
    """An enforcer exception must produce a denial reason, not ``None``."""
    mgr = ToolPermissionManager(scope_budget_enforcer=_CrashingEnforcer())
    reason = mgr.check_scope_budget('write_file', {'path': 'x'})
    assert reason is not None
    assert 'scope budget check failed' in reason


def test_enforcer_exception_fail_open_with_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """When ``TEAAGENT_SCOPE_FAIL_OPEN=1`` the exception yields ``None`` (allowed)."""
    monkeypatch.setenv('TEAAGENT_SCOPE_FAIL_OPEN', '1')
    mgr = ToolPermissionManager(scope_budget_enforcer=_CrashingEnforcer())
    reason = mgr.check_scope_budget('write_file', {'path': 'x'})
    assert reason is None


def test_enforcer_exception_fail_open_logs_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The fail-open path must log a warning mentioning the env var."""
    monkeypatch.setenv('TEAAGENT_SCOPE_FAIL_OPEN', '1')
    mgr = ToolPermissionManager(scope_budget_enforcer=_CrashingEnforcer())
    with caplog.at_level(logging.WARNING, logger='teaagent.tool_permissions'):
        mgr.check_scope_budget('write_file', {'path': 'x'})
    assert any('fail-open' in rec.message for rec in caplog.records)


def test_enforcer_exception_fail_closed_logs_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The fail-closed path must log at ERROR level."""
    mgr = ToolPermissionManager(scope_budget_enforcer=_CrashingEnforcer())
    with caplog.at_level(logging.ERROR, logger='teaagent.tool_permissions'):
        mgr.check_scope_budget('write_file', {'path': 'x'})
    assert any('fail-closed' in rec.message for rec in caplog.records)


def test_no_enforcer_returns_none() -> None:
    """Without an enforcer, ``check_scope_budget`` returns ``None``."""
    mgr = ToolPermissionManager()
    assert mgr.check_scope_budget('write_file') is None


def test_allowing_enforcer_returns_none() -> None:
    """An enforcer that allows must return ``None``."""
    mgr = ToolPermissionManager(scope_budget_enforcer=_AllowingEnforcer())
    assert mgr.check_scope_budget('read_file') is None


def test_denying_enforcer_returns_reason() -> None:
    """An enforcer that denies must return the denial reason."""
    mgr = ToolPermissionManager(scope_budget_enforcer=_DenyingEnforcer())
    reason = mgr.check_scope_budget('write_file')
    assert reason == 'out of scope'
