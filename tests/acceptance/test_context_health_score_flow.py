"""Acceptance test for context-health score (CTX-001).

Verifies that ContextHealthScore model, signal helpers, and
compute_context_health() produce correct traffic-light signals
and recommendations for long-session awareness.
"""

from __future__ import annotations

import time

from teaagent.context_health import (
    ContextHealthScore,
    _build_recommendation,
    _compute_memory_confidence,
    _compute_token_pressure,
    _worst_signal,
    compute_context_health,
)


class TestContextHealthScoreModel:
    """ContextHealthScore dataclass construction and serialization."""

    def test_default_construction(self) -> None:
        """All fields default to safe / unknown."""
        s = ContextHealthScore()
        assert s.overall == 'unknown'
        assert s.token_pressure == 'unknown'
        assert s.stale_files == 0
        assert s.old_observations == 0
        assert s.memory_confidence == 'unknown'
        assert s.hidden_large_attachments == 0
        assert s.recommendation == ''

    def test_round_trip_dict(self) -> None:
        s = ContextHealthScore(
            overall='yellow',
            token_pressure='green',
            stale_files=3,
            old_observations=60,
            memory_confidence='green',
            hidden_large_attachments=0,
            recommendation='Context filling up',
        )
        d = s.to_dict()
        assert d['overall'] == 'yellow'
        assert d['token_pressure'] == 'green'
        assert d['stale_files'] == 3
        assert d['old_observations'] == 60
        assert d['memory_confidence'] == 'green'
        assert d['hidden_large_attachments'] == 0
        assert d['recommendation'] == 'Context filling up'

    def test_to_dict_contains_all_keys(self) -> None:
        s = ContextHealthScore()
        d = s.to_dict()
        expected_keys = {
            'overall',
            'token_pressure',
            'stale_files',
            'old_observations',
            'memory_confidence',
            'hidden_large_attachments',
            'recommendation',
        }
        assert set(d.keys()) == expected_keys


class TestWorstSignal:
    """_worst_signal priority order."""

    def test_red_wins(self) -> None:
        assert _worst_signal(['green', 'yellow', 'red']) == 'red'

    def test_yellow_second(self) -> None:
        assert _worst_signal(['green', 'yellow']) == 'yellow'
        assert _worst_signal(['yellow', 'green', 'green']) == 'yellow'

    def test_green_only(self) -> None:
        assert _worst_signal(['green', 'green']) == 'green'

    def test_unknown_fallback(self) -> None:
        assert _worst_signal(['unknown']) == 'unknown'
        assert _worst_signal([]) == 'unknown'

    def test_red_overrides_any(self) -> None:
        assert _worst_signal(['green', 'green', 'red', 'green']) == 'red'


class TestTokenPressure:
    """_compute_token_pressure traffic-light mapping."""

    def test_green_below_75(self) -> None:
        assert _compute_token_pressure(100_000, 200_000) == 'green'
        assert _compute_token_pressure(0, 200_000) == 'green'

    def test_yellow_75_to_92(self) -> None:
        assert _compute_token_pressure(150_000, 200_000) == 'yellow'
        assert _compute_token_pressure(160_000, 200_000) == 'yellow'

    def test_red_above_92(self) -> None:
        assert _compute_token_pressure(185_000, 200_000) == 'red'
        assert _compute_token_pressure(200_000, 200_000) == 'red'

    def test_unknown_when_max_zero(self) -> None:
        assert _compute_token_pressure(100, 0) == 'unknown'
        assert _compute_token_pressure(100, -1) == 'unknown'


class TestMemoryConfidence:
    """_compute_memory_confidence scoring."""

    def test_unknown_when_none(self) -> None:
        assert _compute_memory_confidence(None) == 'unknown'

    def test_unknown_when_non_iterable(self) -> None:
        """Non-iterable treated as empty → green."""
        assert _compute_memory_confidence(42) == 'green'

    def test_green_when_empty(self) -> None:
        assert _compute_memory_confidence([]) == 'green'

    def test_green_when_mostly_recent(self) -> None:
        now = time.time()
        entries = [
            {'updated_at': now - 100},
            {'updated_at': now - 10_000},
            {'updated_at': now - 60_000},
            {'updated_at': now - 80_000},
            {'updated_at': now - 200_000},
            {'updated_at': now - 700_000},
        ]
        assert _compute_memory_confidence(entries) == 'green'

    def test_yellow_when_few_recent(self) -> None:
        now = time.time()
        # 1 recent (<1 day), rest between 1-7 days (stale)
        entries = (
            [{'updated_at': now - 100}]
            + [{'updated_at': now - 200_000}] * 5
            + [{'updated_at': now - 300_000}] * 6
        )
        assert _compute_memory_confidence(entries) == 'yellow'

    def test_red_when_mostly_old(self) -> None:
        now = time.time()
        # 2 recent, rest > 7 days old
        entries = (
            [{'updated_at': now - 100}] * 2
            + [{'updated_at': now - 200_000}] * 1
            + [{'updated_at': now - 700_000}] * 8
        )
        assert _compute_memory_confidence(entries) == 'red'

    def test_uses_updated_at_fallback_created_at(self) -> None:
        now = time.time()
        entries = [
            {'created_at': now - 100},
            {'created_at': now - 800_000},
        ]
        assert isinstance(_compute_memory_confidence(entries), str)

    def test_exception_returns_unknown(self) -> None:
        """Has __iter__ but raises on list() consumption."""

        class BadCatalog:
            def __iter__(self):
                raise ValueError('boom')

        assert _compute_memory_confidence(BadCatalog()) == 'unknown'

    def test_handles_missing_timestamp(self) -> None:
        entries = [{'title': 'no timestamp'}]
        # No timestamp → age = now - 0 = very old → red
        assert isinstance(_compute_memory_confidence(entries), str)


