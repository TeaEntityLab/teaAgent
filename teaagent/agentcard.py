from __future__ import annotations

import http.server
import json
import sqlite3
import threading
import time as _time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Per-endpoint circuit-breaker parameters for :class:`FederatedAgentRegistry`.

    After *failure_threshold* consecutive failures the circuit opens and the
    endpoint is skipped on subsequent refreshes.  Once *reset_timeout_seconds*
    have elapsed the circuit moves to half-open and the next refresh retries
    the endpoint; a success closes the circuit, another failure re-opens it.
    """

    failure_threshold: int = 3
    reset_timeout_seconds: float = 60.0


@dataclass
class _EndpointCircuit:
    failures: int = 0
    opened_at: Optional[float] = None  # monotonic timestamp when circuit opened

    def is_open(self, reset_timeout: float) -> bool:
        if self.opened_at is None:
            return False
        return (_time.monotonic() - self.opened_at) < reset_timeout

    def record_failure(self, threshold: int) -> None:
        self.failures += 1
        if self.failures >= threshold:
            self.opened_at = _time.monotonic()

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None


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


def _make_a2a_handler(
    card_data: dict[str, Any],
    task_handler: Optional[Callable[[str, dict[str, Any]], str]],
) -> type:
    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == '/.well-known/agent.json':
                body = json.dumps(card_data).encode('utf-8')
                self.send_response(200)
                self.send_header('Connection', 'close')
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.send_header('Connection', 'close')
                self.end_headers()

        def do_POST(self) -> None:
            if self.path == '/a2a/task' and task_handler is not None:
                length = int(self.headers.get('Content-Length', '0'))
                body = self.rfile.read(length)
                try:
                    req_data = json.loads(body.decode('utf-8'))
                    output = task_handler(
                        req_data.get('task', ''), req_data.get('context') or {}
                    )
                    resp_body = json.dumps(
                        {'agent_name': card_data.get('name', ''), 'output': output}
                    ).encode('utf-8')
                    self.send_response(200)
                    self.send_header('Connection', 'close')
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(resp_body)))
                    self.end_headers()
                    self.wfile.write(resp_body)
                except Exception as exc:
                    resp_body = json.dumps({'error': str(exc)}).encode('utf-8')
                    self.send_response(500)
                    self.send_header('Connection', 'close')
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(resp_body)))
                    self.end_headers()
                    self.wfile.write(resp_body)
            else:
                self.send_response(404)
                self.send_header('Connection', 'close')
                self.end_headers()

        def log_message(self, *_: object) -> None:
            pass

    return _Handler


class A2ADiscoveryServer:
    """Serves an AgentCard at ``/.well-known/agent.json`` over HTTP.

    Optionally handles POST ``/a2a/task`` for in-process task delegation when
    *task_handler* is provided.  Use ``port=0`` to let the OS pick a free port
    (useful in tests).
    """

    WELL_KNOWN_PATH = '/.well-known/agent.json'
    TASK_PATH = '/a2a/task'

    def __init__(
        self,
        card: AgentCard,
        *,
        host: str = '127.0.0.1',
        port: int = 0,
        task_handler: Optional[Callable[[str, dict[str, Any]], str]] = None,
    ) -> None:
        self._card = card
        self._host = host
        self._port = port
        self._task_handler = task_handler
        self._server: Optional[http.server.HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def port(self) -> int:
        if self._server is not None:
            return self._server.server_address[1]
        return self._port

    @property
    def base_url(self) -> str:
        return f'http://{self._host}:{self.port}'

    def start(self) -> None:
        card_data = self._card.to_dict()
        handler_cls = _make_a2a_handler(card_data, self._task_handler)
        self._server = http.server.HTTPServer((self._host, self._port), handler_cls)
        if not card_data.get('endpoint'):
            card_data['endpoint'] = self.base_url
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server = None

    def __enter__(self) -> 'A2ADiscoveryServer':
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()


class A2AClient:
    """HTTP client for A2A task delegation and card discovery."""

    def __init__(self, endpoint: str, *, timeout: int = 30) -> None:
        self._endpoint = endpoint.rstrip('/')
        self._timeout = timeout

    @classmethod
    def from_card(cls, card: AgentCard, *, timeout: int = 30) -> 'A2AClient':
        if not card.endpoint:
            raise ValueError(f'AgentCard {card.name!r} has no endpoint')
        return cls(card.endpoint, timeout=timeout)

    def fetch_card(self) -> AgentCard:
        url = f'{self._endpoint}/.well-known/agent.json'
        with urllib.request.urlopen(url, timeout=self._timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return AgentCard.from_dict(data)

    def delegate(
        self,
        task: str,
        *,
        context: Optional[dict[str, Any]] = None,
    ) -> A2ATaskResult:
        payload = json.dumps({'task': task, 'context': context or {}}).encode('utf-8')
        req = urllib.request.Request(
            f'{self._endpoint}/a2a/task',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            result_data = json.loads(resp.read().decode('utf-8'))
        agent_name = result_data.get('agent_name') or ''
        return A2ATaskResult(
            task=task,
            agent_name=agent_name,
            output=result_data.get('output', ''),
        )


class FederatedAgentRegistry:
    """Pulls AgentCards from remote ``/.well-known/agent.json`` endpoints.

    Cards are cached for *ttl_seconds* (default 300).  The cache is
    refreshed lazily on first access and whenever it becomes stale.
    ``refresh()`` can also be called manually and returns a list of
    per-endpoint error strings for diagnostic purposes.
    """

    def __init__(
        self,
        endpoints: list[str],
        *,
        ttl_seconds: int = 300,
        timeout: int = 10,
        circuit_breaker: Optional[CircuitBreakerConfig] = None,
    ) -> None:
        self._endpoints = list(endpoints)
        self._ttl = ttl_seconds
        self._timeout = timeout
        self._cache: list[AgentCard] = []
        self._fetched_at: float = 0.0
        self._cb_config = circuit_breaker
        self._circuits: dict[str, _EndpointCircuit] = {}

    def _is_stale(self) -> bool:
        return _time.monotonic() - self._fetched_at > self._ttl

    def refresh(self) -> list[str]:
        errors: list[str] = []
        cards: list[AgentCard] = []
        for base_url in self._endpoints:
            circuit = self._circuits.setdefault(base_url, _EndpointCircuit())
            if self._cb_config is not None and circuit.is_open(
                self._cb_config.reset_timeout_seconds
            ):
                continue  # circuit open — skip this endpoint
            url = base_url.rstrip('/') + '/.well-known/agent.json'
            try:
                with urllib.request.urlopen(url, timeout=self._timeout) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                cards.append(AgentCard.from_dict(data))
                circuit.record_success()
            except Exception as exc:
                errors.append(f'{base_url}: {exc}')
                if self._cb_config is not None:
                    circuit.record_failure(self._cb_config.failure_threshold)
        self._cache = cards
        self._fetched_at = _time.monotonic()
        return errors

    def circuit_state(self, base_url: str) -> str:
        """Return ``'open'`` or ``'closed'`` for the given endpoint."""
        circuit = self._circuits.get(base_url)
        if circuit is None:
            return 'closed'
        if self._cb_config is None:
            return 'closed'
        return (
            'open'
            if circuit.is_open(self._cb_config.reset_timeout_seconds)
            else 'closed'
        )

    def _ensure_fresh(self) -> None:
        if self._is_stale():
            self.refresh()

    def get(self, name: str) -> Optional[AgentCard]:
        self._ensure_fresh()
        for card in self._cache:
            if card.name == name:
                return card
        return None

    def list_cards(self) -> list[AgentCard]:
        self._ensure_fresh()
        return list(self._cache)

    def find_by_capability(self, capability: str) -> list[AgentCard]:
        return [c for c in self.list_cards() if capability in c.capabilities]

    def find_by_tool(self, tool_name: str) -> list[AgentCard]:
        return [c for c in self.list_cards() if tool_name in c.tools]
