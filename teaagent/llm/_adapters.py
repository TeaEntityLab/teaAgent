from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from typing import Any, Optional
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from teaagent.http_rate_limit import TokenRateLimiter
from teaagent.llm._extract import (
    _extract_claude_content,
    _extract_gemini_content,
    _extract_openai_content,
    _first_choice_delta,
)
from teaagent.llm._retry import DEFAULT_RETRY_CONFIG, LLMRetryConfig, _call_with_retry
from teaagent.llm._sse import consume_sse_json_chunks
from teaagent.llm._transport import UrllibHTTPTransport, build_ssl_context_from_env
from teaagent.llm._types import (
    CostSource,
    GovernanceMetadata,
    HTTPTransport,
    LLMHTTPError,
    LLMRequest,
    LLMResponse,
    LLMResponseFormatError,
    LLMSafetyBlock,
    LLMToolCall,
    ProviderConfig,
    RefusalClass,
    SafetyCategory,
    ToolCallFormat,
)

logger = logging.getLogger(__name__)

_GEMINI_SAFETY_CATEGORY_MAP: dict[str, SafetyCategory] = {
    'HARM_CATEGORY_HARASSMENT': SafetyCategory.HARASSMENT,
    'HARM_CATEGORY_HATE_SPEECH': SafetyCategory.HATE_SPEECH,
    'HARM_CATEGORY_SEXUALLY_EXPLICIT': SafetyCategory.SEXUAL,
    'HARM_CATEGORY_DANGEROUS_CONTENT': SafetyCategory.DANGEROUS,
}


def _extract_claude_tool_calls(response: dict[str, Any]) -> list[LLMToolCall]:
    calls = []
    for block in response.get('content', []):
        if isinstance(block, dict) and block.get('type') == 'tool_use':
            calls.append(
                LLMToolCall(
                    tool_name=str(block.get('name', '')),
                    tool_input=dict(block.get('input') or {}),
                    call_id=str(block.get('id', '')),
                )
            )
    return calls


def _extract_openai_tool_calls(response: dict[str, Any]) -> list[LLMToolCall]:
    calls: list[LLMToolCall] = []
    choices = response.get('choices', [])
    if not choices:
        return calls
    message = choices[0].get('message', {})
    for tc in message.get('tool_calls') or []:
        fn = tc.get('function', {})
        try:
            args = json.loads(fn.get('arguments', '{}'))
        except (json.JSONDecodeError, ValueError):
            args = {}
        calls.append(
            LLMToolCall(
                tool_name=str(fn.get('name', '')),
                tool_input=args,
                call_id=str(tc.get('id', '')),
            )
        )
    return calls


def _extract_gemini_tool_calls(response: dict[str, Any]) -> list[LLMToolCall]:
    calls = []
    for candidate in response.get('candidates', []):
        for part in candidate.get('content', {}).get('parts', []):
            fc = part.get('functionCall')
            if fc:
                calls.append(
                    LLMToolCall(
                        tool_name=str(fc.get('name', '')),
                        tool_input=dict(fc.get('args') or {}),
                    )
                )
    return calls


def _native_tool_calls_to_decision_text(tool_calls: list[LLMToolCall]) -> str:
    first = tool_calls[0]
    return json.dumps(
        {
            'type': 'tool',
            'tool_name': first.tool_name,
            'arguments': first.tool_input,
            'call_id': first.call_id,
        },
        sort_keys=True,
    )


def _extract_gemini_safety(response: dict[str, Any]) -> 'LLMSafetyBlock | None':
    for candidate in response.get('candidates', []):
        if candidate.get('finishReason') == 'SAFETY':
            for rating in candidate.get('safetyRatings', []):
                if rating.get('blocked'):
                    cat = _GEMINI_SAFETY_CATEGORY_MAP.get(
                        rating.get('category', ''), SafetyCategory.OTHER
                    )
                    return LLMSafetyBlock(blocked=True, category=cat)
            return LLMSafetyBlock(blocked=True)
    return None


def _openai_refusal_class(response: dict[str, Any]) -> RefusalClass:
    choices = response.get('choices', [])
    if choices:
        finish = choices[0].get('finish_reason', '')
        if finish == 'content_filter':
            return RefusalClass.CONTENT_FILTER
    return RefusalClass.NONE


