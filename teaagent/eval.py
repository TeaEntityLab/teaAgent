from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvalCase:
    name: str
    task: str
    expected_contains: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvalCaseResult:
    name: str
    passed: bool
    output: str
    failures: tuple[str, ...]


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
