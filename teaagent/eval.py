from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class JudgeScore:
    score: float
    reasoning: str


@dataclass(frozen=True)
class EvalCase:
    name: str
    task: str
    expected_contains: tuple[str, ...] = field(default_factory=tuple)
    judge_prompt: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvalCaseResult:
    name: str
    passed: bool
    output: str
    failures: tuple[str, ...]
    judge_score: Optional[JudgeScore] = None


@dataclass(frozen=True)
class EvalReport:
    results: list[EvalCaseResult]

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for result in self.results if result.passed) / len(self.results)


JudgeFn = Callable[[str, str], JudgeScore]

_SCORE_RE = re.compile(r'"score"\s*:\s*([0-9]*\.?[0-9]+)')
_REASON_RE = re.compile(r'"reasoning"\s*:\s*"([^"]*)"')

_DEFAULT_JUDGE_SYSTEM = (
    'You are an impartial evaluator. Score the agent output from 0.0 (completely wrong) '
    'to 1.0 (perfect). Reply with JSON only: {"score": <float>, "reasoning": "<one sentence>"}'
)


def make_llm_judge_fn(
    adapter: Any,
    *,
    passing_threshold: float = 0.7,
    system_prompt: str = _DEFAULT_JUDGE_SYSTEM,
) -> JudgeFn:
    from teaagent.llm import LLMMessage, LLMRequest

    def judge(task: str, output: str) -> JudgeScore:
        user_content = f'Task: {task}\n\nAgent output:\n{output}'
        try:
            response = adapter.complete(
                LLMRequest(
                    system=system_prompt,
                    messages=[LLMMessage(role='user', content=user_content)],
                )
            )
            raw = response.content.strip()
            try:
                payload = json.loads(raw)
                score = float(payload.get('score', 0.0))
                reasoning = str(payload.get('reasoning', ''))
            except (json.JSONDecodeError, ValueError):
                sm = _SCORE_RE.search(raw)
                rm = _REASON_RE.search(raw)
                score = float(sm.group(1)) if sm else 0.0
                reasoning = rm.group(1) if rm else raw[:200]
            score = max(0.0, min(1.0, score))
            return JudgeScore(score=score, reasoning=reasoning)
        except Exception as exc:
            return JudgeScore(score=0.0, reasoning=f'judge error: {exc}')

    judge._passing_threshold = passing_threshold  # type: ignore[attr-defined]
    return judge


def run_eval(cases: list[EvalCase], run_case: Callable[[EvalCase], str]) -> EvalReport:
    results: list[EvalCaseResult] = []
    for case in cases:
        output = run_case(case)
        failures = tuple(
            expected
            for expected in case.expected_contains
            if expected.lower() not in output.lower()
        )
        results.append(
            EvalCaseResult(
                name=case.name,
                passed=not failures,
                output=output,
                failures=failures,
            )
        )
    return EvalReport(results=results)


def run_eval_with_judge(
    cases: list[EvalCase],
    run_case: Callable[[EvalCase], str],
    judge_fn: JudgeFn,
    *,
    passing_threshold: float = 0.7,
) -> EvalReport:
    threshold = getattr(judge_fn, '_passing_threshold', passing_threshold)
    results: list[EvalCaseResult] = []
    for case in cases:
        output = run_case(case)
        failures = tuple(
            expected
            for expected in case.expected_contains
            if expected.lower() not in output.lower()
        )
        judge_score: Optional[JudgeScore] = None
        if case.judge_prompt is not None:
            task_with_criteria = (
                f'{case.task}\n\nEvaluation criteria: {case.judge_prompt}'
            )
            judge_score = judge_fn(task_with_criteria, output)
        judge_passed = judge_score is None or judge_score.score >= threshold
        results.append(
            EvalCaseResult(
                name=case.name,
                passed=not failures and judge_passed,
                output=output,
                failures=failures,
                judge_score=judge_score,
            )
        )
    return EvalReport(results=results)
