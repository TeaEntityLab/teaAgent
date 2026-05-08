from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError


class LLMAdapterError(RuntimeError):
    pass


class LLMConfigurationError(LLMAdapterError):
    pass


class LLMHTTPError(LLMAdapterError):
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


class UrllibHTTPTransport:
    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        *,
        timeout: int,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode('utf-8')
        req = urllib_request.Request(
            url,
            data=body,
            headers={'content-type': 'application/json', **headers},
            method='POST',
        )
        try:
            with urllib_request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            raise LLMHTTPError(f'HTTP {exc.code}: {detail}') from exc
        except URLError as exc:
            raise LLMHTTPError(f'HTTP request failed: {exc.reason}') from exc


class LLMAdapter(Protocol):
    provider: str

    def complete(self, request: LLMRequest) -> LLMResponse: ...


class OpenAICompatibleAdapter:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        transport: Optional[HTTPTransport] = None,
        timeout: int = 60,
    ) -> None:
        self.config = config
        self.provider = config.name
        self.transport = transport or UrllibHTTPTransport()
        self.timeout = timeout

    def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.config.resolved_model()
        messages = []
        if request.system:
            messages.append({'role': 'system', 'content': request.system})
        messages.extend(
            {'role': message.role, 'content': message.content}
            for message in request.messages
        )
        payload: dict[str, Any] = {
            'model': model,
            'messages': messages,
            'max_tokens': request.max_tokens,
            'temperature': request.temperature,
        }
        if request.stream:
            payload['stream'] = True
            return self._complete_streaming(request, model, payload)
        response = self.transport.post_json(
            f'{self.config.resolved_base_url()}/chat/completions',
            self._headers(),
            payload,
            timeout=self.timeout,
        )
        content = response.get('choices', [{}])[0].get('message', {}).get('content', '')
        usage = response.get('usage', {})
        return LLMResponse(
            provider=self.provider,
            model=model,
            content=content,
            raw=response,
            input_tokens=usage.get('prompt_tokens', 0),
            output_tokens=usage.get('completion_tokens', 0),
        )

    def _complete_streaming(
        self, request: LLMRequest, model: str, payload: dict[str, Any]
    ) -> LLMResponse:
        body = json.dumps(payload).encode('utf-8')
        url = f'{self.config.resolved_base_url()}/chat/completions'
        headers = {'content-type': 'application/json', **self._headers()}
        chunks: list[str] = []
        input_tokens = 0
        output_tokens = 0
        req = urllib_request.Request(url, data=body, headers=headers, method='POST')
        try:
            with urllib_request.urlopen(req, timeout=self.timeout) as response:
                for raw_line in response:
                    line = raw_line.decode('utf-8', errors='replace').strip()
                    if not line.startswith('data: '):
                        continue
                    data = line[6:]
                    if data == '[DONE]':
                        break
                    try:
                        parsed = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    usage = parsed.get('usage')
                    if usage:
                        input_tokens = usage.get('prompt_tokens', 0)
                        output_tokens = usage.get('completion_tokens', 0)
                    delta = parsed.get('choices', [{}])[0].get('delta', {})
                    chunk = delta.get('content', '')
                    if chunk and request.on_chunk:
                        request.on_chunk(chunk)
                    chunks.append(chunk)
        except HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            raise LLMHTTPError(f'HTTP {exc.code}: {detail}') from exc
        except URLError as exc:
            raise LLMHTTPError(f'HTTP request failed: {exc.reason}') from exc
        return LLMResponse(
            provider=self.provider,
            model=model,
            content=''.join(chunks),
            raw={},
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def _headers(self) -> dict[str, str]:
        headers = {'authorization': f'Bearer {self.config.resolved_api_key()}'}
        if self.provider == 'openrouter':
            if os.environ.get('OPENROUTER_HTTP_REFERER'):
                headers['HTTP-Referer'] = os.environ['OPENROUTER_HTTP_REFERER']
            if os.environ.get('OPENROUTER_APP_TITLE'):
                headers['X-Title'] = os.environ['OPENROUTER_APP_TITLE']
        return headers


class ClaudeAdapter:
    provider = 'claude'

    def __init__(
        self,
        config: ProviderConfig,
        *,
        transport: Optional[HTTPTransport] = None,
        timeout: int = 60,
    ) -> None:
        self.config = config
        self.transport = transport or UrllibHTTPTransport()
        self.timeout = timeout

    def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.config.resolved_model()
        payload: dict[str, Any] = {
            'model': model,
            'max_tokens': request.max_tokens,
            'temperature': request.temperature,
            'messages': [
                {'role': message.role, 'content': message.content}
                for message in request.messages
            ],
        }
        if request.system:
            payload['system'] = request.system
        response = self.transport.post_json(
            f'{self.config.resolved_base_url()}/messages',
            {
                'x-api-key': self.config.resolved_api_key(),
                'anthropic-version': '2023-06-01',
            },
            payload,
            timeout=self.timeout,
        )
        content_blocks = response.get('content', [])
        content = ''.join(
            block.get('text', '')
            for block in content_blocks
            if block.get('type') == 'text'
        )
        usage = response.get('usage', {})
        return LLMResponse(
            provider=self.provider,
            model=model,
            content=content,
            raw=response,
            input_tokens=usage.get('input_tokens', 0),
            output_tokens=usage.get('output_tokens', 0),
        )


class GeminiAdapter:
    provider = 'gemini'

    def __init__(
        self,
        config: ProviderConfig,
        *,
        transport: Optional[HTTPTransport] = None,
        timeout: int = 60,
    ) -> None:
        self.config = config
        self.transport = transport or UrllibHTTPTransport()
        self.timeout = timeout

    def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.config.resolved_model()
        contents = []
        for message in request.messages:
            role = 'model' if message.role == 'assistant' else 'user'
            contents.append({'role': role, 'parts': [{'text': message.content}]})
        payload: dict[str, Any] = {
            'contents': contents,
            'generationConfig': {
                'maxOutputTokens': request.max_tokens,
                'temperature': request.temperature,
            },
        }
        if request.system:
            payload['systemInstruction'] = {'parts': [{'text': request.system}]}
        response = self.transport.post_json(
            f'{self.config.resolved_base_url()}/models/{model}:generateContent?key={self.config.resolved_api_key()}',
            {},
            payload,
            timeout=self.timeout,
        )
        parts = response.get('candidates', [{}])[0].get('content', {}).get('parts', [])
        content = ''.join(part.get('text', '') for part in parts)
        metadata = response.get('usageMetadata', {})
        return LLMResponse(
            provider=self.provider,
            model=model,
            content=content,
            raw=response,
            input_tokens=metadata.get('promptTokenCount', 0),
            output_tokens=metadata.get('candidatesTokenCount', 0),
        )


PROVIDER_CONFIGS = {
    'claude': ProviderConfig(
        name='claude',
        api_key_env='ANTHROPIC_API_KEY',
        default_model='claude-3-5-sonnet-latest',
        base_url='https://api.anthropic.com/v1',
        base_url_env='ANTHROPIC_BASE_URL',
    ),
    'gpt': ProviderConfig(
        name='gpt',
        api_key_env='OPENAI_API_KEY',
        default_model='gpt-4o-mini',
        base_url='https://api.openai.com/v1',
        base_url_env='OPENAI_BASE_URL',
    ),
    'gemini': ProviderConfig(
        name='gemini',
        api_key_env='GEMINI_API_KEY',
        default_model='gemini-1.5-flash',
        base_url='https://generativelanguage.googleapis.com/v1beta',
        base_url_env='GEMINI_BASE_URL',
    ),
    'openrouter': ProviderConfig(
        name='openrouter',
        api_key_env='OPENROUTER_API_KEY',
        default_model='openai/gpt-4o-mini',
        base_url='https://openrouter.ai/api/v1',
        base_url_env='OPENROUTER_BASE_URL',
    ),
    'opencodezen-go': ProviderConfig(
        name='opencodezen-go',
        api_key_env='OPENCODEZEN_API_KEY',
        default_model='opencodezen-go',
        base_url='https://api.opencodezen.com/v1',
        base_url_env='OPENCODEZEN_BASE_URL',
    ),
}


def available_providers() -> list[str]:
    return sorted(PROVIDER_CONFIGS)


def create_llm_adapter(
    provider: str,
    *,
    transport: Optional[HTTPTransport] = None,
    model: Optional[str] = None,
) -> LLMAdapter:
    normalized = provider.lower()
    if normalized not in PROVIDER_CONFIGS:
        raise LLMConfigurationError(
            f"unknown provider '{provider}'. Available: {', '.join(available_providers())}"
        )
    config = PROVIDER_CONFIGS[normalized]
    if model:
        config = ProviderConfig(
            name=config.name,
            api_key_env=config.api_key_env,
            default_model=config.default_model,
            base_url=config.base_url,
            api_key=config.api_key,
            model=model,
            base_url_env=config.base_url_env,
        )
    if normalized == 'claude':
        return ClaudeAdapter(config, transport=transport)
    if normalized == 'gemini':
        return GeminiAdapter(config, transport=transport)
    return OpenAICompatibleAdapter(config, transport=transport)


def check_llm_configuration(provider: str) -> tuple[bool, str]:
    adapter = create_llm_adapter(provider)
    try:
        adapter.config.resolved_api_key()  # type: ignore[attr-defined]
    except LLMConfigurationError as exc:
        return False, str(exc)
    return True, f'{provider} configuration is available'


PROVIDER_COST_PER_1K_INPUT = {
    'claude': 0.003,
    'gpt': 0.00015,
    'gemini': 0.000075,
    'openrouter': 0.0005,
    'opencodezen-go': 0.0005,
}

PROVIDER_COST_PER_1K_OUTPUT = {
    'claude': 0.015,
    'gpt': 0.0006,
    'gemini': 0.0003,
    'openrouter': 0.002,
    'opencodezen-go': 0.002,
}


def _estimate_cost(
    provider: str, model: str, input_tokens: int, output_tokens: int
) -> float:
    cost_1k_in = PROVIDER_COST_PER_1K_INPUT.get(provider, 0.001)
    cost_1k_out = PROVIDER_COST_PER_1K_OUTPUT.get(provider, 0.001)
    cost = (input_tokens * cost_1k_in + output_tokens * cost_1k_out) / 1000.0
    return round(cost * 100, 4)
