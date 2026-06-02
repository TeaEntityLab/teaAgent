from __future__ import annotations

from typing import Any, Optional

from teaagent.llm._types import (
    LLMRequest,
    LLMResponse,
    LLMToolCall,
)


class FakeLLMAdapter:
    """A fake LLM adapter for testing that returns scripted responses.

    This adapter allows tests to provide scripted responses without using
    MagicMock or @patch, making tests more maintainable and closer to real
    integration tests.
    """

    def __init__(
        self,
        provider: str = 'fake',
        model: str = 'fake-model',
        responses: Optional[list[LLMResponse]] = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self._responses = responses or []
        self._call_count = 0
        # Add a fake config for compatibility with code that expects it
        class FakeProviderConfig:
            def __init__(self, provider: str, model: str) -> None:
                self.name = provider
                self.api_key_env = 'FAKE_API_KEY'
                self.default_model = model
                self.base_url = 'https://fake.example.com/v1'
                self.api_key = 'fake-key'
                self.model = model
                self.base_url_env = 'FAKE_BASE_URL'

            def resolved_api_key(self) -> str:
                return 'fake-key'

            def resolved_model(self) -> str:
                return self.default_model

            def resolved_base_url(self) -> str:
                return self.base_url

        self.config = FakeProviderConfig(provider, model)

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Return the next scripted response, or a default response if none available."""
        if self._call_count < len(self._responses):
            response = self._responses[self._call_count]
            self._call_count += 1
            return response

        # Default response if no scripted response available
        return LLMResponse(
            provider=self.provider,
            model=self.model,
            content='Fake response',
            input_tokens=0,
            output_tokens=0,
        )

    def add_response(self, response: LLMResponse) -> None:
        """Add a scripted response to the queue."""
        self._responses.append(response)

    def reset(self) -> None:
        """Reset the call counter to reuse scripted responses."""
        self._call_count = 0

    @property
    def call_count(self) -> int:
        """Return the number of times complete() has been called."""
        return self._call_count


def create_fake_text_response(
    content: str,
    provider: str = 'fake',
    model: str = 'fake-model',
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> LLMResponse:
    """Create a fake LLM response with text content."""
    return LLMResponse(
        provider=provider,
        model=model,
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def create_fake_tool_call_response(
    tool_name: str,
    tool_input: dict[str, Any],
    call_id: str = 'fake-call-id',
    provider: str = 'fake',
    model: str = 'fake-model',
) -> LLMResponse:
    """Create a fake LLM response with a tool call."""
    import json

    tool_call = LLMToolCall(
        tool_name=tool_name,
        tool_input=tool_input,
        call_id=call_id,
    )
    return LLMResponse(
        provider=provider,
        model=model,
        content=json.dumps(
            {
                'type': 'tool',
                'tool_name': tool_name,
                'arguments': tool_input,
                'call_id': call_id,
            }
        ),
        input_tokens=0,
        output_tokens=0,
        tool_calls=[tool_call],
    )
