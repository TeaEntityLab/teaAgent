from __future__ import annotations

import pytest

from teaagent.swarm import (
    PromptFitnessMetrics,
    SubagentResult,
    compute_prompt_fitness_score,
    fitness_metrics_from_result,
    rank_prompt_tournament,
    save_prompt_to_gene_pool,
)


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


def test_rank_prompt_tournament_selects_successful_branch() -> None:
    branch_a = fitness_metrics_from_result(
        SubagentResult(
            task_id='a',
            success=False,
            execution_time_ms=1000,
            test_results={'tokens': 50, 'errors': 0},
        ),
        peer_results=[
            SubagentResult(
                task_id='a',
                success=False,
                execution_time_ms=1000,
                test_results={'tokens': 50, 'errors': 0},
            ),
            SubagentResult(
                task_id='c',
                success=True,
                execution_time_ms=2000,
                test_results={'tokens': 80, 'errors': 0},
            ),
        ],
    )
    branch_c = fitness_metrics_from_result(
        SubagentResult(
            task_id='c',
            success=True,
            execution_time_ms=2000,
            test_results={'tokens': 80, 'errors': 0},
        ),
        peer_results=[
            SubagentResult(
                task_id='a',
                success=False,
                execution_time_ms=1000,
                test_results={'tokens': 50, 'errors': 0},
            ),
            SubagentResult(
                task_id='c',
                success=True,
                execution_time_ms=2000,
                test_results={'tokens': 80, 'errors': 0},
            ),
        ],
    )
    ranked = rank_prompt_tournament(
        [
            ('a', 'prompt-a', branch_a),
            ('c', 'prompt-c', branch_c),
        ]
    )
    assert ranked[0][0] == 'c'
    assert ranked[0][1] > ranked[1][1]


def test_save_prompt_to_gene_pool(tmp_path) -> None:
    path = save_prompt_to_gene_pool(
        tmp_path, prompt='be concise', score=0.9, task_id='t1'
    )
    assert path.is_file()
    assert 'be concise' in path.read_text(encoding='utf-8')


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