def _gemini_refusal_class(safety: Optional[LLMSafetyBlock]) -> RefusalClass:
    if safety is not None and safety.blocked:
        return RefusalClass.SAFETY_BLOCK
    return RefusalClass.NONE


def _build_governance(
    provider_id: str,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    *,
    tokens_known: bool,
    refusal_class: RefusalClass,
    tool_call_format: ToolCallFormat,
    streaming_supported: bool,
) -> GovernanceMetadata:
    from teaagent.llm._config import _estimate_cost  # noqa: PLC0415

    cost = (
        _estimate_cost(provider_id, model_id, input_tokens, output_tokens)
        if tokens_known
        else 0.0
    )
    return GovernanceMetadata(
        provider_id=provider_id,
        model_id=model_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        tokens_known=tokens_known,
        estimated_cost_cents=cost,
        cost_source=CostSource.ESTIMATED if tokens_known else CostSource.UNKNOWN,
        actual_cost_cents=None,
        tool_call_format=tool_call_format,
        refusal_class=refusal_class,
        streaming_supported=streaming_supported,
    )


class OpenAICompatibleAdapter:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        transport: Optional[HTTPTransport] = None,
        timeout: int = 60,
        retry_config: Optional[LLMRetryConfig] = None,
        streaming_lines: Optional[list[bytes]] = None,
        rate_limiter: Optional[TokenRateLimiter] = None,
    ) -> None:
        self.config = config
        self.provider = config.name
        self.transport = transport or UrllibHTTPTransport()
        self.timeout = timeout
        self.retry_config = retry_config or DEFAULT_RETRY_CONFIG
        self._streaming_lines = streaming_lines
        self._rate_limiter = rate_limiter

    def _prepare_payload(self, request: LLMRequest, model: str) -> dict[str, Any]:
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
        if request.tools:
            payload['tools'] = [
                {
                    'type': 'function',
                    'function': {
                        'name': t.name,
                        'description': t.description,
                        'parameters': t.input_schema,
                    },
                }
                for t in request.tools
            ]
        if request.response_format and self._supports_response_format():
            payload['response_format'] = request.response_format
        if request.stream:
            payload['stream'] = True
        return payload

    def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.config.resolved_model()
        payload = self._prepare_payload(request, model)
        if request.stream:
            return self._complete_streaming(request, model, payload)
        try:
            response = self._post_chat_completions(payload)
        except LLMHTTPError as exc:
            if not (
                request.response_format and _supports_response_format_fallback(exc)
            ):
                raise
            payload = dict(payload)
            payload.pop('response_format', None)
            response = self._post_chat_completions(payload)
        tool_calls = _extract_openai_tool_calls(response)
        try:
            content = _extract_openai_content(self.provider, response)
        except LLMResponseFormatError:
            if tool_calls:
                content = _native_tool_calls_to_decision_text(tool_calls)
            else:
                raise
        usage = response.get('usage', {})
        in_tok = usage.get('prompt_tokens', 0)
        out_tok = usage.get('completion_tokens', 0)
        return LLMResponse(
            provider=self.provider,
            model=model,
            content=content,
            raw=response,
            input_tokens=in_tok,
            output_tokens=out_tok,
            tool_calls=tool_calls,
            governance=_build_governance(
                self.provider,
                model,
                in_tok,
                out_tok,
                tokens_known=bool(usage),
                refusal_class=_openai_refusal_class(response),
                tool_call_format=ToolCallFormat.OPENAI
                if tool_calls
                else ToolCallFormat.NONE,
                streaming_supported=True,
            ),
        )

    def _check_rate_limit(self, key: str) -> None:
        """Raise LLMHTTPError if the rate limit for *key* is exceeded."""
        if self._rate_limiter is not None:
            allowed, reason = self._rate_limiter.allow(key)
            if not allowed:
                logger.warning(
                    'rate_limit_exceeded: %s',
                    reason,
                    extra={
                        'event': 'rate_limit_exceeded',
                        'provider': self.provider,
                        'error_code': 'RATE_LIMIT',
                    },
                )
                raise LLMHTTPError(
                    f'rate limit exceeded for provider {self.provider}: {reason}',
                    status_code=429,
                )

    def _supports_response_format(self) -> bool:
        return self.provider not in {'opencodezen-go', 'opencodezen'}

    def _post_chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._check_rate_limit(self.provider)
        return _call_with_retry(
            self.provider,
            lambda: self.transport.post_json(
                f'{self.config.resolved_base_url()}/chat/completions',
                self._headers(),
                payload,
                timeout=self.timeout,
            ),
            self.retry_config,
        )

    def _iter_streaming_lines(self, payload: dict[str, Any]) -> Iterator[bytes]:
        self._check_rate_limit(self.provider)
        if self._streaming_lines is not None:
            for line in self._streaming_lines:
                yield line if isinstance(line, bytes) else line.encode('utf-8')
            return
        body = json.dumps(payload).encode('utf-8')
        url = f'{self.config.resolved_base_url()}/chat/completions'
        headers = {
            'user-agent': 'TeaAgent',
            **self._headers(),
        }
        req = urllib_request.Request(url, data=body, headers=headers, method='POST')
        try:
            ssl_context = build_ssl_context_from_env()
            request_kwargs: dict[str, Any] = {'timeout': self.timeout}
            if ssl_context is not None:
                request_kwargs['context'] = ssl_context
            with urllib_request.urlopen(req, **request_kwargs) as resp:
                yield from resp
        except HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            raise LLMHTTPError(
                f'HTTP {exc.code}: {detail}', status_code=exc.code
            ) from exc
        except URLError as exc:
            raise LLMHTTPError(f'HTTP request failed: {exc.reason}') from exc

    def _complete_streaming(
        self, request: LLMRequest, model: str, payload: dict[str, Any]
    ) -> LLMResponse:
        chunks: list[str] = []
        input_tokens = 0
        output_tokens = 0

        def _handle(parsed: dict[str, Any]) -> None:
            nonlocal input_tokens, output_tokens
            usage = parsed.get('usage')
            if usage:
                input_tokens = usage.get('prompt_tokens', 0)
                output_tokens = usage.get('completion_tokens', 0)
            delta = _first_choice_delta(self.provider, parsed)
            chunk = delta.get('content', '')
            if chunk and request.on_chunk:
                request.on_chunk(chunk)
            if chunk:
                chunks.append(chunk)

        consume_sse_json_chunks(
            self._iter_streaming_lines(payload),
            on_data=_handle,
        )
        tokens_known = input_tokens > 0 or output_tokens > 0
        return LLMResponse(
            provider=self.provider,
            model=model,
            content=''.join(chunks),
            raw={},
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            governance=_build_governance(
                self.provider,
                model,
                input_tokens,
                output_tokens,
                tokens_known=tokens_known,
                refusal_class=RefusalClass.NONE,
                tool_call_format=ToolCallFormat.NONE,
                streaming_supported=True,
            ),
        )

    def _headers(self) -> dict[str, str]:
        headers = {'authorization': f'Bearer {self.config.resolved_api_key()}'}
        if self.provider == 'openrouter':
            referer = os.environ.get('OPENROUTER_HTTP_REFERER')
            if referer:
                headers['HTTP-Referer'] = referer
            app_title = os.environ.get('OPENROUTER_APP_TITLE')
            if app_title:
                headers['X-Title'] = app_title
        headers.update(_provider_extra_headers(self.provider))
        return headers


