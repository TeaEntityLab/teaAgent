from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol


class LLMAdapterError(RuntimeError):
    pass


class LLMConfigurationError(LLMAdapterError):
    pass


class LLMHTTPError(LLMAdapterError):
    def __init__(self, message: str, *, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class LLMProviderError(LLMAdapterError):
    pass


class LLMResponseFormatError(LLMAdapterError):
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

    @property
    def estimated_cost_cents(self) -> float:
        from teaagent.llm._config import _estimate_cost  # noqa: PLC0415

        return _estimate_cost(
            self.provider, self.model, self.input_tokens, self.output_tokens
        )


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
            raise LLMConfigurationError(f'{self.name} requires {self.api_key_env}')
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


class LLMAdapter(Protocol):
    provider: str

    def complete(self, request: LLMRequest) -> LLMResponse: ...
