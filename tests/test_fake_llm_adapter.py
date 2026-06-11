from __future__ import annotations

from teaagent.llm import (
    FakeLLMAdapter,
    LLMMessage,
    LLMRequest,
    create_fake_text_response,
    create_fake_tool_call_response,
)


def test_fake_adapter_returns_scripted_responses() -> None:
    """Test that FakeLLMAdapter returns scripted responses in order."""
    adapter = FakeLLMAdapter()
    adapter.add_response(create_fake_text_response('First response'))
    adapter.add_response(create_fake_text_response('Second response'))

    request = LLMRequest(messages=[LLMMessage(role='user', content='test')])

    response1 = adapter.complete(request)
    assert response1.content == 'First response'

    response2 = adapter.complete(request)
    assert response2.content == 'Second response'


def test_fake_adapter_returns_default_when_no_scripted_responses() -> None:
    """Test that FakeLLMAdapter returns a default response when no scripted responses are available."""
    adapter = FakeLLMAdapter()
    request = LLMRequest(messages=[LLMMessage(role='user', content='test')])

    response = adapter.complete(request)
    assert response.content == 'Fake response'


def test_fake_adapter_reset_reuses_responses() -> None:
    """Test that reset() allows reusing scripted responses."""
    adapter = FakeLLMAdapter()
    adapter.add_response(create_fake_text_response('Response'))

    request = LLMRequest(messages=[LLMMessage(role='user', content='test')])

    adapter.complete(request)
    assert adapter.call_count == 1

    adapter.reset()
    assert adapter.call_count == 0

    response2 = adapter.complete(request)
    assert response2.content == 'Response'
    assert adapter.call_count == 1


def test_create_fake_tool_call_response() -> None:
    """Test creating a fake tool call response."""
    response = create_fake_tool_call_response(
        tool_name='workspace_read_file',
        tool_input={'path': 'test.txt'},
    )

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_name == 'workspace_read_file'
    assert response.tool_calls[0].tool_input == {'path': 'test.txt'}


def test_fake_adapter_with_initial_responses() -> None:
    """Test FakeLLMAdapter initialized with responses."""
    responses = [
        create_fake_text_response('Response 1'),
        create_fake_text_response('Response 2'),
    ]
    adapter = FakeLLMAdapter(responses=responses)

    request = LLMRequest(messages=[LLMMessage(role='user', content='test')])

    response1 = adapter.complete(request)
    assert response1.content == 'Response 1'

    response2 = adapter.complete(request)
    assert response2.content == 'Response 2'