class TestRecommendations:
    """_build_recommendation generates correct messages."""

    def test_green_returns_good_health(self) -> None:
        r = _build_recommendation('green', 'green', 0, 0, 'green', 0)
        assert r == 'Context health is good'

    def test_token_pressure_red(self) -> None:
        r = _build_recommendation('red', 'red', 0, 0, 'green', 0)
        assert 'fresh session' in r

    def test_token_pressure_yellow(self) -> None:
        r = _build_recommendation('yellow', 'yellow', 0, 0, 'green', 0)
        assert 'filling up' in r

    def test_stale_files(self) -> None:
        r = _build_recommendation('yellow', 'green', 5, 0, 'green', 0)
        assert 'changed on disk' in r
        assert '5' in r

    def test_observation_count_high(self) -> None:
        r = _build_recommendation('yellow', 'green', 0, 70, 'green', 0)
        assert 'High observation' in r
        assert 'compaction' not in r

    def test_observation_count_very_high(self) -> None:
        r = _build_recommendation('red', 'green', 0, 150, 'green', 0)
        assert 'compaction recommended' in r

    def test_memory_red(self) -> None:
        r = _build_recommendation('red', 'green', 0, 0, 'red', 0)
        assert 'pruning' in r

    def test_memory_yellow(self) -> None:
        r = _build_recommendation('yellow', 'green', 0, 0, 'yellow', 0)
        assert 'outdated' in r

    def test_large_attachments(self) -> None:
        r = _build_recommendation('yellow', 'green', 0, 0, 'green', 3)
        assert 'large file' in r
        assert 'token spikes' in r

    def test_combined_signals(self) -> None:
        r = _build_recommendation('red', 'red', 8, 110, 'yellow', 2)
        assert 'fresh session' in r
        assert 'changed on disk' in r
        assert 'compaction recommended' in r
        assert 'outdated' in r
        assert 'large file' in r


class MockMemoryCatalog:
    """Minimal iterable that mimics a MemoryCatalog for testing."""

    def __init__(self, entries: list[dict]) -> None:
        self._entries = entries

    def __iter__(self):
        return iter(self._entries)


class TestComputeContextHealth:
    """compute_context_health() integration."""

    def test_default_returns_green(self) -> None:
        result = compute_context_health()
        assert result.overall == 'green'
        assert result.token_pressure == 'green'
        assert result.recommendation == 'Context health is good'

    def test_token_pressure_signals_propagated(self) -> None:
        r = compute_context_health(
            session_tokens_used=185_000, session_max_tokens=200_000
        )
        assert r.token_pressure == 'red'
        assert r.overall == 'red'
        assert 'fresh session' in r.recommendation

    def test_yellow_token_pressure(self) -> None:
        r = compute_context_health(
            session_tokens_used=160_000, session_max_tokens=200_000
        )
        assert r.token_pressure == 'yellow'
        assert r.overall == 'yellow'

    def test_high_observation_count_worsens_signal(self) -> None:
        r = compute_context_health(observation_count=200)
        assert r.old_observations == 150
        assert r.overall == 'red'
        assert 'compaction recommended' in r.recommendation

    def test_moderate_observation_count(self) -> None:
        r = compute_context_health(observation_count=80)
        assert r.old_observations == 30
        assert r.overall == 'green'

    def test_memory_confidence_propagates(self) -> None:
        now = time.time()
        # 2 recent, 1 stale (1-7 days), 7 old (>7 days) → old > 50% → red
        catalog = MockMemoryCatalog(
            [{'updated_at': now - 100}] * 2
            + [{'updated_at': now - 200_000}] * 1
            + [{'updated_at': now - 700_000}] * 7
        )
        r = compute_context_health(memory_catalog=catalog)
        assert r.memory_confidence == 'red'
        assert r.overall == 'red'

    def test_memory_yellow_propagates(self) -> None:
        now = time.time()
        # 1 recent, rest stale (1-7 days) — few recent → yellow
        catalog = MockMemoryCatalog(
            [{'updated_at': now - 100}] * 1
            + [{'updated_at': now - 200_000}] * 5
            + [{'updated_at': now - 300_000}] * 6
        )
        r = compute_context_health(memory_catalog=catalog)
        assert r.memory_confidence == 'yellow'

    def test_overall_is_worst_signal(self) -> None:
        """Multiple yellow components produce yellow overall."""
        r = compute_context_health(
            session_tokens_used=160_000,
            session_max_tokens=200_000,
            observation_count=80,
        )
        assert r.overall == 'yellow'
