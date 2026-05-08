from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable

from teaagent.llm import (
    LLMMessage,
    LLMRequest,
    available_providers,
    check_llm_configuration,
    create_llm_adapter,
)


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


AdapterFactory = Callable[..., object]
ConfigurationChecker = Callable[[str], tuple[bool, str]]


def run_model_conformance(
    providers: Iterable[str] | None = None,
    *,
    prompt: str = 'Reply with exactly: ok',
    expected_content: str | None = 'ok',
    max_tokens: int = 32,
    model: str | None = None,
    adapter_factory: AdapterFactory = create_llm_adapter,
    configuration_checker: ConfigurationChecker = check_llm_configuration,
) -> ModelConformanceReport:
    selected_providers = list(providers or available_providers())
    results = [
        _run_provider_conformance(
            provider,
            prompt=prompt,
            expected_content=expected_content,
            max_tokens=max_tokens,
            model=model,
            adapter_factory=adapter_factory,
            configuration_checker=configuration_checker,
        )
        for provider in selected_providers
    ]
    return ModelConformanceReport(results=results)


def _run_provider_conformance(
    provider: str,
    *,
    prompt: str,
    expected_content: str | None,
    max_tokens: int,
    model: str | None,
    adapter_factory: AdapterFactory,
    configuration_checker: ConfigurationChecker,
) -> ModelConformanceResult:
    configured, message = configuration_checker(provider)
    if not configured:
        return ModelConformanceResult(
            provider=provider, status='skipped', error=message
        )

    try:
        adapter = adapter_factory(provider, model=model)
        response = adapter.complete(  # type: ignore[attr-defined]
            LLMRequest(
                messages=[LLMMessage(role='user', content=prompt)],
                max_tokens=max_tokens,
            )
        )
    except Exception as exc:
        return ModelConformanceResult(
            provider=provider,
            status='failed',
            error=f'{type(exc).__name__}: {exc}',
        )

    content = response.content.strip()
    if not content:
        return ModelConformanceResult(
            provider=provider,
            status='failed',
            model=response.model,
            error='provider returned empty content',
        )
    if expected_content is not None and content != expected_content:
        return ModelConformanceResult(
            provider=provider,
            status='failed',
            model=response.model,
            content=content,
            error=f'provider returned {content!r}; expected {expected_content!r}',
        )
    return ModelConformanceResult(
        provider=provider,
        status='passed',
        model=response.model,
        content=content,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        estimated_cost_cents=response.estimated_cost_cents,
    )


def run_tiered_conformance(
    providers: Iterable[str] | None = None,
    *,
    tier: ConformanceTier = ConformanceTier.SMOKE,
    model: str | None = None,
    adapter_factory: AdapterFactory = create_llm_adapter,
    configuration_checker: ConfigurationChecker = check_llm_configuration,
) -> TieredConformanceReport:
    selected_providers = list(providers or available_providers())
    results = [
        _run_tiered_provider(
            provider,
            tier=tier,
            model=model,
            adapter_factory=adapter_factory,
            configuration_checker=configuration_checker,
        )
        for provider in selected_providers
    ]
    return TieredConformanceReport(tier=tier.value, results=results)


def _run_tiered_provider(
    provider: str,
    *,
    tier: ConformanceTier,
    model: str | None,
    adapter_factory: AdapterFactory,
    configuration_checker: ConfigurationChecker,
) -> TieredConformanceResult:
    configured, message = configuration_checker(provider)
    if not configured:
        return TieredConformanceResult(
            provider=provider, tier=tier.value, status='skipped', error=message
        )

    try:
        adapter = adapter_factory(provider, model=model)
        resolved_model = None

        checks: list[CheckResult] = []

        # --- smoke: non-empty response ---
        smoke_response = adapter.complete(  # type: ignore[attr-defined]
            LLMRequest(
                messages=[LLMMessage(role='user', content='Reply with exactly: ok')],
                max_tokens=32,
            )
        )
        resolved_model = smoke_response.model
        smoke_content = smoke_response.content.strip()
        if smoke_content:
            checks.append(CheckResult(name='non_empty_response', status='passed'))
        else:
            checks.append(
                CheckResult(
                    name='non_empty_response', status='failed', detail='empty content'
                )
            )
            return TieredConformanceResult(
                provider=provider,
                tier=tier.value,
                status='failed',
                checks=checks,
                model=resolved_model,
                error='provider returned empty content',
            )

        if tier == ConformanceTier.CONTRACT:
            # --- contract: exact content match ---
            if smoke_content == 'ok':
                checks.append(CheckResult(name='exact_content_match', status='passed'))
            else:
                checks.append(
                    CheckResult(
                        name='exact_content_match',
                        status='failed',
                        detail=f'got {smoke_content!r}; expected "ok"',
                    )
                )

            # --- contract: system prompt adherence ---
            sys_response = adapter.complete(  # type: ignore[attr-defined]
                LLMRequest(
                    messages=[LLMMessage(role='user', content='Say hello briefly.')],
                    system='Always begin your reply with exactly "CONTRACT-OK:" followed by your answer.',
                    max_tokens=64,
                )
            )
            sys_content = sys_response.content.strip()
            if sys_content.startswith('CONTRACT-OK:'):
                checks.append(
                    CheckResult(name='system_prompt_adherence', status='passed')
                )
            else:
                checks.append(
                    CheckResult(
                        name='system_prompt_adherence',
                        status='failed',
                        detail=f'response did not start with "CONTRACT-OK:": {sys_content[:80]!r}',
                    )
                )

            # --- contract: token budget reported ---
            if smoke_response.input_tokens > 0 and smoke_response.output_tokens > 0:
                checks.append(
                    CheckResult(name='token_budget_reported', status='passed')
                )
            else:
                checks.append(
                    CheckResult(
                        name='token_budget_reported',
                        status='failed',
                        detail=f'input_tokens={smoke_response.input_tokens} output_tokens={smoke_response.output_tokens}',
                    )
                )

    except Exception as exc:
        return TieredConformanceResult(
            provider=provider,
            tier=tier.value,
            status='failed',
            checks=checks if 'checks' in dir() else [],
            model=resolved_model if 'resolved_model' in dir() else None,
            error=f'{type(exc).__name__}: {exc}',
        )

    overall = 'passed' if all(c.status == 'passed' for c in checks) else 'failed'
    return TieredConformanceResult(
        provider=provider,
        tier=tier.value,
        status=overall,
        checks=checks,
        model=resolved_model,
    )
