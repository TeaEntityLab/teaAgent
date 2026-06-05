from __future__ import annotations

import dataclasses
import tempfile
from pathlib import Path

from teaagent.context_pressure import (
    ContextPressureScore,
    compute_context_pressure,
)


def test_context_pressure_score_has_all_fields() -> None:
    """Verify ContextPressureScore has all specified fields."""
    fields = {f.name for f in dataclasses.fields(ContextPressureScore)}
    expected = {
        'token_usage_ratio',
        'usage_level',
        'estimated_total_tokens',
        'max_context_tokens',
        'memory_count',
        'files_pinned',
        'recent_runs',
        'large_artifacts',
        'contributors',
        'recommendations',
    }
    assert fields == expected


def test_context_pressure_score_usage_level_green() -> None:
    """compute_context_pressure on a fresh empty workspace returns green usage_level."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        workspace = root / 'workspace'
        workspace.mkdir()
        (workspace / '.teaagent').mkdir()

        score = compute_context_pressure(workspace)
        assert isinstance(score, ContextPressureScore)
        assert score.usage_level in ('green', 'unknown')
        assert score.files_pinned == 0
        assert score.memory_count == 0
        assert score.recent_runs == 0
        assert score.large_artifacts == []


def test_context_pressure_score_empty_workspace() -> None:
    """compute_context_pressure on a non-existent directory should not crash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        score = compute_context_pressure(Path(tmpdir) / 'nonexistent')
        assert isinstance(score, ContextPressureScore)


def test_context_pressure_to_dict() -> None:
    """to_dict returns all expected keys."""
    score = ContextPressureScore(
        token_usage_ratio=0.1,
        usage_level='green',
        estimated_total_tokens=5000,
        max_context_tokens=128000,
        memory_count=3,
        files_pinned=2,
        recent_runs=1,
        large_artifacts=['big_file.log'],
        contributors={'task': 100, 'memories': 50},
        recommendations=['all good'],
    )
    d = score.to_dict()
    assert d['token_usage_ratio'] == 0.1
    assert d['usage_level'] == 'green'
    assert d['estimated_total_tokens'] == 5000
    assert d['max_context_tokens'] == 128000
    assert d['memory_count'] == 3
    assert d['files_pinned'] == 2
    assert d['recent_runs'] == 1
    assert d['large_artifacts'] == ['big_file.log']
    assert d['contributors'] == {'task': 100, 'memories': 50}
    assert d['recommendations'] == ['all good']
