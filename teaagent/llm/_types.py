from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol


class LLMAdapterError(RuntimeError):
    """Base exception for LLM adapter errors."""

    pass


class LLMConfigurationError(LLMAdapterError):
    """Exception raised when LLM adapter configuration is invalid."""

    pass


class ProviderKeyError(LLMConfigurationError):
    """Missing or invalid provider API key."""

    def __init__(
        self,
        provider: str,
        env_var: str,
        *,
        hint: str | None = None,
    ) -> None:
        message = f'{provider} requires {env_var}'
        super().__init__(message)
        self.provider = provider
        self.env_var = env_var
        self.hint = hint or (
            f'Export {env_var} or run `teaagent setup` to configure provider keys.'
        )


class LLMHTTPError(LLMAdapterError):
    """Exception raised for HTTP-related errors from LLM providers."""

    def __init__(self, message: str, *, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class LLMProviderError(LLMAdapterError):
    """Exception raised when LLM provider returns an error."""

    pass


class LLMResponseFormatError(LLMAdapterError):
    """Exception raised when LLM response format is invalid."""

    pass


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LLMToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any] = field(
        default_factory=lambda: {'type': 'object', 'properties': {}}
    )


@dataclass(frozen=True)
class LLMToolCall:
    tool_name: str
    tool_input: dict[str, Any]
    call_id: str = ''


class SafetyCategory(str, Enum):
    HARASSMENT = 'harassment'
    HATE_SPEECH = 'hate_speech'
    SEXUAL = 'sexual'
    VIOLENCE = 'violence'
    SELF_HARM = 'self_harm'
    DANGEROUS = 'dangerous'
    OTHER = 'other'


@dataclass(frozen=True)
class LLMSafetyBlock:
    blocked: bool
    category: Optional[SafetyCategory] = None
    detail: str = ''


class CostSource(str, Enum):
    """How the cost figure in GovernanceMetadata was obtained."""

    ESTIMATED = 'estimated'
    UNKNOWN = 'unknown'


class RefusalClass(str, Enum):
    """Normalized classification of why a provider declined to generate content."""

    NONE = 'none'
    SAFETY_BLOCK = 'safety_block'
    CONTENT_FILTER = 'content_filter'
    RATE_LIMIT = 'rate_limit'
    CONTEXT_LENGTH = 'context_length'
    AUTH_ERROR = 'auth_error'
    PROVIDER_ERROR = 'provider_error'
    UNKNOWN = 'unknown'


class ToolCallFormat(str, Enum):
    """Wire format the provider used to represent tool calls in its raw response."""

    ANTHROPIC = 'anthropic'
    OPENAI = 'openai'
    GEMINI = 'gemini'
    NORMALIZED = 'normalized'
    NONE = 'none'


@dataclass(frozen=True)
class GovernanceMetadata:
    """Required governance fields every provider adapter must populate.

    Any field the provider cannot supply must use its explicit sentinel
    (UNKNOWN / None) rather than a default zero that looks like real data.
    """

    provider_id: str
    model_id: str
    input_tokens: int
    output_tokens: int
    tokens_known: bool
    estimated_cost_cents: float
    cost_source: CostSource
    actual_cost_cents: Optional[float]
    tool_call_format: ToolCallFormat
    refusal_class: RefusalClass
    streaming_supported: bool


@dataclass(frozen=True)
class LLMRequest:
    messages: list[LLMMessage]
    model: Optional[str] = None
    system: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.2
    stream: bool = False
    on_chunk: Optional[Callable[[str], None]] = None
    tools: list[LLMToolDefinition] = field(default_factory=list)
    response_format: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class LLMResponse:
    provider: str
    model: str
    content: str
    raw: dict[str, Any] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    safety: Optional[LLMSafetyBlock] = None
    governance: Optional[GovernanceMetadata] = None

    def __post_init__(self) -> None:
        if self.governance is None:
            from teaagent.llm._config import _estimate_cost  # noqa: PLC0415

            tokens_known = self.input_tokens > 0 or self.output_tokens > 0
            cost = (
                _estimate_cost(
                    self.provider, self.model, self.input_tokens, self.output_tokens
                )
                if tokens_known
                else 0.0
            )
            object.__setattr__(
                self,
                'governance',
                GovernanceMetadata(
                    provider_id=self.provider,
                    model_id=self.model,
                    input_tokens=self.input_tokens,
                    output_tokens=self.output_tokens,
                    tokens_known=tokens_known,
                    estimated_cost_cents=cost,
                    cost_source=CostSource.ESTIMATED
                    if tokens_known
                    else CostSource.UNKNOWN,
                    actual_cost_cents=None,
                    tool_call_format=ToolCallFormat.NORMALIZED,
                    refusal_class=RefusalClass.NONE,
                    streaming_supported=False,
                ),
            )

    @property
    def estimated_cost_cents(self) -> float:
        g = self.governance
        assert g is not None  # guaranteed by __post_init__
        return g.estimated_cost_cents


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key_env: str
    default_model: str
    base_url: str
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url_env: Optional[str] = None

    def resolved_api_key(self) -> str:
        api_key = self.api_key or os.environ.get(self.api_key_env)
        if not api_key:
            raise ProviderKeyError(self.name, self.api_key_env)
        return api_key

    def resolved_model(self) -> str:
        env_prefix = self.name.upper().replace('-', '_')
        return self.model or os.environ.get(f'{env_prefix}_MODEL') or self.default_model

    def resolved_base_url(self) -> str:
        if self.name == 'workers-ai':
            workers_base_url = os.environ.get('WORKERS_AI_BASE_URL', '').strip()
            if workers_base_url:
                return workers_base_url.rstrip('/')
            gateway_compat_url = os.environ.get('AIGATEWAY_BASE_URL', '').strip()
            if gateway_compat_url:
                return gateway_compat_url.rstrip('/')
        base_url = (
            os.environ[self.base_url_env].strip()
            if self.base_url_env and os.environ.get(self.base_url_env)
            else self.base_url
        )
        if '{ACCOUNT_ID}' in base_url:
            account_id = os.environ.get('CLOUDFLARE_ACCOUNT_ID', '').strip()
            if account_id:
                base_url = base_url.replace('{ACCOUNT_ID}', account_id)
        if '{GATEWAY_ID}' in base_url:
            gateway_id = os.environ.get('CLOUDFLARE_GATEWAY_ID', '').strip()
            if gateway_id:
                base_url = base_url.replace('{GATEWAY_ID}', gateway_id)
        if '{ACCOUNT_ID}' in base_url:
            raise LLMConfigurationError(
                f'{self.name} requires CLOUDFLARE_ACCOUNT_ID or {self.base_url_env}'
            )
        if '{GATEWAY_ID}' in base_url:
            raise LLMConfigurationError(
                f'{self.name} requires CLOUDFLARE_GATEWAY_ID or {self.base_url_env}'
            )
        return base_url.rstrip('/')


class HTTPTransport(Protocol):
    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        *,
        timeout: int,
    ) -> dict[str, Any]: ...


class _AdapterConfigLike(Protocol):
    """Structural protocol for adapter config objects that provide resolved_* helpers."""

    def resolved_api_key(self) -> str: ...
    def resolved_model(self) -> str: ...
    def resolved_base_url(self) -> str: ...


class LLMAdapter(Protocol):
    provider: str
    config: _AdapterConfigLike

    def complete(self, request: LLMRequest) -> LLMResponse: ...