class WorkersAIAdapter(OpenAICompatibleAdapter):
    """Adapter for Cloudflare Workers AI / AI Gateway.

    Workers AI has several quirks vs standard OpenAI-compatible endpoints:
    - AI Gateway's workers-ai provider route strips the ``@cf/`` model prefix.
    - Structured output (``json_schema``) is unstable and often 500s.
    - Streaming + response_format may not mix.
    """

    def __init__(
        self,
        config: ProviderConfig,
        *,
        transport: Optional[HTTPTransport] = None,
        timeout: int = 60,
        retry_config: Optional[LLMRetryConfig] = None,
        streaming_lines: Optional[list[bytes]] = None,
        disable_tools: bool = False,
        rate_limiter: Optional[TokenRateLimiter] = None,
    ) -> None:
        super().__init__(
            config,
            transport=transport,
            timeout=timeout,
            retry_config=retry_config,
            streaming_lines=streaming_lines,
            rate_limiter=rate_limiter,
        )
        self.disable_tools = disable_tools

    def _prepare_payload(self, request: LLMRequest, model: str) -> dict[str, Any]:
        # AI Gateway's workers-ai provider endpoint often expects @cf/ to be
        # stripped, otherwise it returns "Invalid provider" (HTTP 400).
        # Direct Workers AI API DOES require @cf/.
        base_url = self.config.resolved_base_url()
        parsed = urlparse(base_url)
        if parsed.hostname == 'gateway.ai.cloudflare.com' and model.startswith('@cf/'):
            model = model[4:]

        # Workers AI structured output (json_schema) is extremely unstable
        # and often 500s. Default to removing it and relying on prompt
        # instructions, unless forced via env var.
        force_json_object = (
            os.environ.get('TEAAGENT_WORKERS_AI_FORCE_JSON_OBJECT') == '1'
        )

        if request.response_format and not force_json_object:
            request = LLMRequest(
                messages=request.messages,
                model=request.model,
                system=(request.system or '')
                + '\n\nIMPORTANT: You must respond with a valid JSON object matching the requested schema. No prose.',
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                stream=request.stream,
                on_chunk=request.on_chunk,
                tools=request.tools,
                response_format=None,  # Strip it
            )

        payload = super()._prepare_payload(request, model)

        if force_json_object:
            payload['response_format'] = {'type': 'json_object'}

        # Ensure stream and response_format never mix in Workers AI
        if payload.get('stream') and 'response_format' in payload:
            del payload['response_format']

        # If tools cause 500s, allow disabling them entirely.
        if self.disable_tools and 'tools' in payload:
            del payload['tools']

        return payload


