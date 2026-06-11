"""AC-NEW: Context compaction latency SLO.

Verifies that the context compaction system correctly identifies usage
levels (green/yellow/red traffic-light zones matching Claude Code) and
that compaction operations complete within acceptable latency bounds.

Acceptance criteria:
- should_compact returns True at or above 75% token usage, False below.
- get_usage_level returns green (0-75%), yellow (75-92%), red (92%+).
- compact produces a CompactionResult with observations pruned and a summary.
- The compaction operation completes within acceptable latency for typical context sizes.
- Empty/no-observation contexts compact cleanly.
"""

from __future__ import annotations

import os
import time

from teaagent.context import CompactionManager, CompactionResult, ContextCompactor

# Configurable SLO threshold for context compaction latency
# Can be overridden via environment variable for slow CI systems
# Default is conservative (500ms) to avoid flakiness on slow CI systems
_COMPACTION_SLO_MS = float(os.environ.get('TEAAGENT_TEST_COMPACTION_SLO_MS', '500'))

# Token count constants for usage level thresholds
# Based on 200,000 max context tokens:
# - Green: 0-75% (0-150,000 tokens)
# - Yellow: 75-92% (150,000-184,000 tokens)
# - Red: 92%+ (184,000+ tokens)
_MAX_CONTEXT_TOKENS = 200000
_GREEN_THRESHOLD_TOKENS = 150000  # 75% of max
_YELLOW_THRESHOLD_TOKENS = 184000  # 92% of max
_YELLOW_START_TOKENS = 150000  # Start of yellow zone (75%)
_YELLOW_END_TOKENS = 183999  # End of yellow zone (just before 92%)
_RED_START_TOKENS = 184000  # Start of red zone (92%)

# Compaction test constants
_RECENT_OBSERVATIONS_COUNT = 3  # Number of recent observations to preserve
_MAX_RECENT_OBSERVATIONS = 5  # Maximum recent observations for fewer-than test
_COMPACT_TEST_OBSERVATIONS_COUNT = 50  # Number of observations for latency test
_COMPACT_TEST_TOKEN_LIMIT = 200  # Token limit for chat history compaction test
_COMPACT_TEST_MAX_TOKENS = 1000  # Max tokens for chat history compaction test

# Token estimation constants
_CHARS_PER_TOKEN_TEXT = 3.5  # Average characters per token for plain text
_CHARS_PER_TOKEN_CODE = 4.0  # Average characters per token for code-heavy content
_TEST_STRING_LENGTH_100 = 100  # Length of test string for token estimation
_TEST_STRING_HELLO_WORLD = 'hello world'  # Test string for token estimation

# Chat history test constants
_CHAT_HISTORY_REPEAT_COUNT = (
    100  # Number of times to repeat "Hello " / "Hi there " in test
)
_CHAT_HISTORY_TEST_MESSAGES_COUNT = 5  # Number of messages in chat history test
_COMPRESSION_RATIO_TEST_OBSERVATIONS_COUNT = (
    10  # Number of observations for compression ratio test
)


def test_should_compact_thresholds():
    compactor = ContextCompactor()
    # Verify compaction triggers at or above yellow threshold (75%)
    assert (
        compactor.should_compact(_YELLOW_START_TOKENS, _MAX_CONTEXT_TOKENS) is True
    ), (
        f'Expected compaction to trigger at yellow threshold ({_YELLOW_START_TOKENS} tokens)'
    )
    assert compactor.should_compact(160000, _MAX_CONTEXT_TOKENS) is True, (
        'Expected compaction to trigger at 160000 tokens (above yellow threshold)'
    )
    # Verify compaction does not trigger below yellow threshold
    assert (
        compactor.should_compact(_YELLOW_START_TOKENS - 1, _MAX_CONTEXT_TOKENS) is False
    ), (
        f'Expected compaction not to trigger below yellow threshold ({_YELLOW_START_TOKENS - 1} tokens)'
    )
    assert compactor.should_compact(0, _MAX_CONTEXT_TOKENS) is False, (
        'Expected compaction not to trigger at zero tokens'
    )


def test_should_compact_zero_max_tokens():
    compactor = ContextCompactor()
    # Edge case: when max_tokens is 0, compaction should never trigger
    assert compactor.should_compact(1, 0) is False, (
        'Expected compaction not to trigger when max_tokens is 0'
    )
    assert compactor.should_compact(0, 0) is False, (
        'Expected compaction not to trigger when both current and max tokens are 0'
    )


