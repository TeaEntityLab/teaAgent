from __future__ import annotations

import unittest

from teaagent.eval import (
    EvalCase,
    JudgeScore,
    make_llm_judge_fn,
    run_eval,
    run_eval_with_judge,
)


class RunEvalTests(unittest.TestCase):
    def test_all_pass_when_expected_found(self) -> None:
        cases = [EvalCase(name='c1', task='t', expected_contains=('hello',))]
        report = run_eval(cases, run_case=lambda c: 'hello world')
        self.assertTrue(report.passed)
        self.assertEqual(report.pass_rate, 1.0)

    def test_fails_when_expected_missing(self) -> None:
        cases = [EvalCase(name='c1', task='t', expected_contains=('hello',))]
        report = run_eval(cases, run_case=lambda c: 'goodbye world')
        self.assertFalse(report.passed)
        self.assertEqual(report.results[0].failures, ('hello',))

    def test_case_without_expected_always_passes(self) -> None:
        cases = [EvalCase(name='c1', task='t')]
        report = run_eval(cases, run_case=lambda c: 'anything')
        self.assertTrue(report.passed)

    def test_empty_cases_pass_rate_zero(self) -> None:
        report = run_eval([], run_case=lambda c: '')
        self.assertEqual(report.pass_rate, 0.0)
        self.assertTrue(report.passed)

    def test_judge_score_field_none_in_basic_run_eval(self) -> None:
        cases = [EvalCase(name='c1', task='t', judge_prompt='quality')]
        report = run_eval(cases, run_case=lambda c: 'output')
        self.assertIsNone(report.results[0].judge_score)


class RunEvalWithJudgeTests(unittest.TestCase):
    def _fixed_judge(self, score: float) -> object:
        def judge(task: str, output: str) -> JudgeScore:
            return JudgeScore(score=score, reasoning='fixed')

        return judge

    def test_passes_when_judge_score_above_threshold(self) -> None:
        cases = [EvalCase(name='c1', task='t', judge_prompt='quality')]
        report = run_eval_with_judge(
            cases,
            run_case=lambda c: 'good output',
            judge_fn=self._fixed_judge(0.9),  # type: ignore[arg-type]
            passing_threshold=0.7,
        )
        self.assertTrue(report.passed)
        self.assertIsNotNone(report.results[0].judge_score)
        assert report.results[0].judge_score is not None
        self.assertAlmostEqual(report.results[0].judge_score.score, 0.9)

    def test_fails_when_judge_score_below_threshold(self) -> None:
        cases = [EvalCase(name='c1', task='t', judge_prompt='quality')]
        report = run_eval_with_judge(
            cases,
            run_case=lambda c: 'poor output',
            judge_fn=self._fixed_judge(0.3),  # type: ignore[arg-type]
            passing_threshold=0.7,
        )
        self.assertFalse(report.passed)

    def test_fails_when_expected_missing_even_if_judge_passes(self) -> None:
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
            judge_fn=self._fixed_judge(1.0),  # type: ignore[arg-type]
        )
        self.assertFalse(report.passed)
        self.assertIn('required phrase', report.results[0].failures)

    def test_no_judge_prompt_skips_judge_call(self) -> None:
        called = []

        def judge(task: str, output: str) -> JudgeScore:
            called.append(True)
            return JudgeScore(score=1.0, reasoning='')

        cases = [EvalCase(name='c1', task='t')]
        run_eval_with_judge(cases, run_case=lambda c: 'out', judge_fn=judge)
        self.assertEqual(called, [])

    def test_threshold_from_judge_fn_attribute(self) -> None:
        def judge(task: str, output: str) -> JudgeScore:
            return JudgeScore(score=0.5, reasoning='mid')

        judge._passing_threshold = 0.4  # type: ignore[attr-defined]
        cases = [EvalCase(name='c1', task='t', judge_prompt='q')]
        report = run_eval_with_judge(cases, run_case=lambda c: 'out', judge_fn=judge)
        self.assertTrue(report.passed)


class MakeLLMJudgeFnTests(unittest.TestCase):
    def _fake_adapter(self, content: str) -> object:
        class FakeResponse:
            def __init__(self, c: str) -> None:
                self.content = c
                self.estimated_cost_cents = 0.0

        class FakeAdapter:
            def complete(self, req: object) -> FakeResponse:
                return FakeResponse(content)

        return FakeAdapter()

    def test_parses_json_score(self) -> None:
        adapter = self._fake_adapter('{"score": 0.85, "reasoning": "good job"}')
        judge_fn = make_llm_judge_fn(adapter)  # type: ignore[arg-type]
        score = judge_fn('task', 'output')
        self.assertAlmostEqual(score.score, 0.85)
        self.assertEqual(score.reasoning, 'good job')

    def test_parses_score_from_non_json_response(self) -> None:
        adapter = self._fake_adapter('The score is "score": 0.6 and "reasoning": "ok"')
        judge_fn = make_llm_judge_fn(adapter)  # type: ignore[arg-type]
        score = judge_fn('task', 'output')
        self.assertAlmostEqual(score.score, 0.6)

    def test_clamps_score_to_0_1(self) -> None:
        adapter = self._fake_adapter('{"score": 1.5, "reasoning": "overflow"}')
        judge_fn = make_llm_judge_fn(adapter)  # type: ignore[arg-type]
        score = judge_fn('task', 'output')
        self.assertAlmostEqual(score.score, 1.0)

    def test_error_on_adapter_failure(self) -> None:
        class FailAdapter:
            def complete(self, req: object) -> object:
                raise RuntimeError('model down')

        judge_fn = make_llm_judge_fn(FailAdapter())  # type: ignore[arg-type]
        score = judge_fn('task', 'output')
        self.assertAlmostEqual(score.score, 0.0)
        self.assertIn('judge error', score.reasoning)

    def test_passing_threshold_stored_on_fn(self) -> None:
        adapter = self._fake_adapter('{"score": 0.9, "reasoning": "x"}')
        judge_fn = make_llm_judge_fn(adapter, passing_threshold=0.8)  # type: ignore[arg-type]
        self.assertAlmostEqual(judge_fn._passing_threshold, 0.8)  # type: ignore[attr-defined]


if __name__ == '__main__':
    unittest.main()