def _provider_extra_headers(provider: str) -> dict[str, str]:
    env_prefix = provider.upper().replace('-', '_')
    extra = os.environ.get(f'{env_prefix}_EXTRA_HEADERS')
    if not extra:
        return {}
    try:
        parsed = json.loads(extra)
    except json.JSONDecodeError as exc:
        raise LLMHTTPError(
            f'invalid {env_prefix}_EXTRA_HEADERS JSON: {exc.msg}'
        ) from exc
    if not isinstance(parsed, dict):
        raise LLMHTTPError(f'{env_prefix}_EXTRA_HEADERS must be a JSON object')
    normalized: dict[str, str] = {}
    for key, value in parsed.items():
        if not isinstance(key, str):
            raise LLMHTTPError(f'{env_prefix}_EXTRA_HEADERS keys must be strings')
        normalized[key] = str(value)
    return normalized


def _supports_response_format_fallback(exc: LLMHTTPError) -> bool:
    if exc.status_code < 400 or exc.status_code >= 500:
        return False
    message = str(exc).lower()
    if 'response_format' not in message:
        return False
    return (
        'unavailable' in message
        or 'unsupported' in message
        or 'not supported' in message
        or 'invalid_request_error' in message
    )


def _iter_http_post_lines(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int,
) -> Iterator[bytes]:
    body = json.dumps(payload).encode('utf-8')
    req = urllib_request.Request(
        url,
        data=body,
        headers={**headers, 'content-type': 'application/json'},
        method='POST',
    )
    try:
        ssl_context = build_ssl_context_from_env()
        request_kwargs: dict[str, Any] = {'timeout': timeout}
        if ssl_context is not None:
            request_kwargs['context'] = ssl_context
        with urllib_request.urlopen(req, **request_kwargs) as resp:
            yield from resp
    except HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise LLMHTTPError(f'HTTP {exc.code}: {detail}', status_code=exc.code) from exc
    except URLError as exc:
        raise LLMHTTPError(f'HTTP request failed: {exc.reason}') from exc


