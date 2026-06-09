"""LLM provider fallback for outage resilience (F-ECO-009 / provider-resilience-playbook)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from teaagent.ergonomics.workspace_defaults import load_workspace_defaults
from teaagent.llm import LLMHTTPError, LLMRequest, LLMResponse, create_llm_adapter
from teaagent.types import BudgetExceededError


@dataclass(frozen=True)
class FallbackTarget:
    provider: str
    model: str | None = None


@dataclass(frozen=True)
class ModelFallbackPolicy:
    primary: FallbackTarget
    fallbacks: tuple[FallbackTarget, ...] = ()
    on_outage: bool = True
    on_throttled: bool = True

    def ordered_targets(self) -> tuple[FallbackTarget, ...]:
        return (self.primary, *self.fallbacks)


@dataclass
class ProviderFallbackEvent:
    from_provider: str
    from_model: str
    to_provider: str
    to_model: str
    reason: str
    failure_class: str


def classify_provider_failure(exc: Exception) -> str:
    if isinstance(exc, BudgetExceededError):
        return 'budget'
    if isinstance(exc, LLMHTTPError):
        code = int(getattr(exc, 'status_code', 0) or 0)
        if code in {401, 403}:
            return 'credential'
        if code == 429:
            return 'throttled'
        if code >= 500:
            return 'outage'
    return 'provider_error'


def should_attempt_fallback(exc: Exception, *, policy: ModelFallbackPolicy) -> bool:
    failure_class = classify_provider_failure(exc)
    if failure_class == 'budget':
        return False
    if failure_class == 'credential':
        return False
    if failure_class == 'throttled':
        return policy.on_throttled
    if failure_class == 'outage':
        return policy.on_outage
    return False


def load_fallback_policy(
    root: str | Path,
    *,
    primary_provider: str,
    primary_model: str | None,
) -> ModelFallbackPolicy | None:
    defaults = load_workspace_defaults(root)
    fallback_provider = defaults.get('fallback_provider')
    if not isinstance(fallback_provider, str) or not fallback_provider.strip():
        return None
    fallback_model = defaults.get('fallback_model')
    model = (
        fallback_model if isinstance(fallback_model, str) and fallback_model else None
    )
    return ModelFallbackPolicy(
        primary=FallbackTarget(primary_provider, primary_model),
        fallbacks=(FallbackTarget(fallback_provider.strip(), model),),
    )


class ResilientLLMAdapter:
    """Adapter wrapper that tries configured fallbacks on retriable provider failures."""

    def __init__(
        self,
        primary: Any,
        *,
        fallbacks: list[tuple[Any, FallbackTarget]],
        policy: ModelFallbackPolicy,
        on_fallback: Callable[[ProviderFallbackEvent], None] | None = None,
    ) -> None:
        self._primary = primary
        self._fallbacks = fallbacks
        self._policy = policy
        self._on_fallback = on_fallback
        self._active = primary
        self.fallback_used = False
        self.fallback_events: list[ProviderFallbackEvent] = []
        self.provider = getattr(primary, 'provider', 'unknown')
        self.model = getattr(getattr(primary, 'config', None), 'model', None)
        self.config = getattr(primary, 'config', None)
        self.transport = getattr(primary, 'transport', None)

    def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            return self._active.complete(request)
        except Exception as exc:
            if not should_attempt_fallback(exc, policy=self._policy):
                raise
            return self._activate_next_fallback(request, exc)

    def _activate_next_fallback(
        self, request: LLMRequest, primary_exc: Exception
    ) -> LLMResponse:
        failure_class = classify_provider_failure(primary_exc)
        from_provider = getattr(self._active, 'provider', self.provider)
        from_model = getattr(getattr(self._active, 'config', None), 'model', None) or ''
        errors = [str(primary_exc)]
        for adapter, target in self._fallbacks:
            try:
                response = adapter.complete(request)
            except Exception as exc:
                errors.append(str(exc))
                continue
            event = ProviderFallbackEvent(
                from_provider=from_provider,
                from_model=str(from_model),
                to_provider=target.provider,
                to_model=str(target.model or adapter.config.resolved_model()),
                reason='; '.join(errors),
                failure_class=failure_class,
            )
            self.fallback_used = True
            self.fallback_events.append(event)
            self._active = adapter
            self.provider = target.provider
            self.model = target.model or getattr(adapter.config, 'model', None)
            self.config = adapter.config
            self.transport = getattr(adapter, 'transport', self.transport)
            if self._on_fallback is not None:
                self._on_fallback(event)
            return response
        raise primary_exc


def maybe_wrap_adapter_with_fallback(
    adapter: Any,
    *,
    root: str | Path,
    primary_provider: str,
    primary_model: str | None,
    audit: Any | None = None,
    run_id: str | None = None,
    adapter_factory: Callable[..., Any] | None = None,
) -> Any:
    """Wrap *adapter* when workspace config defines ``fallback_provider``."""
    policy = load_fallback_policy(
        root,
        primary_provider=primary_provider,
        primary_model=primary_model,
    )
    if policy is None or not policy.fallbacks:
        return adapter

    factory = adapter_factory or create_llm_adapter
    fallback_adapters: list[tuple[Any, FallbackTarget]] = []
    for target in policy.fallbacks:
        fallback_adapters.append(
            (
                factory(target.provider, model=target.model),
                target,
            )
        )

    def _record_fallback(event: ProviderFallbackEvent) -> None:
        if audit is None or run_id is None:
            return
        audit.record(
            'provider_fallback',
            run_id,
            from_provider=event.from_provider,
            from_model=event.from_model,
            to_provider=event.to_provider,
            to_model=event.to_model,
            failure_class=event.failure_class,
            reason=event.reason,
        )

    return ResilientLLMAdapter(
        adapter,
        fallbacks=fallback_adapters,
        policy=policy,
        on_fallback=_record_fallback,
    )
