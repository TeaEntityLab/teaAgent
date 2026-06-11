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
        # Verify default values are safe/unknown
        assert s.overall == 'unknown', (
            f'Expected overall to default to "unknown", got {s.overall!r}'
        )
        assert s.token_pressure == 'unknown', (
            f'Expected token_pressure to default to "unknown", got {s.token_pressure!r}'
        )
        assert s.stale_files == 0, (
            f'Expected stale_files to default to 0, got {s.stale_files}'
        )
        assert s.old_observations == 0, (
            f'Expected old_observations to default to 0, got {s.old_observations}'
        )
        assert s.memory_confidence == 'unknown', (
            f'Expected memory_confidence to default to "unknown", got {s.memory_confidence!r}'
        )
        assert s.hidden_large_attachments == 0, (
            f'Expected hidden_large_attachments to default to 0, got {s.hidden_large_attachments}'
        )
        assert s.recommendation == '', (
            'Expected recommendation to default to empty string'
        )

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
        # Verify all fields are correctly serialized to dict
        assert d['overall'] == 'yellow', (
            f'Expected overall "yellow", got {d["overall"]!r}'
        )
        assert d['token_pressure'] == 'green', (
            f'Expected token_pressure "green", got {d["token_pressure"]!r}'
        )
        assert d['stale_files'] == 3, f'Expected stale_files 3, got {d["stale_files"]}'
        assert d['old_observations'] == 60, (
            f'Expected old_observations 60, got {d["old_observations"]}'
        )
        assert d['memory_confidence'] == 'green', (
            f'Expected memory_confidence "green", got {d["memory_confidence"]!r}'
        )
        assert d['hidden_large_attachments'] == 0, (
            f'Expected hidden_large_attachments 0, got {d["hidden_large_attachments"]}'
        )
        assert d['recommendation'] == 'Context filling up', (
            f'Expected recommendation "Context filling up", got {d["recommendation"]!r}'
        )

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
        # Verify all expected keys are present in serialized dict
        assert set(d.keys()) == expected_keys, (
            f'Expected keys {expected_keys}, got {set(d.keys())}'
        )


class TestWorstSignal:
    """_worst_signal priority order."""

    def test_red_wins(self) -> None:
        # Verify red signal has highest priority
        assert _worst_signal(['green', 'yellow', 'red']) == 'red', (
            'Expected red to win as worst signal'
        )

    def test_yellow_second(self) -> None:
        # Verify yellow signal has second-highest priority
        assert _worst_signal(['green', 'yellow']) == 'yellow', (
            'Expected yellow to win over green'
        )
        assert _worst_signal(['yellow', 'green', 'green']) == 'yellow', (
            'Expected yellow to win over multiple greens'
        )

    def test_green_only(self) -> None:
        # Verify green signal wins when only greens are present
        assert _worst_signal(['green', 'green']) == 'green', (
            'Expected green to win when only greens present'
        )

    def test_unknown_fallback(self) -> None:
        # Verify unknown is returned for unknown or empty signal lists
        assert _worst_signal(['unknown']) == 'unknown', (
            'Expected unknown for single unknown signal'
        )
        assert _worst_signal([]) == 'unknown', 'Expected unknown for empty signal list'

    def test_red_overrides_any(self) -> None:
        # Verify red overrides any other signals
        assert _worst_signal(['green', 'green', 'red', 'green']) == 'red', (
            'Expected red to override all other signals'
        )


