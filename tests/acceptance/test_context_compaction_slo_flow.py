"""AC-NEW: Context compaction latency SLO.

Verifies that the context compaction system correctly identifies usage
levels (green/yellow/red traffic-light zones matching Claude Code) and
that compaction operations complete within acceptable latency bounds.

Acceptance criteria:
- should_compact returns True at or above 75% token usage, False below.
- get_usage_level returns green (0-75%), yellow (75-92%), red (92%+).
- compact produces a CompactionResult with observations pruned and a summary.
- The compaction operation completes within 100ms for typical context sizes.
- Empty/no-observation contexts compact cleanly.
"""

from __future__ import annotations

import time

from teaagent.context import CompactionManager, CompactionResult, ContextCompactor


def test_should_compact_thresholds():
    compactor = ContextCompactor()
    assert compactor.should_compact(150000, 200000) is True
    assert compactor.should_compact(160000, 200000) is True
    assert compactor.should_compact(149999, 200000) is False
    assert compactor.should_compact(0, 200000) is False


def test_should_compact_zero_max_tokens():
    compactor = ContextCompactor()
    assert compactor.should_compact(1, 0) is False
    assert compactor.should_compact(0, 0) is False


def test_get_usage_level_green():
    mgr = CompactionManager(max_context_tokens=200000)
    assert mgr.get_usage_level(0) == 'green'
    assert mgr.get_usage_level(100000) == 'green'
    assert mgr.get_usage_level(149999) == 'green'


def test_get_usage_level_yellow():
    mgr = CompactionManager(max_context_tokens=200000)
    assert mgr.get_usage_level(150000) == 'yellow'
    assert mgr.get_usage_level(180000) == 'yellow'
    assert mgr.get_usage_level(183999) == 'yellow'


def test_get_usage_level_red():
    mgr = CompactionManager(max_context_tokens=200000)
    assert mgr.get_usage_level(184000) == 'red'
    assert mgr.get_usage_level(200000) == 'red'


def test_get_usage_level_unknown():
    mgr = CompactionManager(max_context_tokens=0)
    assert mgr.get_usage_level(50000) == 'unknown'


def test_compaction_hints():
    mgr = CompactionManager(max_context_tokens=200000)
    assert mgr.get_compaction_hint(100000) is None
    yellow_hint = mgr.get_compaction_hint(150000)
    assert yellow_hint is not None
    assert 'saving' in yellow_hint.lower()
    red_hint = mgr.get_compaction_hint(190000)
    assert red_hint is not None
    assert 'compacting' in red_hint.lower()


def test_compact_preserves_recent_observations():
    compactor = ContextCompactor(recent_observations=3)
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
    assert isinstance(result, CompactionResult)
    assert len(result.context['observations']) == 3
    assert result.context['observations'][0]['result']['path'].endswith('c.py')
    assert result.context['compaction_count'] == 1
    assert 'read_file' in result.summary
    assert result.tokens_saved > 0


def test_compact_empty_observations():
    compactor = ContextCompactor()
    context = {'task': 'test', 'observations': []}
    result = compactor.compact(context)
    assert isinstance(result, CompactionResult)
    assert len(result.context['observations']) == 0
    assert result.summary == ''


def test_compact_fewer_than_recent():
    compactor = ContextCompactor(recent_observations=5)
    context = {
        'task': 'test',
        'observations': [
            {'tool_name': 'read_file', 'result': {'path': 'x.py'}},
        ],
    }
    result = compactor.compact(context)
    assert len(result.context['observations']) == 1
    assert result.context['observations'][0]['tool_name'] == 'read_file'


def test_check_and_compact_triggers_when_needed():
    mgr = CompactionManager(max_context_tokens=200000)
    context = {
        'task': 'test',
        'observations': [
            {'tool_name': 'read_file', 'result': {'path': 'old.py'}},
            {'tool_name': 'search_text', 'result': {'matches': []}},
        ],
    }
    result = mgr.check_and_compact(context, 180000)
    assert isinstance(result, CompactionResult)
    assert result.context['compaction_count'] == 1


def test_check_and_compact_skips_when_below_threshold():
    mgr = CompactionManager(max_context_tokens=200000)
    context = {'task': 'test', 'observations': []}
    result = mgr.check_and_compact(context, 100000)
    assert result is None


def test_compaction_latency_within_slo():
    compactor = ContextCompactor()
    observations = [
        {'tool_name': 'read_file', 'result': {'path': f'file_{i}.py'}}
        for i in range(50)
    ]
    context = {'task': 'large task', 'observations': observations}
    start = time.perf_counter()
    result = compactor.compact(context)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert isinstance(result, CompactionResult)
    assert elapsed_ms < 100, f'Compaction took {elapsed_ms:.1f}ms, exceeds 100ms SLO'


def test_estimate_tokens():
    compactor = ContextCompactor()
    assert compactor.estimate_tokens('hello world') == 2
    assert compactor.estimate_tokens('a' * 100) == 25
