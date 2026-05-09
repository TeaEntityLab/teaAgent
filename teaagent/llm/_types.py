from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
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
class LLMRequest:
    messages: list[LLMMessage]
    model: Optional[str] = None
    system: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.2
    stream: bool = False
    on_chunk: Optional[Callable[[str], None]] = None


@dataclass(frozen=True)
class LLMResponse:
    provider: str
    model: str
    content: str
    raw: dict[str, Any] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0

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
        return (
            self.model
            or os.environ.get(f'{self.name.upper()}_MODEL')
            or self.default_model
        )

    def resolved_base_url(self) -> str:
        if self.base_url_env and os.environ.get(self.base_url_env):
            return os.environ[self.base_url_env].rstrip('/')
        return self.base_url.rstrip('/')


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
