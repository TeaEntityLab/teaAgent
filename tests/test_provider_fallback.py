"""Unit tests for LLM provider fallback resilience."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from teaagent.llm import LLMHTTPError, LLMRequest, LLMResponse
from teaagent.provider_fallback import (
    ModelFallbackPolicy,
    ProviderFallbackEvent,
    ResilientLLMAdapter,
    classify_provider_failure,
    load_fallback_policy,
    maybe_wrap_adapter_with_fallback,
    should_attempt_fallback,
)
from teaagent.types import BudgetExceededError


class _StubAdapter:
    def __init__(
        self,
        provider: str,
        *,
        model: str = 'model-a',
        fail_with: Exception | None = None,
        content: str = 'ok',
    ) -> None:
        self.provider = provider
        self.fail_with = fail_with
        self.content = content

        class _Cfg:
            def __init__(self, provider: str, model: str) -> None:
                self.name = provider
                self.model = model

            def resolved_model(self) -> str:
                return self.model

        self.config = _Cfg(provider, model)

    def complete(self, request: LLMRequest) -> LLMResponse:
        if self.fail_with is not None:
            raise self.fail_with
        return LLMResponse(
            provider=self.provider,
            model=self.config.model,
            content=self.content,
        )


def test_classify_provider_failure_outage_and_budget() -> None:
    assert classify_provider_failure(LLMHTTPError('down', status_code=503)) == 'outage'
    assert (
        classify_provider_failure(LLMHTTPError('limit', status_code=429)) == 'throttled'
    )
    assert classify_provider_failure(BudgetExceededError('cap')) == 'budget'


def test_should_not_fallback_on_budget_or_credential() -> None:
    policy = ModelFallbackPolicy(primary=_target('anthropic'))
    assert not should_attempt_fallback(BudgetExceededError('cap'), policy=policy)
    assert not should_attempt_fallback(
        LLMHTTPError('auth', status_code=401), policy=policy
    )


def _target(provider: str, model: str | None = 'm1'):
    from teaagent.provider_fallback import FallbackTarget

    return FallbackTarget(provider, model)


def test_resilient_adapter_uses_fallback_on_outage() -> None:
    primary = _StubAdapter(
        'anthropic',
        fail_with=LLMHTTPError('503', status_code=503),
    )
    fallback = _StubAdapter('gpt', content='fallback answer')
    events: list[ProviderFallbackEvent] = []

    wrapped = ResilientLLMAdapter(
        primary,
        fallbacks=[(fallback, _target('gpt', 'gpt-4o-mini'))],
        policy=ModelFallbackPolicy(
            primary=_target('anthropic'), fallbacks=(_target('gpt'),)
        ),
        on_fallback=events.append,
    )
    response = wrapped.complete(LLMRequest(system='s', messages=[]))
    assert response.content == 'fallback answer'
    assert wrapped.fallback_used is True
    assert events[0].to_provider == 'gpt'


def test_resilient_adapter_reraises_when_no_fallback_succeeds() -> None:
    primary = _StubAdapter(
        'anthropic',
        fail_with=LLMHTTPError('503', status_code=503),
    )
    fallback = _StubAdapter(
        'gpt',
        fail_with=LLMHTTPError('503', status_code=503),
    )
    wrapped = ResilientLLMAdapter(
        primary,
        fallbacks=[(fallback, _target('gpt'))],
        policy=ModelFallbackPolicy(
            primary=_target('anthropic'), fallbacks=(_target('gpt'),)
        ),
    )
    with pytest.raises(LLMHTTPError):
        wrapped.complete(LLMRequest(system='s', messages=[]))


def test_load_fallback_policy_from_workspace_config(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.json'
    config.parent.mkdir(parents=True)
    config.write_text(
        '{"fallback_provider": "gpt", "fallback_model": "gpt-4o-mini"}',
        encoding='utf-8',
    )
    policy = load_fallback_policy(
        tmp_path,
        primary_provider='anthropic',
        primary_model='claude-sonnet',
    )
    assert policy is not None
    assert policy.fallbacks[0].provider == 'gpt'
    assert policy.fallbacks[0].model == 'gpt-4o-mini'


def test_maybe_wrap_adapter_records_provider_fallback_event() -> None:
    events: list[dict] = []

    class _Audit:
        def record(self, event_type: str, run_id: str, **payload) -> None:
            events.append({'event_type': event_type, 'run_id': run_id, **payload})

    primary = _StubAdapter(
        'anthropic',
        fail_with=LLMHTTPError('503', status_code=503),
    )
    fallback = _StubAdapter('gpt', content='recovered')

    def factory(provider: str, *, model=None):
        if provider == 'anthropic':
            return primary
        return fallback

    with tempfile.TemporaryDirectory() as tmp:
        config = Path(tmp) / '.teaagent' / 'config.json'
        config.parent.mkdir(parents=True)
        config.write_text('{"fallback_provider": "gpt"}', encoding='utf-8')
        wrapped = maybe_wrap_adapter_with_fallback(
            primary,
            root=tmp,
            primary_provider='anthropic',
            primary_model='claude-sonnet',
            audit=_Audit(),
            run_id='run-fallback',
            adapter_factory=factory,
        )
        response = wrapped.complete(LLMRequest(system='s', messages=[]))
        assert response.content == 'recovered'
        assert any(e['event_type'] == 'provider_fallback' for e in events)
