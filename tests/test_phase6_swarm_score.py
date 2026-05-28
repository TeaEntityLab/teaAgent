from __future__ import annotations

import pytest

from teaagent.swarm import PromptFitnessMetrics, compute_prompt_fitness_score


def test_success_zero_forces_score_zero() -> None:
    score = compute_prompt_fitness_score(
        PromptFitnessMetrics(
            success=0,
            tokens=100,
            min_tokens=50,
            time_seconds=10,
            min_time_seconds=5,
            errors=0,
        )
    )
    assert score == 0.0


def test_score_decreases_with_higher_tokens() -> None:
    base = compute_prompt_fitness_score(
        PromptFitnessMetrics(
            success=1,
            tokens=100,
            min_tokens=100,
            time_seconds=10,
            min_time_seconds=10,
            errors=0,
        )
    )
    worse = compute_prompt_fitness_score(
        PromptFitnessMetrics(
            success=1,
            tokens=200,
            min_tokens=100,
            time_seconds=10,
            min_time_seconds=10,
            errors=0,
        )
    )
    assert worse < base


def test_invalid_metrics_raise() -> None:
    with pytest.raises(ValueError):
        compute_prompt_fitness_score(
            PromptFitnessMetrics(
                success=1,
                tokens=0,
                min_tokens=1,
                time_seconds=1,
                min_time_seconds=1,
                errors=0,
            )
        )
