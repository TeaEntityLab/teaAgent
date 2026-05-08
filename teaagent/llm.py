from __future__ import annotations

import json
import os
import random
import time
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
            raise LLMHTTPError(f'HTTP {exc.code}: {detail}', status_code=exc.code) from exc
        except URLError as exc:
            raise LLMHTTPError(f'HTTP request failed: {exc.reason}') from exc


@dataclass(frozen=True)
class LLMRetryConfig:
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    retry_on_status: frozenset[int] = frozenset({429, 500, 502, 503, 504})

    def delay(self, attempt: int) -> float:
        delay = self.base_delay_seconds * (2 ** attempt)
        jitter = random.uniform(0, delay * 0.5)
        return min(delay + jitter, self.max_delay_seconds)


DEFAULT_RETRY_CONFIG = LLMRetryConfig()


def _call_with_retry(
    provider: str,
    transport_fn: Callable[[], dict[str, Any]],
    retry_config: LLMRetryConfig,
) -> dict[str, Any]:
    last_exc: Optional[LLMHTTPError] = None
    for attempt in range(retry_config.max_retries + 1):
        try:
            return transport_fn()
        except LLMHTTPError as exc:
            last_exc = exc
            if attempt >= retry_config.max_retries:
                raise
            is_transient = exc.status_code in retry_config.retry_on_status
            is_network = exc.status_code == 0
            if is_transient or is_network:
                time.sleep(retry_config.delay(attempt))
                continue
            raise
    assert last_exc is not None
    raise last_exc


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
        retry_config: Optional[LLMRetryConfig] = None,
    ) -> None:
        self.config = config
        self.provider = config.name
        self.transport = transport or UrllibHTTPTransport()
        self.timeout = timeout
        self.retry_config = retry_config or DEFAULT_RETRY_CONFIG

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
        response = _call_with_retry(
            self.provider,
            lambda: self.transport.post_json(
                f'{self.config.resolved_base_url()}/chat/completions',
                self._headers(),
                payload,
                timeout=self.timeout,
            ),
            self.retry_config,
        )
        content = _extract_openai_content(self.provider, response)
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
                    delta = _first_choice_delta(self.provider, parsed)
                    chunk = delta.get('content', '')
                    if chunk and request.on_chunk:
                        request.on_chunk(chunk)
                    chunks.append(chunk)
        except HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            raise LLMHTTPError(f'HTTP {exc.code}: {detail}', status_code=exc.code) from exc
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
        retry_config: Optional[LLMRetryConfig] = None,
    ) -> None:
        self.config = config
        self.transport = transport or UrllibHTTPTransport()
        self.timeout = timeout
        self.retry_config = retry_config or DEFAULT_RETRY_CONFIG

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
        response = _call_with_retry(
            self.provider,
            lambda: self.transport.post_json(
                f'{self.config.resolved_base_url()}/messages',
                {
                    'x-api-key': self.config.resolved_api_key(),
                    'anthropic-version': '2023-06-01',
                },
                payload,
                timeout=self.timeout,
            ),
            self.retry_config,
        )
        content = _extract_claude_content(response)
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
        retry_config: Optional[LLMRetryConfig] = None,
    ) -> None:
        self.config = config
        self.transport = transport or UrllibHTTPTransport()
        self.timeout = timeout
        self.retry_config = retry_config or DEFAULT_RETRY_CONFIG

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
        response = _call_with_retry(
            self.provider,
            lambda: self.transport.post_json(
                f'{self.config.resolved_base_url()}/models/{model}:generateContent?key={self.config.resolved_api_key()}',
                {},
                payload,
                timeout=self.timeout,
            ),
            self.retry_config,
        )
        content = _extract_gemini_content(response)
        metadata = response.get('usageMetadata', {})
        return LLMResponse(
            provider=self.provider,
            model=model,
            content=content,
            raw=response,
            input_tokens=metadata.get('promptTokenCount', 0),
            output_tokens=metadata.get('candidatesTokenCount', 0),
        )


def _extract_openai_content(provider: str, response: dict[str, Any]) -> str:
    _raise_provider_error(provider, response)
    choices = response.get('choices')
    if not isinstance(choices, list) or not choices:
        raise LLMResponseFormatError(f'{provider} response missing choices')
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise LLMResponseFormatError(f'{provider} response choice is not an object')
    message = first_choice.get('message')
    if not isinstance(message, dict):
        raise LLMResponseFormatError(f'{provider} response missing message')
    content = message.get('content')
    if not isinstance(content, str) or not content:
        raise LLMResponseFormatError(f'{provider} response missing text content')
    return content


def _first_choice_delta(provider: str, response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get('choices')
    if not isinstance(choices, list) or not choices:
        raise LLMResponseFormatError(f'{provider} stream chunk missing choices')
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise LLMResponseFormatError(f'{provider} stream choice is not an object')
    delta = first_choice.get('delta', {})
    if not isinstance(delta, dict):
        raise LLMResponseFormatError(f'{provider} stream delta is not an object')
    return delta


def _extract_claude_content(response: dict[str, Any]) -> str:
    _raise_provider_error('claude', response)
    content_blocks = response.get('content')
    if not isinstance(content_blocks, list):
        raise LLMResponseFormatError('claude response missing content blocks')
    text_parts = [
        block.get('text', '')
        for block in content_blocks
        if isinstance(block, dict) and block.get('type') == 'text'
    ]
    content = ''.join(part for part in text_parts if isinstance(part, str))
    if not content:
        raise LLMResponseFormatError('claude response missing text content')
    return content


def _extract_gemini_content(response: dict[str, Any]) -> str:
    _raise_provider_error('gemini', response)
    candidates = response.get('candidates')
    if not isinstance(candidates, list) or not candidates:
        raise LLMResponseFormatError('gemini response missing candidates')
    first_candidate = candidates[0]
    if not isinstance(first_candidate, dict):
        raise LLMResponseFormatError('gemini candidate is not an object')
    content = first_candidate.get('content')
    if not isinstance(content, dict):
        raise LLMResponseFormatError('gemini response missing content')
    parts = content.get('parts')
    if not isinstance(parts, list):
        raise LLMResponseFormatError('gemini response missing parts')
    text = ''.join(
        part.get('text', '')
        for part in parts
        if isinstance(part, dict) and isinstance(part.get('text'), str)
    )
    if not text:
        raise LLMResponseFormatError('gemini response missing text content')
    return text


def _raise_provider_error(provider: str, response: dict[str, Any]) -> None:
    error = response.get('error')
    if isinstance(error, dict):
        message = error.get('message') or error.get('status') or error
        raise LLMProviderError(f'{provider} provider error: {message}')
    if isinstance(error, str):
        raise LLMProviderError(f'{provider} provider error: {error}')
    prompt_feedback = response.get('promptFeedback')
    if isinstance(prompt_feedback, dict) and prompt_feedback.get('blockReason'):
        raise LLMProviderError(
            f'{provider} provider blocked prompt: {prompt_feedback["blockReason"]}'
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


def estimate_cost_preflight(
    provider: str,
    model: str,
    approx_input_chars: int,
    max_output_tokens: int,
) -> float:
    approx_input_tokens = max(1, approx_input_chars // 3)
    cost_1k_in = PROVIDER_COST_PER_1K_INPUT.get(provider, 0.001)
    cost_1k_out = PROVIDER_COST_PER_1K_OUTPUT.get(provider, 0.001)
    cost = (approx_input_tokens * cost_1k_in + max_output_tokens * cost_1k_out) / 1000.0
    return round(cost * 100, 4)
