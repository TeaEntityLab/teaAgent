from __future__ import annotations

import pytest

from teaagent.eval import (
    EvalCase,
    JudgeScore,
    make_llm_judge_fn,
    run_eval,
    run_eval_with_judge,
)


def test_all_pass_when_expected_found() -> None:
    cases = [EvalCase(name='c1', task='t', expected_contains=('hello',))]
    report = run_eval(cases, run_case=lambda c: 'hello world')
    assert report.passed
    assert report.pass_rate == 1.0


def test_fails_when_expected_missing() -> None:
    cases = [EvalCase(name='c1', task='t', expected_contains=('hello',))]
    report = run_eval(cases, run_case=lambda c: 'goodbye world')
    assert not report.passed
    assert report.results[0].failures == ('hello',)


def test_case_without_expected_always_passes() -> None:
    cases = [EvalCase(name='c1', task='t')]
    report = run_eval(cases, run_case=lambda c: 'anything')
    assert report.passed


def test_empty_cases_pass_rate_zero() -> None:
    report = run_eval([], run_case=lambda c: '')
    assert report.pass_rate == 0.0
    assert report.passed


def test_judge_score_field_none_in_basic_run_eval() -> None:
    cases = [EvalCase(name='c1', task='t', judge_prompt='quality')]
    report = run_eval(cases, run_case=lambda c: 'output')
    assert report.results[0].judge_score is None


def _fixed_judge(score: float) -> object:
    def judge(task: str, output: str) -> JudgeScore:
        return JudgeScore(score=score, reasoning='fixed')

    return judge


def test_passes_when_judge_score_above_threshold() -> None:
    cases = [EvalCase(name='c1', task='t', judge_prompt='quality')]
    report = run_eval_with_judge(
        cases,
        run_case=lambda c: 'good output',
        judge_fn=_fixed_judge(0.9),
        passing_threshold=0.7,
    )
    assert report.passed
    assert report.results[0].judge_score is not None
    assert report.results[0].judge_score.score == pytest.approx(0.9)


def test_fails_when_judge_score_below_threshold() -> None:
    cases = [EvalCase(name='c1', task='t', judge_prompt='quality')]
    report = run_eval_with_judge(
        cases,
        run_case=lambda c: 'poor output',
        judge_fn=_fixed_judge(0.3),
        passing_threshold=0.7,
    )
    assert not report.passed


def test_fails_when_expected_missing_even_if_judge_passes() -> None:
    cases = [
        EvalCase(
            name='c1',
            task='t',
            expected_contains=('required phrase',),
            judge_prompt='quality',
        )
    ]
    report = run_eval_with_judge(
        cases,
        run_case=lambda c: 'this is bad output',
        judge_fn=_fixed_judge(1.0),
    )
    assert not report.passed
    assert 'required phrase' in report.results[0].failures


def test_no_judge_prompt_skips_judge_call() -> None:
    called = []

    def judge(task: str, output: str) -> JudgeScore:
        called.append(True)
        return JudgeScore(score=1.0, reasoning='')

    cases = [EvalCase(name='c1', task='t')]
    run_eval_with_judge(cases, run_case=lambda c: 'out', judge_fn=judge)
    assert called == []


def test_threshold_from_judge_fn_attribute() -> None:
    def judge(task: str, output: str) -> JudgeScore:
        return JudgeScore(score=0.5, reasoning='mid')

    judge._passing_threshold = 0.4  # type: ignore[attr-defined]
    cases = [EvalCase(name='c1', task='t', judge_prompt='q')]
    report = run_eval_with_judge(cases, run_case=lambda c: 'out', judge_fn=judge)
    assert report.passed


def _fake_adapter(content: str) -> object:
    class FakeResponse:
        def __init__(self, c: str) -> None:
            self.content = c
            self.estimated_cost_cents = 0.0

    class FakeAdapter:
        def complete(self, req: object) -> FakeResponse:
            return FakeResponse(content)

    return FakeAdapter()


def test_parses_json_score() -> None:
    adapter = _fake_adapter('{"score": 0.85, "reasoning": "good job"}')
    judge_fn = make_llm_judge_fn(adapter)
    score = judge_fn('task', 'output')
    assert score.score == pytest.approx(0.85)
    assert score.reasoning == 'good job'


def test_parses_score_from_non_json_response() -> None:
    adapter = _fake_adapter('The score is "score": 0.6 and "reasoning": "ok"')
    judge_fn = make_llm_judge_fn(adapter)
    score = judge_fn('task', 'output')
    assert score.score == pytest.approx(0.6)


def test_clamps_score_to_0_1() -> None:
    adapter = _fake_adapter('{"score": 1.5, "reasoning": "overflow"}')
    judge_fn = make_llm_judge_fn(adapter)
    score = judge_fn('task', 'output')
    assert score.score == pytest.approx(1.0)


def test_error_on_adapter_failure() -> None:
    class FailAdapter:
        def complete(self, req: object) -> object:
            raise RuntimeError('model down')

    judge_fn = make_llm_judge_fn(FailAdapter())
    score = judge_fn('task', 'output')
    assert score.score == pytest.approx(0.0)
    assert 'judge error' in score.reasoning


def test_passing_threshold_stored_on_fn() -> None:
    adapter = _fake_adapter('{"score": 0.9, "reasoning": "x"}')
    judge_fn = make_llm_judge_fn(adapter, passing_threshold=0.8)
    assert judge_fn._passing_threshold == pytest.approx(0.8)
