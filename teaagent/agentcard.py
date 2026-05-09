from __future__ import annotations

from dataclasses import dataclass, field
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
