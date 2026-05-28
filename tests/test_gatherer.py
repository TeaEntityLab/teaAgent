"""Tests for ContextGatherer with turn limits."""

import logging

import pytest

from teaagent.plan_mode import ContextGatherer, InsufficientContextError


def test_gatherer_sufficient_on_first_turn():
    """Test that gatherer stops when context is sufficient on first turn."""
    gatherer = ContextGatherer(soft_limit=3, hard_limit=5)

    def mock_llm_check(task, memories):
        return True, []

    def mock_gather(needs):
        pass

    gatherer.gather_context('test task', [], mock_llm_check, mock_gather)

    assert gatherer.current_turn == 1


def test_gatherer_soft_limit_warning(caplog):
    """Test that gatherer warns after soft limit."""
    gatherer = ContextGatherer(soft_limit=3, hard_limit=5)

    call_count = 0

    def mock_llm_check(task, memories):
        nonlocal call_count
        call_count += 1
        if call_count < 5:
            return False, ['need_more_info']
        return True, []

    def mock_gather(needs):
        pass

    with caplog.at_level(logging.WARNING):
        gatherer.gather_context('test task', [], mock_llm_check, mock_gather)

    assert any(
        'Context sufficiency check round' in record.message for record in caplog.records
    )


def test_gatherer_hard_limit_error():
    """Test that gatherer raises InsufficientContextError after hard limit."""
    gatherer = ContextGatherer(soft_limit=3, hard_limit=5)

    def mock_llm_check(task, memories):
        return False, ['need_more_info']

    def mock_gather(needs):
        pass

    with pytest.raises(InsufficientContextError) as exc_info:
        gatherer.gather_context('test task', [], mock_llm_check, mock_gather)

    assert 'exceeded hard limit' in str(exc_info.value)
    assert gatherer.current_turn == 5


def test_gatherer_gathers_on_insufficient():
    """Test that gatherer calls gather_fn when context is insufficient."""
    gatherer = ContextGatherer(soft_limit=3, hard_limit=5)

    gather_calls = []
    memories = []

    def mock_llm_check(task, current_memories):
        if len(current_memories) < 2:
            return False, ['need_file']
        return True, []

    def mock_gather(needs):
        gather_calls.append(needs)
        memories.append('gathered_info')

    gatherer.gather_context('test task', memories, mock_llm_check, mock_gather)

    assert len(gather_calls) == 2
    assert gatherer.current_turn == 3


def test_gatherer_respects_sufficient_after_gathering():
    """Test that gatherer stops after gathering sufficient context."""
    gatherer = ContextGatherer(soft_limit=3, hard_limit=5)

    call_count = 0
    memories = []

    def mock_llm_check(task, current_memories):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return False, ['need_info']
        return True, []

    def mock_gather(needs):
        memories.append('gathered_info')

    gatherer.gather_context('test task', memories, mock_llm_check, mock_gather)

    assert gatherer.current_turn == 2
