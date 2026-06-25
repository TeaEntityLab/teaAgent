from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class FocusState(Enum):
    """Focus state for topic tracking."""

    CREATED = 'created'
    KEPT = 'kept'
    PUSHED = 'pushed'
    RETURNED = 'returned'
    CLEARED = 'cleared'


@dataclass
class FocusFrame:
    """A single frame in the focus stack representing a topic."""

    topic: str
    state: FocusState = FocusState.CREATED
    message_start_index: int = 0
    message_end_index: int = 0
    conclusion: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'topic': self.topic,
            'state': self.state.value,
            'message_start_index': self.message_start_index,
            'message_end_index': self.message_end_index,
            'conclusion': self.conclusion,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'FocusFrame':
        return cls(
            topic=data.get('topic', ''),
            state=FocusState(data.get('state', FocusState.CREATED.value)),
            message_start_index=data.get('message_start_index', 0),
            message_end_index=data.get('message_end_index', 0),
            conclusion=data.get('conclusion', ''),
        )


@dataclass
class FocusStackManager:
    """Manages a stack of focus frames for topic tracking."""

    frames: list[FocusFrame] = field(default_factory=list)

    def push(self, topic: str, message_index: int) -> None:
        """Push a new topic onto the stack."""
        if self.frames:
            self.frames[-1].state = FocusState.PUSHED
        self.frames.append(
            FocusFrame(
                topic=topic, state=FocusState.CREATED, message_start_index=message_index
            )
        )

    def pop(self, conclusion: str = '') -> Optional[FocusFrame]:
        """Pop the current topic from the stack."""
        if not self.frames:
            return None
        frame = self.frames.pop()
        frame.state = FocusState.RETURNED
        frame.conclusion = conclusion
        if self.frames:
            self.frames[-1].state = FocusState.KEPT
        return frame

    def current(self) -> Optional[FocusFrame]:
        """Get the current focus frame."""
        return self.frames[-1] if self.frames else None

    def to_dict(self) -> dict[str, Any]:
        return {'frames': [f.to_dict() for f in self.frames]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'FocusStackManager':
        return cls(frames=[FocusFrame.from_dict(f) for f in data.get('frames', [])])


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        return {'role': self.role, 'content': self.content}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ChatMessage':
        return cls(role=data['role'], content=data['content'])


@dataclass
class ChatSession:
    id: str
    created_at: str = field(default_factory=lambda: _utcnow())
    updated_at: str = field(default_factory=lambda: _utcnow())
    messages: list[ChatMessage] = field(default_factory=list)
    label: str = ''
    focus_stack: FocusStackManager = field(default_factory=FocusStackManager)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'messages': [m.to_dict() for m in self.messages],
            'label': self.label,
            'focus_stack': self.focus_stack.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ChatSession':
        return cls(
            id=data.get('id', ''),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            messages=[ChatMessage.from_dict(m) for m in data.get('messages', [])],
            label=data.get('label', ''),
            focus_stack=FocusStackManager.from_dict(data.get('focus_stack', {})),
        )

    def compress_returned_topic(
        self, frame: FocusFrame, compaction_manager: Any | None = None
    ) -> None:
        """Compress messages from a returned topic into a summary card.

        Args:
            frame: The focus frame that was returned.
            compaction_manager: Optional :class:`~teaagent.context.CompactionManager`
                used to compact the full chat history after topic summarization.
        """
        if frame.message_start_index >= len(self.messages):
            return

        messages_to_compress = self.messages[
            frame.message_start_index : frame.message_end_index
        ]
        if not messages_to_compress:
            return

        summary_text = f'[Topic Summarized: {frame.topic}]\n{frame.conclusion}'
        summary_message = ChatMessage(role='system', content=summary_text)

        self.messages[frame.message_start_index : frame.message_end_index] = [
            summary_message
        ]

        if compaction_manager is None:
            return

        compactor = getattr(compaction_manager, 'compactor', None)
        if compactor is None or not hasattr(compactor, 'compact_chat_history'):
            return

        max_context_tokens = getattr(compaction_manager, 'max_context_tokens', 200000)
        token_budget = max(max_context_tokens // 4, 256)
        message_dicts = [
            {'role': message.role, 'content': message.content}
            for message in self.messages
        ]
        compacted_dicts = compactor.compact_chat_history(message_dicts, token_budget)
        self.messages = [
            ChatMessage(role=item['role'], content=item.get('content', ''))
            for item in compacted_dicts
            if isinstance(item, dict) and 'role' in item
        ]


class SessionStore:
    def __init__(self, root: str | Path = '.') -> None:
        self._dir = Path(root) / '.teaagent' / 'sessions'
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def dir(self) -> Path:
        return self._dir

    def save(self, session: ChatSession) -> None:
        session.updated_at = _utcnow()
        path = self._path(session.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    def load(self, session_id: str) -> Optional[ChatSession]:
        path = self._path(session_id)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return ChatSession.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def list_sessions(self) -> list[dict[str, Any]]:
        result = []
        for path in sorted(
            self._dir.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True
        ):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                result.append(
                    {
                        'id': data.get('id', path.stem),
                        'label': data.get('label', ''),
                        'message_count': len(data.get('messages', [])),
                        'created_at': data.get('created_at', ''),
                        'updated_at': data.get('updated_at', ''),
                    }
                )
            except (json.JSONDecodeError, KeyError):
                continue
        return result

    def delete(self, session_id: str) -> bool:
        path = self._path(session_id)
        if path.is_file():
            path.unlink()
            return True
        return False

    def _path(self, session_id: str) -> Path:
        # Prevent directory traversal attacks (RSK-11)
        if '..' in session_id or '/' in session_id or '\\' in session_id:
            raise ValueError('Invalid session_id: contains path traversal characters')
        # Allow only safe characters (alphanumeric, dash, underscore)
        safe_id = ''.join(c for c in session_id if c.isalnum() or c in '-_')
        if safe_id != session_id:
            raise ValueError('Invalid session_id: contains unsafe characters')
        return self._dir / f'{safe_id}.json'


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
