"""Tranche B/C governance extension tests."""

from __future__ import annotations

import os
import time

import pytest
from cryptography.fernet import Fernet

from teaagent.hooks import HookError, HookRegistry, mcp_tool_filter_hook
from teaagent.mcp_trust import (
    load_mcp_trust_policy,
    save_mcp_trust_policy,
    update_global_tools,
)
from teaagent.memory.failure_card import FailureCard, FailureCardStorage
from teaagent.selftest import run_security_selftest


def test_security_selftest_passes_on_clean_workspace(tmp_path) -> None:
    report = run_security_selftest(tmp_path)
    assert report['ok'] is True
    assert report['tool_lint']['ok'] is True
    assert report['permission_smoke']['ok'] is True


def test_failure_card_ttl_and_invalidation(tmp_path) -> None:
    card = FailureCard.create(
        run_id='r1',
        error_type='TestError',
        file_path='a.py',
        error_message='boom',
        task_description='task',
        context_files=[],
        ttl_seconds=1,
    )
    assert card.is_active()
    expired = FailureCard.from_dict({**card.to_dict(), 'expires_at': time.time() - 1})
    assert not expired.is_active()
    assert expired.effective_behavior() == 'ignore'

    storage = FailureCardStorage(tmp_path)
    storage.append(card)
    assert storage.invalidate(card.id, reason='fixed upstream') is True
    loaded = storage.get_by_id(card.id)
    assert loaded is not None
    assert loaded.invalidated is True
    assert storage.prune_expired() == 1


def test_failure_card_auto_reviewer_never_blocks() -> None:
    card = FailureCard.create(
        run_id='r1',
        error_type='TestError',
        file_path='a.py',
        error_message='boom',
        task_description='task',
        context_files=[],
        confidence='high',
        warning_behavior='block',
        reviewer_type='auto',
    )
    assert card.effective_behavior() == 'warning'


def test_mcp_trust_policy_persist_and_hook_blocks(tmp_path) -> None:
    # Set up test encryption key for MCP trust policy (must be valid Fernet key)
    test_key = Fernet.generate_key()
    os.environ['TEAAGENT_MCP_TRUST_KEY'] = test_key.decode('utf-8')

    try:
        policy = load_mcp_trust_policy(tmp_path)
        update_global_tools(policy, deny=['blocked_tool'])
        save_mcp_trust_policy(tmp_path, policy)
        reloaded = load_mcp_trust_policy(tmp_path)
        assert 'blocked_tool' in reloaded.denied_tools

        registry = HookRegistry()
        registry.register_pre_hook(
            mcp_tool_filter_hook(
                allowed_tools=frozenset(),
                blocked_tools=frozenset({'blocked_tool'}),
            )
        )
        with pytest.raises(HookError):
            registry.run_pre_hooks('blocked_tool', {})
    finally:
        # Clean up test environment variable
        if 'TEAAGENT_MCP_TRUST_KEY' in os.environ:
            del os.environ['TEAAGENT_MCP_TRUST_KEY']