class ClaudeAdapter:
    provider = 'claude'

    def __init__(
        self,
        config: ProviderConfig,
        *,
        transport: Optional[HTTPTransport] = None,
        timeout: int = 60,
        retry_config: Optional[LLMRetryConfig] = None,
        streaming_lines: Optional[list[bytes]] = None,
        rate_limiter: Optional[TokenRateLimiter] = None,
    ) -> None:
        self.config = config
        self.transport = transport or UrllibHTTPTransport()
        self.timeout = timeout
        self.retry_config = retry_config or DEFAULT_RETRY_CONFIG
        self._streaming_lines = streaming_lines
        self._rate_limiter = rate_limiter

    def _check_rate_limit(self, key: str) -> None:
        if self._rate_limiter is not None:
            allowed, reason = self._rate_limiter.allow(key)
            if not allowed:
                logger.warning(
                    'rate_limit_exceeded: %s',
                    reason,
                    extra={
                        'event': 'rate_limit_exceeded',
                        'provider': self.provider,
                        'error_code': 'RATE_LIMIT',
                    },
                )
                raise LLMHTTPError(
                    f'rate limit exceeded for provider {self.provider}: {reason}',
                    status_code=429,
                )

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
        if request.tools:
            payload['tools'] = [
                {
                    'name': t.name,
                    'description': t.description,
                    'input_schema': t.input_schema,
                }
                for t in request.tools
            ]
        if request.stream:
            payload['stream'] = True
            return self._complete_streaming(request, model, payload)
        self._check_rate_limit(self.provider)
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
        tool_calls = _extract_claude_tool_calls(response)
        in_tok = usage.get('input_tokens', 0)
        out_tok = usage.get('output_tokens', 0)
        return LLMResponse(
            provider=self.provider,
            model=model,
            content=content,
            raw=response,
            input_tokens=in_tok,
            output_tokens=out_tok,
            tool_calls=tool_calls,
            governance=_build_governance(
                self.provider,
                model,
                in_tok,
                out_tok,
                tokens_known=bool(usage),
                refusal_class=RefusalClass.NONE,
                tool_call_format=ToolCallFormat.ANTHROPIC
                if tool_calls
                else ToolCallFormat.NONE,
                streaming_supported=True,
            ),
        )

    def _iter_streaming_lines(self, payload: dict[str, Any]) -> Iterator[bytes]:
        self._check_rate_limit(self.provider)
        if self._streaming_lines is not None:
            for line in self._streaming_lines:
                yield line if isinstance(line, bytes) else line.encode('utf-8')
            return
        yield from _iter_http_post_lines(
            url=f'{self.config.resolved_base_url()}/messages',
            headers={
                'x-api-key': self.config.resolved_api_key(),
                'anthropic-version': '2023-06-01',
            },
            payload=payload,
            timeout=self.timeout,
        )

    def _complete_streaming(
        self, request: LLMRequest, model: str, payload: dict[str, Any]
    ) -> LLMResponse:
        chunks: list[str] = []
        input_tokens = 0
        output_tokens = 0

        def _handle(parsed: dict[str, Any]) -> None:
            nonlocal input_tokens, output_tokens
            event_type = parsed.get('type', '')
            usage = parsed.get('usage')
            if isinstance(usage, dict):
                input_tokens = usage.get('input_tokens', input_tokens)
                output_tokens = usage.get('output_tokens', output_tokens)
            text = ''
            if event_type == 'content_block_delta' or event_type == 'message_delta':
                delta = parsed.get('delta', {})
                if isinstance(delta, dict):
                    text = str(delta.get('text', ''))
            if text and request.on_chunk:
                request.on_chunk(text)
            if text:
                chunks.append(text)

        consume_sse_json_chunks(self._iter_streaming_lines(payload), on_data=_handle)
        tokens_known = input_tokens > 0 or output_tokens > 0
        return LLMResponse(
            provider=self.provider,
            model=model,
            content=''.join(chunks),
            raw={},
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            governance=_build_governance(
                self.provider,
                model,
                input_tokens,
                output_tokens,
                tokens_known=tokens_known,
                refusal_class=RefusalClass.NONE,
                tool_call_format=ToolCallFormat.NONE,
                streaming_supported=True,
            ),
        )


def _extract_gemini_stream_text(parsed: dict[str, Any]) -> str:
    parts: list[str] = []
    for candidate in parsed.get('candidates', []):
        if not isinstance(candidate, dict):
            continue
        content = candidate.get('content', {})
        if not isinstance(content, dict):
            continue
        for part in content.get('parts', []):
            if isinstance(part, dict) and isinstance(part.get('text'), str):
                parts.append(part['text'])
    return ''.join(parts)


