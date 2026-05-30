"""Tranche B/C governance extension tests."""

from __future__ import annotations

import os
import time

import pytest
from cryptography.fernet import Fernet

from teaagent.hooks import HookError, HookRegistry, mcp_tool_filter_hook
from teaagent.mcp_trust import (
    _get_trust_policy_fernet,
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


def test_mcp_trust_policy_missing_env_var_raises_error() -> None:
    """Test that missing TEAAGENT_MCP_TRUST_KEY environment variable raises informative error."""
    # Ensure environment variable is not set
    if 'TEAAGENT_MCP_TRUST_KEY' in os.environ:
        del os.environ['TEAAGENT_MCP_TRUST_KEY']
    
    with pytest.raises(ValueError) as exc_info:
        _get_trust_policy_fernet()
    
    assert 'TEAAGENT_MCP_TRUST_KEY environment variable is required' in str(exc_info.value)
    assert 'Fernet.generate_key()' in str(exc_info.value)


def test_mcp_trust_policy_invalid_key_format_raises_error() -> None:
    """Test that invalid Fernet key format raises informative error."""
    # Set an invalid key (not a valid Fernet key)
    os.environ['TEAAGENT_MCP_TRUST_KEY'] = 'invalid_key_format'
    
    try:
        with pytest.raises(ValueError) as exc_info:
            _get_trust_policy_fernet()
        
        assert 'Invalid TEAAGENT_MCP_TRUST_KEY format' in str(exc_info.value)
        assert 'Fernet.generate_key()' in str(exc_info.value)
    finally:
        # Clean up test environment variable
        if 'TEAAGENT_MCP_TRUST_KEY' in os.environ:
            del os.environ['TEAAGENT_MCP_TRUST_KEY']


def test_mcp_trust_policy_save_with_invalid_key_raises_error(tmp_path) -> None:
    """Test that save_mcp_trust_policy raises error with invalid key."""
    # Set an invalid key
    os.environ['TEAAGENT_MCP_TRUST_KEY'] = 'invalid_key_format'
    
    try:
        policy = load_mcp_trust_policy(tmp_path)
        with pytest.raises(ValueError) as exc_info:
            save_mcp_trust_policy(tmp_path, policy)
        
        assert 'Invalid TEAAGENT_MCP_TRUST_KEY format' in str(exc_info.value)
    finally:
        # Clean up test environment variable
        if 'TEAAGENT_MCP_TRUST_KEY' in os.environ:
            del os.environ['TEAAGENT_MCP_TRUST_KEY']
