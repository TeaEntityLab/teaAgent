"""Tests for FocusStackManager and auto-local compression."""

from teaagent.context import CompactionManager
from teaagent.session import (
    ChatMessage,
    ChatSession,
    FocusFrame,
    FocusStackManager,
    FocusState,
)


def test_focus_frame_creation():
    """Test FocusFrame creation and serialization."""
    frame = FocusFrame(
        topic='Auth Refactoring', state=FocusState.CREATED, message_start_index=0
    )

    assert frame.topic == 'Auth Refactoring'
    assert frame.state == FocusState.CREATED

    data = frame.to_dict()
    restored = FocusFrame.from_dict(data)

    assert restored.topic == frame.topic
    assert restored.state == frame.state


def test_focus_stack_push_pop():
    """Test push and pop operations on focus stack."""
    stack = FocusStackManager()

    stack.push('Topic A', message_index=0)
    assert len(stack.frames) == 1
    assert stack.current().topic == 'Topic A'
    assert stack.current().state == FocusState.CREATED

    stack.push('Topic B', message_index=5)
    assert len(stack.frames) == 2
    assert stack.current().topic == 'Topic B'
    assert stack.frames[0].state == FocusState.PUSHED

    popped = stack.pop(conclusion='Topic B completed')
    assert len(stack.frames) == 1
    assert popped.topic == 'Topic B'
    assert popped.state == FocusState.RETURNED
    assert popped.conclusion == 'Topic B completed'
    assert stack.current().state == FocusState.KEPT


def test_focus_stack_serialization():
    """Test FocusStackManager serialization."""
    stack = FocusStackManager()
    stack.push('Topic A', message_index=0)
    stack.push('Topic B', message_index=5)

    data = stack.to_dict()
    restored = FocusStackManager.from_dict(data)

    assert len(restored.frames) == 2
    assert restored.frames[0].topic == 'Topic A'
    assert restored.frames[1].topic == 'Topic B'


def test_session_compression_on_topic_return():
    """Test that session compresses messages when topic is returned."""
    session = ChatSession(id='test-session')
    session.messages = [
        ChatMessage(role='user', content='Start Topic A'),
        ChatMessage(role='assistant', content='Response 1'),
        ChatMessage(role='user', content='Follow up'),
        ChatMessage(role='assistant', content='Response 2'),
    ]

    frame = FocusFrame(
        topic='Topic A',
        state=FocusState.RETURNED,
        message_start_index=0,
        message_end_index=4,
        conclusion='Topic A completed successfully',
    )

    compaction_manager = CompactionManager(max_context_tokens=200000)

    session.compress_returned_topic(frame, compaction_manager)

    assert len(session.messages) == 1
    assert session.messages[0].role == 'system'
    assert '[Topic Summarized: Topic A]' in session.messages[0].content
    assert 'Topic A completed successfully' in session.messages[0].content


def test_session_focus_stack_integration():
    """Test ChatSession with focus stack integration."""
    session = ChatSession(id='test-session')

    session.focus_stack.push('Auth Refactoring', message_index=0)
    session.messages.append(ChatMessage(role='user', content='Refactor auth'))

    assert len(session.focus_stack.frames) == 1
    assert session.focus_stack.current().topic == 'Auth Refactoring'

    session_data = session.to_dict()
    restored = ChatSession.from_dict(session_data)

    assert len(restored.focus_stack.frames) == 1
    assert restored.focus_stack.current().topic == 'Auth Refactoring'
