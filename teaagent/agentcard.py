from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class AgentCard:
    name: str
    version: str
    description: str
    capabilities: frozenset[str]
    tools: tuple[str, ...]
    endpoint: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'capabilities': sorted(self.capabilities),
            'tools': list(self.tools),
            'endpoint': self.endpoint,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'AgentCard':
        return cls(
            name=str(data['name']),
            version=str(data.get('version', '0.0.0')),
            description=str(data.get('description', '')),
            capabilities=frozenset(data.get('capabilities', [])),
            tools=tuple(data.get('tools', [])),
            endpoint=data.get('endpoint') or None,
            metadata=dict(data.get('metadata') or {}),
        )


class InMemoryAgentRegistry:
    def __init__(self) -> None:
        self._cards: dict[str, AgentCard] = {}

    def register(self, card: AgentCard) -> None:
        self._cards[card.name] = card

    def deregister(self, name: str) -> None:
        self._cards.pop(name, None)

    def get(self, name: str) -> Optional[AgentCard]:
        return self._cards.get(name)

    def list_cards(self) -> list[AgentCard]:
        return list(self._cards.values())

    def find_by_capability(self, capability: str) -> list[AgentCard]:
        return [
            card for card in self._cards.values() if capability in card.capabilities
        ]

    def find_by_tool(self, tool_name: str) -> list[AgentCard]:
        return [card for card in self._cards.values() if tool_name in card.tools]


_STANDARD_CAPABILITIES = frozenset(
    ['tool_execution', 'audit_logging', 'budget_enforcement']
)


def build_self_card(
    name: str,
    version: str,
    registry: Any,
    *,
    endpoint: Optional[str] = None,
    extra_capabilities: frozenset[str] = frozenset(),
    metadata: Optional[dict[str, Any]] = None,
) -> AgentCard:
    tools = tuple(entry['name'] for entry in registry.mcp_metadata())
    return AgentCard(
        name=name,
        version=version,
        description=f'{name} v{version} — {len(tools)} tool(s) registered',
        capabilities=_STANDARD_CAPABILITIES | extra_capabilities,
        tools=tools,
        endpoint=endpoint,
        metadata=metadata or {},
    )


class SQLiteAgentRegistry:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path), timeout=10)
        conn.execute('PRAGMA journal_mode=WAL')
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_cards (
                    name TEXT PRIMARY KEY,
                    card_json TEXT NOT NULL,
                    registered_at TEXT NOT NULL
                )
                """
            )

    def register(self, card: AgentCard) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_cards (name, card_json, registered_at)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    card_json = excluded.card_json,
                    registered_at = excluded.registered_at
                """,
                (card.name, json.dumps(card.to_dict(), ensure_ascii=False), now),
            )

    def deregister(self, name: str) -> None:
        with self._connect() as conn:
            conn.execute('DELETE FROM agent_cards WHERE name = ?', (name,))

    def get(self, name: str) -> Optional[AgentCard]:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT card_json FROM agent_cards WHERE name = ?', (name,)
            ).fetchone()
        if row is None:
            return None
        return AgentCard.from_dict(json.loads(row[0]))

    def list_cards(self) -> list[AgentCard]:
        with self._connect() as conn:
            rows = conn.execute('SELECT card_json FROM agent_cards').fetchall()
        return [AgentCard.from_dict(json.loads(r[0])) for r in rows]

    def find_by_capability(self, capability: str) -> list[AgentCard]:
        return [c for c in self.list_cards() if capability in c.capabilities]

    def find_by_tool(self, tool_name: str) -> list[AgentCard]:
        return [c for c in self.list_cards() if tool_name in c.tools]


@dataclass(frozen=True)
class A2ATaskResult:
    task: str
    agent_name: str
    output: str
    routed_by_capability: Optional[str] = None


class A2ADispatcher:
    def __init__(self, registry: Any) -> None:
        self._registry = registry

    def dispatch_by_capability(
        self,
        task: str,
        capability: str,
        *,
        runner: Any,
    ) -> A2ATaskResult:
        candidates = self._registry.find_by_capability(capability)
        if not candidates:
            raise LookupError(f'No registered agent has capability {capability!r}')
        card = candidates[0]
        output = runner(task, card)
        return A2ATaskResult(
            task=task,
            agent_name=card.name,
            output=output,
            routed_by_capability=capability,
        )

    def dispatch_by_name(
        self,
        task: str,
        agent_name: str,
        *,
        runner: Any,
    ) -> A2ATaskResult:
        card = self._registry.get(agent_name)
        if card is None:
            raise LookupError(f'No registered agent named {agent_name!r}')
        output = runner(task, card)
        return A2ATaskResult(task=task, agent_name=card.name, output=output)
