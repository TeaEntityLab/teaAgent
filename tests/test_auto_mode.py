"""Tests for auto mode: fully autonomous execution with safety budget."""

from __future__ import annotations

import time

import pytest

from teaagent.auto_mode import (
    AutoModeConfig,
    AutoModeGuard,
    AutoModeLimitError,
)


def test_auto_mode_config_defaults() -> None:
    config = AutoModeConfig()
    assert not config.enabled
    assert config.max_iterations == 50
    assert config.max_tool_calls == 100
    assert config.max_cost_cents == 500.0
    assert config.max_wall_clock_seconds == 600.0
    assert not config.auto_commit
    assert config.allowed_tools is None
    assert 'workspace_run_shell' in config.denied_tools


def test_auto_mode_guard_iteration_limit() -> None:
    config = AutoModeConfig(enabled=True, max_iterations=3)
    guard = AutoModeGuard(config=config)
    guard.record_iteration()
    guard.record_iteration()
    with pytest.raises(AutoModeLimitError) as ctx:
        guard.record_iteration()
    assert 'iteration limit' in str(ctx.value)


def test_auto_mode_guard_tool_call_limit() -> None:
    config = AutoModeConfig(enabled=True, max_tool_calls=2)
    guard = AutoModeGuard(config=config)
    guard.record_tool_call()
    with pytest.raises(AutoModeLimitError):
        guard.record_tool_call()


def test_auto_mode_guard_cost_limit() -> None:
    config = AutoModeConfig(enabled=True, max_cost_cents=100.0)
    guard = AutoModeGuard(config=config)
    guard.record_cost(60.0)
    with pytest.raises(AutoModeLimitError):
        guard.record_cost(50.0)


def test_auto_mode_guard_wall_clock_limit() -> None:
    config = AutoModeConfig(
        enabled=True, max_wall_clock_seconds=0.1, max_iterations=1000
    )
    guard = AutoModeGuard(config=config)
    time.sleep(0.15)
    with pytest.raises(AutoModeLimitError):
        guard.record_iteration()


def test_auto_mode_guard_tool_allowed_with_whitelist() -> None:
    config = AutoModeConfig(
        enabled=True,
        allowed_tools=frozenset({'workspace_read_file', 'workspace_write_file'}),
    )
    guard = AutoModeGuard(config=config)
    assert guard.is_tool_allowed('workspace_read_file')
    assert not guard.is_tool_allowed('workspace_run_shell')


def test_auto_mode_guard_tool_allowed_with_denylist() -> None:
    config = AutoModeConfig(
        enabled=True,
        denied_tools=frozenset({'dangerous_tool'}),
    )
    guard = AutoModeGuard(config=config)
    assert guard.is_tool_allowed('safe_tool')
    assert not guard.is_tool_allowed('dangerous_tool')


def test_auto_mode_guard_summary() -> None:
    config = AutoModeConfig(enabled=True)
    guard = AutoModeGuard(config=config)
    guard.record_iteration()
    guard.record_tool_call()
    guard.record_cost(10.0)
    summary = guard.summary()
    assert summary['auto_mode']
    assert summary['iterations'] == 1
    assert summary['tool_calls'] == 1
    assert summary['cost_cents'] == 10.0