def test_get_usage_level_green():
    mgr = CompactionManager(max_context_tokens=_MAX_CONTEXT_TOKENS)
    # Verify green zone (0-75% usage)
    assert mgr.get_usage_level(0) == 'green', (
        f'Expected green level at 0 tokens, got {mgr.get_usage_level(0)!r}'
    )
    assert mgr.get_usage_level(100000) == 'green', (
        f'Expected green level at 100000 tokens, got {mgr.get_usage_level(100000)!r}'
    )
    assert mgr.get_usage_level(_YELLOW_START_TOKENS - 1) == 'green', (
        f'Expected green level just below yellow threshold ({_YELLOW_START_TOKENS - 1} tokens), '
        f'got {mgr.get_usage_level(_YELLOW_START_TOKENS - 1)!r}'
    )


def test_get_usage_level_yellow():
    mgr = CompactionManager(max_context_tokens=_MAX_CONTEXT_TOKENS)
    # Verify yellow zone (75-92% usage)
    assert mgr.get_usage_level(_YELLOW_START_TOKENS) == 'yellow', (
        f'Expected yellow level at yellow threshold start ({_YELLOW_START_TOKENS} tokens), '
        f'got {mgr.get_usage_level(_YELLOW_START_TOKENS)!r}'
    )
    assert mgr.get_usage_level(180000) == 'yellow', (
        f'Expected yellow level at 180000 tokens, got {mgr.get_usage_level(180000)!r}'
    )
    assert mgr.get_usage_level(_YELLOW_END_TOKENS) == 'yellow', (
        f'Expected yellow level at yellow threshold end ({_YELLOW_END_TOKENS} tokens), '
        f'got {mgr.get_usage_level(_YELLOW_END_TOKENS)!r}'
    )


def test_get_usage_level_red():
    mgr = CompactionManager(max_context_tokens=_MAX_CONTEXT_TOKENS)
    # Verify red zone (92%+ usage)
    assert mgr.get_usage_level(_RED_START_TOKENS) == 'red', (
        f'Expected red level at red threshold start ({_RED_START_TOKENS} tokens), '
        f'got {mgr.get_usage_level(_RED_START_TOKENS)!r}'
    )
    assert mgr.get_usage_level(_MAX_CONTEXT_TOKENS) == 'red', (
        f'Expected red level at max context tokens ({_MAX_CONTEXT_TOKENS}), '
        f'got {mgr.get_usage_level(_MAX_CONTEXT_TOKENS)!r}'
    )


def test_get_usage_level_unknown():
    mgr = CompactionManager(max_context_tokens=0)
    # Edge case: when max_tokens is 0, usage level should be unknown
    assert mgr.get_usage_level(50000) == 'unknown', (
        f'Expected unknown level when max_tokens is 0, got {mgr.get_usage_level(50000)!r}'
    )


def test_compaction_hints():
    mgr = CompactionManager(max_context_tokens=_MAX_CONTEXT_TOKENS)
    # No hint should be provided in green zone
    assert mgr.get_compaction_hint(100000) is None, (
        'Expected no compaction hint in green zone (100000 tokens)'
    )
    # Yellow zone should provide a hint about saving
    yellow_hint = mgr.get_compaction_hint(_YELLOW_START_TOKENS)
    assert yellow_hint is not None, (
        f'Expected compaction hint in yellow zone ({_YELLOW_START_TOKENS} tokens)'
    )
    assert 'saving' in yellow_hint.lower(), (
        f'Expected yellow hint to mention "saving", got: {yellow_hint}'
    )
    # Red zone should provide a hint about compaction
    red_hint = mgr.get_compaction_hint(190000)
    assert red_hint is not None, 'Expected compaction hint in red zone (190000 tokens)'
    assert 'compacting' in red_hint.lower(), (
        f'Expected red hint to mention "compacting", got: {red_hint}'
    )


