from __future__ import annotations

import json
import os
from typing import Any, Optional
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from teaagent.llm._extract import (
    _extract_claude_content,
    _extract_gemini_content,
    _extract_openai_content,
    _first_choice_delta,
)
from teaagent.llm._retry import DEFAULT_RETRY_CONFIG, LLMRetryConfig, _call_with_retry
from teaagent.llm._transport import UrllibHTTPTransport, build_ssl_context_from_env
from teaagent.llm._types import (
    HTTPTransport,
    LLMHTTPError,
    LLMRequest,
    LLMResponse,
    LLMResponseFormatError,
    LLMSafetyBlock,
    LLMToolCall,
    ProviderConfig,
    SafetyCategory,
)

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
        except Exception:
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


class OpenAICompatibleAdapter:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        transport: Optional[HTTPTransport] = None,
        timeout: int = 60,
        retry_config: Optional[LLMRetryConfig] = None,
        streaming_lines: Optional[list[bytes]] = None,
    ) -> None:
        self.config = config
        self.provider = config.name
        self.transport = transport or UrllibHTTPTransport()
        self.timeout = timeout
        self.retry_config = retry_config or DEFAULT_RETRY_CONFIG
        self._streaming_lines = streaming_lines

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
        tool_calls = _extract_openai_tool_calls(response)
        try:
            content = _extract_openai_content(self.provider, response)
        except LLMResponseFormatError:
            if tool_calls:
                content = _native_tool_calls_to_decision_text(tool_calls)
            else:
                raise
        usage = response.get('usage', {})
        return LLMResponse(
            provider=self.provider,
            model=model,
            content=content,
            raw=response,
            input_tokens=usage.get('prompt_tokens', 0),
            output_tokens=usage.get('completion_tokens', 0),
            tool_calls=tool_calls,
        )

    def _complete_streaming(
        self, request: LLMRequest, model: str, payload: dict[str, Any]
    ) -> LLMResponse:
        chunks: list[str] = []
        input_tokens = 0
        output_tokens = 0
        if self._streaming_lines is not None:
            lines = self._streaming_lines
        else:
            body = json.dumps(payload).encode('utf-8')
            url = f'{self.config.resolved_base_url()}/chat/completions'
            headers = {
                'content-type': 'application/json',
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
                    lines = list(resp)
            except HTTPError as exc:
                detail = exc.read().decode('utf-8', errors='replace')
                raise LLMHTTPError(
                    f'HTTP {exc.code}: {detail}', status_code=exc.code
                ) from exc
            except URLError as exc:
                raise LLMHTTPError(f'HTTP request failed: {exc.reason}') from exc
        for raw_line in lines:
            line = (
                raw_line.decode('utf-8', errors='replace').strip()
                if isinstance(raw_line, bytes)
                else str(raw_line).strip()
            )
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
        if request.tools:
            payload['tools'] = [
                {
                    'name': t.name,
                    'description': t.description,
                    'input_schema': t.input_schema,
                }
                for t in request.tools
            ]
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
        return LLMResponse(
            provider=self.provider,
            model=model,
            content=content,
            raw=response,
            input_tokens=usage.get('input_tokens', 0),
            output_tokens=usage.get('output_tokens', 0),
            tool_calls=tool_calls,
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
        return LLMResponse(
            provider=self.provider,
            model=model,
            content=content,
            raw=response,
            input_tokens=metadata.get('promptTokenCount', 0),
            output_tokens=metadata.get('candidatesTokenCount', 0),
            tool_calls=tool_calls,
            safety=safety,
        )
