from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


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

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'messages': [m.to_dict() for m in self.messages],
            'label': self.label,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ChatSession':
        return cls(
            id=data.get('id', ''),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            messages=[ChatMessage.from_dict(m) for m in data.get('messages', [])],
            label=data.get('label', ''),
        )


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
        return self._dir / f'{session_id}.json'


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
