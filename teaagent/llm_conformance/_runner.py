from __future__ import annotations

from typing import Callable, Iterable

from teaagent.llm import (
    LLMMessage,
    LLMRequest,
    available_providers,
    check_llm_configuration,
    create_llm_adapter,
)

from ._types import (
    CheckResult,
    ConformanceTier,
    ModelConformanceReport,
    ModelConformanceResult,
    TieredConformanceReport,
    TieredConformanceResult,
)

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

    checks: list[CheckResult] = []
    resolved_model: str | None = None
    try:
        adapter = adapter_factory(provider, model=model)

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

        if tier == ConformanceTier.STREAMING:
            chunks: list[str] = []
            adapter.complete(  # type: ignore[attr-defined]
                LLMRequest(
                    messages=[LLMMessage(role='user', content='Count to 3 briefly.')],
                    max_tokens=64,
                    stream=True,
                    on_chunk=chunks.append,
                )
            )
            if chunks:
                checks.append(
                    CheckResult(
                        name='streaming_chunks_received',
                        status='passed',
                        detail=f'{len(chunks)} chunk(s) received',
                    )
                )
            else:
                checks.append(
                    CheckResult(
                        name='streaming_chunks_received',
                        status='failed',
                        detail='stream=True produced no on_chunk calls',
                    )
                )

        elif tier == ConformanceTier.STRUCTURED_OUTPUT:
            import json as _json

            json_response = adapter.complete(  # type: ignore[attr-defined]
                LLMRequest(
                    system='You must respond with valid JSON only. No prose.',
                    messages=[
                        LLMMessage(
                            role='user',
                            content='Return a JSON object with key "status" set to "ok".',
                        )
                    ],
                    max_tokens=64,
                )
            )
            raw = json_response.content.strip()
            try:
                parsed = _json.loads(raw)
                if isinstance(parsed, dict):
                    checks.append(
                        CheckResult(name='structured_json_output', status='passed')
                    )
                else:
                    checks.append(
                        CheckResult(
                            name='structured_json_output',
                            status='failed',
                            detail=f'parsed value is not a dict: {raw[:80]}',
                        )
                    )
            except _json.JSONDecodeError:
                checks.append(
                    CheckResult(
                        name='structured_json_output',
                        status='failed',
                        detail=f'response is not valid JSON: {raw[:80]}',
                    )
                )

        elif tier == ConformanceTier.CONTRACT:
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
            checks=checks,
            model=resolved_model,
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
