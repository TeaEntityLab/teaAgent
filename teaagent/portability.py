from __future__ import annotations

from dataclasses import dataclass, field

REQUIRED_PROVIDER_CAPABILITIES = {
    'tool_calling',
    'structured_output',
    'system_prompt',
}


@dataclass(frozen=True)
class ProviderProfile:
    name: str
    model: str
    capabilities: frozenset[str]
    limits: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class PortabilityResult:
    provider: ProviderProfile
    missing_capabilities: frozenset[str]
    warnings: tuple[str, ...]

    @property
    def portable(self) -> bool:
        return not self.missing_capabilities


def assess_provider_portability(
    providers: list[ProviderProfile],
) -> list[PortabilityResult]:
    results: list[PortabilityResult] = []
    for provider in providers:
        missing = frozenset(REQUIRED_PROVIDER_CAPABILITIES - provider.capabilities)
        warnings = []
        if 'prompt_caching' not in provider.capabilities:
            warnings.append('prompt caching unavailable; long tasks may cost more')
        if (
            provider.limits.get('max_context_tokens', 0)
            and provider.limits['max_context_tokens'] < 128000
        ):
            warnings.append('context window below recommended portability baseline')
        results.append(
            PortabilityResult(
                provider=provider,
                missing_capabilities=missing,
                warnings=tuple(warnings),
            )
        )
    return results