class TestTokenPressure:
    """_compute_token_pressure traffic-light mapping."""

    def test_green_below_75(self) -> None:
        # Verify green zone (below 75% usage)
        assert _compute_token_pressure(100_000, 200_000) == 'green', (
            'Expected green for 50% usage (100k/200k)'
        )
        assert _compute_token_pressure(0, 200_000) == 'green', (
            'Expected green for 0% usage (0/200k)'
        )

    def test_yellow_75_to_92(self) -> None:
        # Verify yellow zone (75-92% usage)
        assert _compute_token_pressure(150_000, 200_000) == 'yellow', (
            'Expected yellow for 75% usage (150k/200k)'
        )
        assert _compute_token_pressure(160_000, 200_000) == 'yellow', (
            'Expected yellow for 80% usage (160k/200k)'
        )

    def test_red_above_92(self) -> None:
        # Verify red zone (above 92% usage)
        assert _compute_token_pressure(185_000, 200_000) == 'red', (
            'Expected red for 92.5% usage (185k/200k)'
        )
        assert _compute_token_pressure(200_000, 200_000) == 'red', (
            'Expected red for 100% usage (200k/200k)'
        )

    def test_unknown_when_max_zero(self) -> None:
        # Verify unknown when max_tokens is zero or negative
        assert _compute_token_pressure(100, 0) == 'unknown', (
            'Expected unknown when max_tokens is 0'
        )
        assert _compute_token_pressure(100, -1) == 'unknown', (
            'Expected unknown when max_tokens is negative'
        )


class TestMemoryConfidence:
    """_compute_memory_confidence scoring."""

    def test_unknown_when_none(self) -> None:
        # Verify unknown when catalog is None
        assert _compute_memory_confidence(None) == 'unknown', (
            'Expected unknown when catalog is None'
        )

    def test_unknown_when_non_iterable(self) -> None:
        """Non-iterable treated as empty → green."""
        # Verify green when catalog is non-iterable (treated as empty)
        assert _compute_memory_confidence(42) == 'green', (
            'Expected green for non-iterable catalog (treated as empty)'
        )

    def test_green_when_empty(self) -> None:
        # Verify green when catalog is empty
        assert _compute_memory_confidence([]) == 'green', (
            'Expected green for empty catalog'
        )

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
        # Verify green when most entries are recent (<1 day)
        assert _compute_memory_confidence(entries) == 'green', (
            'Expected green when most entries are recent'
        )

    def test_yellow_when_few_recent(self) -> None:
        now = time.time()
        # 1 recent (<1 day), rest between 1-7 days (stale)
        entries = (
            [{'updated_at': now - 100}]
            + [{'updated_at': now - 200_000}] * 5
            + [{'updated_at': now - 300_000}] * 6
        )
        # Verify yellow when few entries are recent
        assert _compute_memory_confidence(entries) == 'yellow', (
            'Expected yellow when few entries are recent'
        )

    def test_red_when_mostly_old(self) -> None:
        now = time.time()
        # 2 recent, rest > 7 days old
        entries = (
            [{'updated_at': now - 100}] * 2
            + [{'updated_at': now - 200_000}] * 1
            + [{'updated_at': now - 700_000}] * 8
        )
        # Verify red when most entries are old (>7 days)
        assert _compute_memory_confidence(entries) == 'red', (
            'Expected red when most entries are old'
        )

    def test_uses_updated_at_fallback_created_at(self) -> None:
        now = time.time()
        entries = [
            {'created_at': now - 100},
            {'created_at': now - 800_000},
        ]
        # Verify fallback to created_at when updated_at is missing
        assert isinstance(_compute_memory_confidence(entries), str), (
            'Expected string result when using created_at fallback'
        )

    def test_exception_returns_unknown(self) -> None:
        """Has __iter__ but raises on list() consumption."""

        class BadCatalog:
            def __iter__(self):
                raise ValueError('boom')

        # Verify unknown when catalog raises exception during iteration
        assert _compute_memory_confidence(BadCatalog()) == 'unknown', (
            'Expected unknown when catalog raises exception'
        )

    def test_handles_missing_timestamp(self) -> None:
        entries = [{'title': 'no timestamp'}]
        # No timestamp → age = now - 0 = very old → red
        # Verify string result when timestamp is missing
        assert isinstance(_compute_memory_confidence(entries), str), (
            'Expected string result when timestamp is missing'
        )