def test_compact_preserves_recent_observations():
    compactor = ContextCompactor(recent_observations=_RECENT_OBSERVATIONS_COUNT)
    context = {
        'task': 'test task',
        'observations': [
            {'tool_name': 'read_file', 'result': {'path': 'a.py'}},
            {'tool_name': 'read_file', 'result': {'path': 'b.py'}},
            {'tool_name': 'read_file', 'result': {'path': 'c.py'}},
            {'tool_name': 'read_file', 'result': {'path': 'd.py'}},
            {'tool_name': 'search_text', 'result': {'matches': []}},
        ],
    }
    result = compactor.compact(context)
    # Verify compaction result structure
    assert isinstance(result, CompactionResult), (
        f'Expected CompactionResult, got {type(result).__name__}'
    )
    # Verify only recent observations are preserved
    assert len(result.context['observations']) == _RECENT_OBSERVATIONS_COUNT, (
        f'Expected {_RECENT_OBSERVATIONS_COUNT} recent observations, '
        f'got {len(result.context["observations"])}'
    )
    # Verify the oldest preserved observation is correct (should be c.py, the 3rd from end)
    assert result.context['observations'][0]['result']['path'].endswith('c.py'), (
        f'Expected oldest preserved observation to be c.py, '
        f'got {result.context["observations"][0]["result"]["path"]}'
    )
    # Verify compaction count is incremented
    assert result.context['compaction_count'] == 1, (
        f'Expected compaction_count to be 1, got {result.context["compaction_count"]}'
    )
    # Semantic summary should mention files
    assert 'files' in result.summary.lower() or 'read' in result.summary.lower(), (
        f'Expected summary to mention files or read operations, got: {result.summary}'
    )
    # Verify tokens were actually saved
    assert result.tokens_saved > 0, (
        f'Expected tokens_saved to be positive, got {result.tokens_saved}'
    )


def test_compact_empty_observations():
    compactor = ContextCompactor()
    context = {'task': 'test', 'observations': []}
    result = compactor.compact(context)
    # Edge case: empty observations should compact cleanly
    assert isinstance(result, CompactionResult), (
        f'Expected CompactionResult for empty observations, got {type(result).__name__}'
    )
    assert len(result.context['observations']) == 0, (
        f'Expected 0 observations after compaction, got {len(result.context["observations"])}'
    )
    assert result.summary == '', (
        f'Expected empty summary for empty observations, got: {result.summary!r}'
    )


def test_compact_fewer_than_recent():
    compactor = ContextCompactor(recent_observations=_MAX_RECENT_OBSERVATIONS)
    context = {
        'task': 'test',
        'observations': [
            {'tool_name': 'read_file', 'result': {'path': 'x.py'}},
        ],
    }
    result = compactor.compact(context)
    # Edge case: when observations < recent limit, all should be preserved
    assert len(result.context['observations']) == 1, (
        f'Expected 1 observation preserved (fewer than recent limit), '
        f'got {len(result.context["observations"])}'
    )
    assert result.context['observations'][0]['tool_name'] == 'read_file', (
        f'Expected tool_name to be "read_file", got {result.context["observations"][0]["tool_name"]!r}'
    )


def test_check_and_compact_triggers_when_needed():
    mgr = CompactionManager(max_context_tokens=_MAX_CONTEXT_TOKENS)
    context = {
        'task': 'test',
        'observations': [
            {'tool_name': 'read_file', 'result': {'path': 'old.py'}},
            {'tool_name': 'search_text', 'result': {'matches': []}},
        ],
    }
    result = mgr.check_and_compact(context, 180000)
    # Verify compaction triggers when usage is in yellow/red zone (180000 tokens)
    assert isinstance(result, CompactionResult), (
        f'Expected CompactionResult when usage is high (180000 tokens), got {type(result).__name__}'
    )
    assert result.context['compaction_count'] == 1, (
        f'Expected compaction_count to be 1 after compaction, got {result.context["compaction_count"]}'
    )


def test_check_and_compact_skips_when_below_threshold():
    mgr = CompactionManager(max_context_tokens=_MAX_CONTEXT_TOKENS)
    context = {'task': 'test', 'observations': []}
    result = mgr.check_and_compact(context, 100000)
    # Verify compaction is skipped when usage is in green zone (100000 tokens)
    assert result is None, (
        'Expected no compaction when usage is below threshold (100000 tokens in green zone)'
    )


def test_compaction_latency_within_slo():
    compactor = ContextCompactor()
    observations = [
        {'tool_name': 'read_file', 'result': {'path': f'file_{i}.py'}}
        for i in range(_COMPACT_TEST_OBSERVATIONS_COUNT)
    ]
    context = {'task': 'large task', 'observations': observations}
    start = time.perf_counter()
    result = compactor.compact(context)
    elapsed_ms = (time.perf_counter() - start) * 1000
    # Verify compaction completes within SLO
    assert isinstance(result, CompactionResult), (
        f'Expected CompactionResult, got {type(result).__name__}'
    )
    assert elapsed_ms < _COMPACTION_SLO_MS, (
        f'Compaction took {elapsed_ms:.1f}ms, exceeds {_COMPACTION_SLO_MS}ms SLO'
    )


