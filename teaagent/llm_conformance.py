from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from teaagent.llm import (
    LLMMessage,
    LLMRequest,
    available_providers,
    check_llm_configuration,
    create_llm_adapter,
)


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