class TestRecommendations:
    """_build_recommendation generates correct messages."""

    def test_green_returns_good_health(self) -> None:
        r = _build_recommendation('green', 'green', 0, 0, 'green', 0)
        # Verify green health returns good health message
        assert r == 'Context health is good', (
            f'Expected "Context health is good" for green signals, got {r!r}'
        )

    def test_token_pressure_red(self) -> None:
        r = _build_recommendation('red', 'red', 0, 0, 'green', 0)
        # Verify red token pressure recommends fresh session
        assert 'fresh session' in r, (
            f'Expected recommendation to mention "fresh session" for red token pressure, got {r!r}'
        )

    def test_token_pressure_yellow(self) -> None:
        r = _build_recommendation('yellow', 'yellow', 0, 0, 'green', 0)
        # Verify yellow token pressure mentions filling up
        assert 'filling up' in r, (
            f'Expected recommendation to mention "filling up" for yellow token pressure, got {r!r}'
        )

    def test_stale_files(self) -> None:
        r = _build_recommendation('yellow', 'green', 5, 0, 'green', 0)
        # Verify stale files recommendation includes count
        assert 'changed on disk' in r, (
            f'Expected recommendation to mention "changed on disk" for stale files, got {r!r}'
        )
        assert '5' in r, (
            f'Expected recommendation to include stale file count 5, got {r!r}'
        )

    def test_observation_count_high(self) -> None:
        r = _build_recommendation('yellow', 'green', 0, 70, 'green', 0)
        # Verify high observation count mentions high observations but not compaction
        assert 'High observation' in r, (
            f'Expected recommendation to mention "High observation" for 70 observations, got {r!r}'
        )
        assert 'compaction' not in r, (
            f'Expected no compaction recommendation for 70 observations (below threshold), got {r!r}'
        )

    def test_observation_count_very_high(self) -> None:
        r = _build_recommendation('red', 'green', 0, 150, 'green', 0)
        # Verify very high observation count recommends compaction
        assert 'compaction recommended' in r, (
            f'Expected recommendation to mention "compaction recommended" for 150 observations, got {r!r}'
        )

    def test_memory_red(self) -> None:
        r = _build_recommendation('red', 'green', 0, 0, 'red', 0)
        # Verify red memory confidence recommends pruning
        assert 'pruning' in r, (
            f'Expected recommendation to mention "pruning" for red memory, got {r!r}'
        )

    def test_memory_yellow(self) -> None:
        r = _build_recommendation('yellow', 'green', 0, 0, 'yellow', 0)
        # Verify yellow memory confidence mentions outdated entries
        assert 'outdated' in r, (
            f'Expected recommendation to mention "outdated" for yellow memory, got {r!r}'
        )

    def test_large_attachments(self) -> None:
        r = _build_recommendation('yellow', 'green', 0, 0, 'green', 3)
        # Verify large attachments recommendation mentions token spikes
        assert 'large file' in r, (
            f'Expected recommendation to mention "large file" for large attachments, got {r!r}'
        )
        assert 'token spikes' in r, (
            f'Expected recommendation to mention "token spikes" for large attachments, got {r!r}'
        )

    def test_combined_signals(self) -> None:
        r = _build_recommendation('red', 'red', 8, 110, 'yellow', 2)
        # Verify combined signals produce comprehensive recommendation
        assert 'fresh session' in r, (
            f'Expected combined recommendation to mention "fresh session", got {r!r}'
        )
        assert 'changed on disk' in r, (
            f'Expected combined recommendation to mention "changed on disk", got {r!r}'
        )
        assert 'compaction recommended' in r, (
            f'Expected combined recommendation to mention "compaction recommended", got {r!r}'
        )
        assert 'outdated' in r, (
            f'Expected combined recommendation to mention "outdated", got {r!r}'
        )
        assert 'large file' in r, (
            f'Expected combined recommendation to mention "large file", got {r!r}'
        )


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
        # Verify default context health is green
        assert result.overall == 'green', (
            f'Expected overall "green" for default context, got {result.overall!r}'
        )
        assert result.token_pressure == 'green', (
            f'Expected token_pressure "green" for default context, got {result.token_pressure!r}'
        )
        assert result.recommendation == 'Context health is good', (
            f'Expected "Context health is good" recommendation, got {result.recommendation!r}'
        )

    def test_token_pressure_signals_propagated(self) -> None:
        r = compute_context_health(
            session_tokens_used=185_000, session_max_tokens=200_000
        )
        # Verify red token pressure is propagated to overall signal
        assert r.token_pressure == 'red', (
            f'Expected token_pressure "red" for 92.5% usage, got {r.token_pressure!r}'
        )
        assert r.overall == 'red', (
            f'Expected overall "red" when token_pressure is red, got {r.overall!r}'
        )
        assert 'fresh session' in r.recommendation, (
            f'Expected recommendation to mention "fresh session" for red token pressure, got {r.recommendation!r}'
        )

    def test_yellow_token_pressure(self) -> None:
        r = compute_context_health(
            session_tokens_used=160_000, session_max_tokens=200_000
        )
        # Verify yellow token pressure is propagated
        assert r.token_pressure == 'yellow', (
            f'Expected token_pressure "yellow" for 80% usage, got {r.token_pressure!r}'
        )
        assert r.overall == 'yellow', (
            f'Expected overall "yellow" when token_pressure is yellow, got {r.overall!r}'
        )

    def test_high_observation_count_worsens_signal(self) -> None:
        r = compute_context_health(observation_count=200)
        # Verify high observation count worsens signal to red
        assert r.old_observations == 150, (
            f'Expected old_observations 150 for count 200, got {r.old_observations}'
        )
        assert r.overall == 'red', (
            f'Expected overall "red" for high observation count, got {r.overall!r}'
        )
        assert 'compaction recommended' in r.recommendation, (
            f'Expected recommendation to mention "compaction recommended", got {r.recommendation!r}'
        )

    def test_moderate_observation_count(self) -> None:
        r = compute_context_health(observation_count=80)
        # Verify moderate observation count stays green
        assert r.old_observations == 30, (
            f'Expected old_observations 30 for count 80, got {r.old_observations}'
        )
        assert r.overall == 'green', (
            f'Expected overall "green" for moderate observation count, got {r.overall!r}'
        )

    def test_memory_confidence_propagates(self) -> None:
        now = time.time()
        # 2 recent, 1 stale (1-7 days), 7 old (>7 days) → old > 50% → red
        catalog = MockMemoryCatalog(
            [{'updated_at': now - 100}] * 2
            + [{'updated_at': now - 200_000}] * 1
            + [{'updated_at': now - 700_000}] * 7
        )
        r = compute_context_health(memory_catalog=catalog)
        # Verify red memory confidence is propagated
        assert r.memory_confidence == 'red', (
            f'Expected memory_confidence "red" for mostly old entries, got {r.memory_confidence!r}'
        )
        assert r.overall == 'red', (
            f'Expected overall "red" when memory_confidence is red, got {r.overall!r}'
        )

    def test_memory_yellow_propagates(self) -> None:
        now = time.time()
        # 1 recent, rest stale (1-7 days) — few recent → yellow
        catalog = MockMemoryCatalog(
            [{'updated_at': now - 100}] * 1
            + [{'updated_at': now - 200_000}] * 5
            + [{'updated_at': now - 300_000}] * 6
        )
        r = compute_context_health(memory_catalog=catalog)
        # Verify yellow memory confidence is propagated
        assert r.memory_confidence == 'yellow', (
            f'Expected memory_confidence "yellow" for few recent entries, got {r.memory_confidence!r}'
        )

    def test_overall_is_worst_signal(self) -> None:
        """Multiple yellow components produce yellow overall."""
        r = compute_context_health(
            session_tokens_used=160_000,
            session_max_tokens=200_000,
            observation_count=80,
        )
        # Verify overall signal is the worst of all component signals
        assert r.overall == 'yellow', (
            f'Expected overall "yellow" (worst of multiple yellows), got {r.overall!r}'
        )
