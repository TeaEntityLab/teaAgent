from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ConformanceTier(str, Enum):
    SMOKE = 'smoke'
    CONTRACT = 'contract'


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str = ''


@dataclass(frozen=True)
class TieredConformanceResult:
    provider: str
    tier: str
    status: str
    checks: list[CheckResult] = field(default_factory=list)
    model: str | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            'provider': self.provider,
            'tier': self.tier,
            'status': self.status,
            'checks': [
                {'name': c.name, 'status': c.status, 'detail': c.detail}
                for c in self.checks
            ],
        }
        if self.model is not None:
            payload['model'] = self.model
        if self.error:
            payload['error'] = self.error
        return payload


@dataclass(frozen=True)
class TieredConformanceReport:
    tier: str
    results: list[TieredConformanceResult]

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == 'passed')

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == 'failed')

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == 'skipped')

    @property
    def ok(self) -> bool:
        return self.failed == 0

    def as_dict(self) -> dict[str, object]:
        return {
            'tier': self.tier,
            'ok': self.ok,
            'passed': self.passed,
            'failed': self.failed,
            'skipped': self.skipped,
            'results': [r.as_dict() for r in self.results],
        }


@dataclass(frozen=True)
class ModelConformanceResult:
    provider: str
    status: str
    model: str | None = None
    content: str = ''
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_cents: float = 0.0

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            'provider': self.provider,
            'status': self.status,
        }
        if self.model is not None:
            payload['model'] = self.model
        if self.content:
            payload['content'] = self.content
        if self.error:
            payload['error'] = self.error
        if self.status == 'passed':
            payload['input_tokens'] = self.input_tokens
            payload['output_tokens'] = self.output_tokens
            payload['estimated_cost_cents'] = self.estimated_cost_cents
        return payload


@dataclass(frozen=True)
class ModelConformanceReport:
    results: list[ModelConformanceResult]

    @property
    def passed(self) -> int:
        return sum(1 for result in self.results if result.status == 'passed')

    @property
    def failed(self) -> int:
        return sum(1 for result in self.results if result.status == 'failed')

    @property
    def skipped(self) -> int:
        return sum(1 for result in self.results if result.status == 'skipped')

    @property
    def ok(self) -> bool:
        return self.failed == 0

    def as_dict(self) -> dict[str, object]:
        return {
            'ok': self.ok,
            'passed': self.passed,
            'failed': self.failed,
            'skipped': self.skipped,
            'results': [result.as_dict() for result in self.results],
        }
