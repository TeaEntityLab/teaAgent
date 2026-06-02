from __future__ import annotations

import unittest

from teaagent.llm import (
    FakeLLMAdapter,
    LLMMessage,
    LLMRequest,
    create_fake_text_response,
    create_fake_tool_call_response,
)


class TestFakeLLMAdapter(unittest.TestCase):
    def test_fake_adapter_returns_scripted_responses(self) -> None:
        """Test that FakeLLMAdapter returns scripted responses in order."""
        adapter = FakeLLMAdapter()
        adapter.add_response(create_fake_text_response('First response'))
        adapter.add_response(create_fake_text_response('Second response'))

        request = LLMRequest(messages=[LLMMessage(role='user', content='test')])

        response1 = adapter.complete(request)
        self.assertEqual(response1.content, 'First response')

        response2 = adapter.complete(request)
        self.assertEqual(response2.content, 'Second response')

    def test_fake_adapter_returns_default_when_no_scripted_responses(self) -> None:
        """Test that FakeLLMAdapter returns a default response when no scripted responses are available."""
        adapter = FakeLLMAdapter()
        request = LLMRequest(messages=[LLMMessage(role='user', content='test')])

        response = adapter.complete(request)
        self.assertEqual(response.content, 'Fake response')

    def test_fake_adapter_reset_reuses_responses(self) -> None:
        """Test that reset() allows reusing scripted responses."""
        adapter = FakeLLMAdapter()
        adapter.add_response(create_fake_text_response('Response'))

        request = LLMRequest(messages=[LLMMessage(role='user', content='test')])

        response1 = adapter.complete(request)
        self.assertEqual(adapter.call_count, 1)

        adapter.reset()
        self.assertEqual(adapter.call_count, 0)

        response2 = adapter.complete(request)
        self.assertEqual(response2.content, 'Response')
        self.assertEqual(adapter.call_count, 1)

    def test_create_fake_tool_call_response(self) -> None:
        """Test creating a fake tool call response."""
        response = create_fake_tool_call_response(
            tool_name='workspace_read_file',
            tool_input={'path': 'test.txt'},
        )

        self.assertEqual(len(response.tool_calls), 1)
        self.assertEqual(response.tool_calls[0].tool_name, 'workspace_read_file')
        self.assertEqual(response.tool_calls[0].tool_input, {'path': 'test.txt'})

    def test_fake_adapter_with_initial_responses(self) -> None:
        """Test FakeLLMAdapter initialized with responses."""
        responses = [
            create_fake_text_response('Response 1'),
            create_fake_text_response('Response 2'),
        ]
        adapter = FakeLLMAdapter(responses=responses)

        request = LLMRequest(messages=[LLMMessage(role='user', content='test')])

        response1 = adapter.complete(request)
        self.assertEqual(response1.content, 'Response 1')

        response2 = adapter.complete(request)
        self.assertEqual(response2.content, 'Response 2')


if __name__ == '__main__':
    unittest.main()