def test_estimate_tokens():
    compactor = ContextCompactor()
    # Text estimation (3.5 chars per token)
    assert compactor.estimate_tokens(_TEST_STRING_HELLO_WORLD) == 3, (
        f'Expected 3 tokens for "{_TEST_STRING_HELLO_WORLD}" (11 chars / 3.5), '
        f'got {compactor.estimate_tokens(_TEST_STRING_HELLO_WORLD)}'
    )
    # Plain text uses 3.5 chars per token
    assert compactor.estimate_tokens('a' * _TEST_STRING_LENGTH_100) == 28, (
        f'Expected 28 tokens for 100 chars (100 / 3.5), '
        f'got {compactor.estimate_tokens("a" * _TEST_STRING_LENGTH_100)}'
    )
    # Code-heavy content uses 4 chars per token
    code = 'def foo(): { return bar; }'
    assert compactor.estimate_tokens(code) > 0, (
        f'Expected positive token count for code, got {compactor.estimate_tokens(code)}'
    )


def test_semantic_summarization():
    compactor = ContextCompactor(enable_semantic_compression=True)
    observations = [
        {'tool_name': 'read_file', 'result': {'path': 'a.py'}},
        {'tool_name': 'read_file', 'result': {'path': 'b.py'}},
        {'tool_name': 'read_file', 'result': {'path': 'c.py'}},
        {'tool_name': 'search_text', 'result': {'matches': ['line1', 'line2']}},
    ]
    summary = compactor._semantic_summarize(observations)
    # Verify semantic summary captures key operations
    assert 'Read 3 files' in summary, (
        f'Expected summary to mention "Read 3 files", got: {summary}'
    )
    assert 'a.py' in summary, f'Expected summary to mention file "a.py", got: {summary}'
    assert 'Searched' in summary, (
        f'Expected summary to mention search operation, got: {summary}'
    )


def test_compact_chat_history():
    compactor = ContextCompactor()
    messages = [
        {'role': 'system', 'content': 'You are a helpful assistant.'},
        {'role': 'user', 'content': 'Hello ' * _CHAT_HISTORY_REPEAT_COUNT},
        {'role': 'assistant', 'content': 'Hi there ' * _CHAT_HISTORY_REPEAT_COUNT},
        {'role': 'user', 'content': 'How are you?'},
        {'role': 'assistant', 'content': 'I am good.'},
    ]
    compacted = compactor.compact_chat_history(
        messages, max_tokens=_COMPACT_TEST_TOKEN_LIMIT
    )
    # System message should be preserved
    assert any(m.get('role') == 'system' for m in compacted), (
        'Expected system message to be preserved in compacted chat history'
    )
    # Should have fewer messages due to token limit
    assert len(compacted) < len(messages), (
        f'Expected fewer messages after compaction ({len(compacted)} < {len(messages)}), '
        f'but got {len(compacted)} messages'
    )


def test_compact_chat_history_preserves_recent():
    compactor = ContextCompactor()
    messages = [
        {'role': 'system', 'content': 'System prompt'},
        {'role': 'user', 'content': 'Old message'},
        {'role': 'assistant', 'content': 'Old response'},
        {'role': 'user', 'content': 'Recent message'},
        {'role': 'assistant', 'content': 'Recent response'},
    ]
    compacted = compactor.compact_chat_history(
        messages, max_tokens=_COMPACT_TEST_MAX_TOKENS
    )
    # Should preserve recent messages
    assert any('Recent' in m.get('content', '') for m in compacted), (
        'Expected recent messages to be preserved in compacted chat history'
    )


def test_compression_ratio():
    compactor = ContextCompactor(enable_semantic_compression=True)
    context = {
        'task': 'test',
        'observations': [
            {'tool_name': 'read_file', 'result': {'path': f'file_{i}.py'}}
            for i in range(_COMPRESSION_RATIO_TEST_OBSERVATIONS_COUNT)
        ],
    }
    result = compactor.compact(context)
    # Verify compression ratio is within valid bounds [0.0, 1.0]
    assert result.compression_ratio >= 0.0, (
        f'Expected compression_ratio >= 0.0, got {result.compression_ratio}'
    )
    assert result.compression_ratio <= 1.0, (
        f'Expected compression_ratio <= 1.0, got {result.compression_ratio}'
    )
