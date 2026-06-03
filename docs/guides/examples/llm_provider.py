"""Working example: custom LLM provider adapter.

Shows how to implement, register, and smoke-test a new provider adapter
that satisfies the LLMAdapter protocol.

Run (requires an OpenAI-compatible endpoint at MY_PROVIDER_BASE_URL):

    MY_PROVIDER_API_KEY=sk-... python3 docs/guides/examples/llm_provider.py

Without credentials it falls back to a stub that validates the interface.
"""

from __future__ import annotations

import os
from typing import Any

from teaagent.llm import (
    LLMAdapter,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMResponseFormatError,
)


# ── adapter implementation ────────────────────────────────────────────────────


class MyProviderAdapter:
    """Minimal OpenAI-compatible provider adapter."""

    provider = 'my-provider'

    def __init__(
        self,
        api_key: str,
        base_url: str = 'https://api.my-provider.example/v1',
        model: str = 'my-model-v1',
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip('/')
        self._model = model

    def complete(self, request: LLMRequest) -> LLMResponse:
        import httpx

        messages = [{'role': m.role, 'content': m.content} for m in request.messages]
        payload: dict[str, Any] = {
            'model': request.model or self._model,
            'messages': messages,
            'max_tokens': request.max_tokens or 4096,
            'temperature': request.temperature
            if request.temperature is not None
            else 0.7,
        }
        if request.system:
            # Insert system message at the front (OpenAI-style)
            payload['messages'] = [
                {'role': 'system', 'content': request.system}
            ] + messages

        resp = httpx.post(
            f'{self._base_url}/chat/completions',
            json=payload,
            headers={'Authorization': f'Bearer {self._api_key}'},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        try:
            content = data['choices'][0]['message']['content']
        except (KeyError, IndexError) as exc:
            raise LLMResponseFormatError(
                f'my-provider returned unexpected shape: {data}'
            ) from exc

        if not content:
            raise LLMResponseFormatError('my-provider returned empty content')

        usage = data.get('usage', {})
        return LLMResponse(
            content=content,
            input_tokens=usage.get('prompt_tokens', 0),
            output_tokens=usage.get('completion_tokens', 0),
            raw=data,
        )


# ── stub for offline testing ──────────────────────────────────────────────────


class StubAdapter:
    """Deterministic stub — no network needed."""

    provider = 'stub'

    def complete(self, request: LLMRequest) -> LLMResponse:
        last = request.messages[-1].content if request.messages else ''
        return LLMResponse(
            content=f'[stub] echo: {last[:60]}',
            input_tokens=len(last) // 4,
            output_tokens=10,
            raw={'stub': True},
        )


# ── smoke test ────────────────────────────────────────────────────────────────


def smoke_test(adapter: LLMAdapter) -> None:
    print(f'Provider: {adapter.provider}')
    request = LLMRequest(
        messages=[LLMMessage(role='user', content='Say hello in one word.')],
        system='You are a concise assistant.',
        max_tokens=16,
    )
    response = adapter.complete(request)
    print(f'Content:  {response.content!r}')
    print(f'Tokens:   in={response.input_tokens} out={response.output_tokens}')
    assert response.content, 'content must be non-empty'
    assert response.input_tokens >= 0, 'input_tokens must be >= 0'
    assert response.output_tokens >= 0, 'output_tokens must be >= 0'
    print('Smoke test passed.\n')


def main() -> None:
    api_key = os.environ.get('MY_PROVIDER_API_KEY')
    base_url = os.environ.get(
        'MY_PROVIDER_BASE_URL', 'https://api.my-provider.example/v1'
    )

    if api_key:
        print('Using MyProviderAdapter (live):')
        adapter: LLMAdapter = MyProviderAdapter(api_key=api_key, base_url=base_url)
    else:
        print('MY_PROVIDER_API_KEY not set — using StubAdapter (offline demo):')
        adapter = StubAdapter()

    smoke_test(adapter)


if __name__ == '__main__':
    main()