class GeminiAdapter:
    provider = 'gemini'

    def __init__(
        self,
        config: ProviderConfig,
        *,
        transport: Optional[HTTPTransport] = None,
        timeout: int = 60,
        retry_config: Optional[LLMRetryConfig] = None,
        streaming_lines: Optional[list[bytes]] = None,
        rate_limiter: Optional[TokenRateLimiter] = None,
    ) -> None:
        self.config = config
        self.transport = transport or UrllibHTTPTransport()
        self.timeout = timeout
        self.retry_config = retry_config or DEFAULT_RETRY_CONFIG
        self._streaming_lines = streaming_lines
        self._rate_limiter = rate_limiter

    def _check_rate_limit(self, key: str) -> None:
        if self._rate_limiter is not None:
            allowed, reason = self._rate_limiter.allow(key)
            if not allowed:
                logger.warning(
                    'rate_limit_exceeded: %s',
                    reason,
                    extra={
                        'event': 'rate_limit_exceeded',
                        'provider': self.provider,
                        'error_code': 'RATE_LIMIT',
                    },
                )
                raise LLMHTTPError(
                    f'rate limit exceeded for provider {self.provider}: {reason}',
                    status_code=429,
                )

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
        if request.tools:
            payload['tools'] = [
                {
                    'functionDeclarations': [
                        {
                            'name': t.name,
                            'description': t.description,
                            'parameters': t.input_schema,
                        }
                    ]
                }
                for t in request.tools
            ]
        if request.stream:
            return self._complete_streaming(request, model, payload)
        self._check_rate_limit(self.provider)
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
        tool_calls = _extract_gemini_tool_calls(response)
        safety = _extract_gemini_safety(response)
        in_tok = metadata.get('promptTokenCount', 0)
        out_tok = metadata.get('candidatesTokenCount', 0)
        return LLMResponse(
            provider=self.provider,
            model=model,
            content=content,
            raw=response,
            input_tokens=in_tok,
            output_tokens=out_tok,
            tool_calls=tool_calls,
            safety=safety,
            governance=_build_governance(
                self.provider,
                model,
                in_tok,
                out_tok,
                tokens_known=bool(metadata),
                refusal_class=_gemini_refusal_class(safety),
                tool_call_format=ToolCallFormat.GEMINI
                if tool_calls
                else ToolCallFormat.NONE,
                streaming_supported=True,
            ),
        )

    def _iter_streaming_lines(
        self, model: str, payload: dict[str, Any]
    ) -> Iterator[bytes]:
        self._check_rate_limit(self.provider)
        if self._streaming_lines is not None:
            for line in self._streaming_lines:
                yield line if isinstance(line, bytes) else line.encode('utf-8')
            return
        url = (
            f'{self.config.resolved_base_url()}/models/{model}:streamGenerateContent'
            f'?key={self.config.resolved_api_key()}&alt=sse'
        )
        yield from _iter_http_post_lines(
            url=url,
            headers={},
            payload=payload,
            timeout=self.timeout,
        )

    def _complete_streaming(
        self, request: LLMRequest, model: str, payload: dict[str, Any]
    ) -> LLMResponse:
        chunks: list[str] = []
        input_tokens = 0
        output_tokens = 0

        def _handle(parsed: dict[str, Any]) -> None:
            nonlocal input_tokens, output_tokens
            metadata = parsed.get('usageMetadata', {})
            if isinstance(metadata, dict):
                input_tokens = metadata.get('promptTokenCount', input_tokens)
                output_tokens = metadata.get('candidatesTokenCount', output_tokens)
            text = _extract_gemini_stream_text(parsed)
            if text and request.on_chunk:
                request.on_chunk(text)
            if text:
                chunks.append(text)

        consume_sse_json_chunks(
            self._iter_streaming_lines(model, payload),
            on_data=_handle,
        )
        tokens_known = input_tokens > 0 or output_tokens > 0
        return LLMResponse(
            provider=self.provider,
            model=model,
            content=''.join(chunks),
            raw={},
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            governance=_build_governance(
                self.provider,
                model,
                input_tokens,
                output_tokens,
                tokens_known=tokens_known,
                refusal_class=RefusalClass.NONE,
                tool_call_format=ToolCallFormat.NONE,
                streaming_supported=True,
            ),
        )
