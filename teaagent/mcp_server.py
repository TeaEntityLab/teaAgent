from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, TextIO

from teaagent.errors import AgentHarnessError
from teaagent.resource_monitor import is_process_alive
from teaagent.storage import file_lock
from teaagent.tools import ToolRegistry

PROTOCOL_VERSION = '2024-11-05'
SERVER_INFO = {'name': 'teaagent', 'version': '0.1.0'}
REGISTRY_PATH = Path.home() / '.teaagent' / 'workspace_registry.json'


@dataclass
class WorkspaceLock:
    """Represents a workspace lock with owner PID."""

    workspace_path: str
    owner_pid: int
    acquired_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'workspace_path': self.workspace_path,
            'owner_pid': self.owner_pid,
            'acquired_at': self.acquired_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'WorkspaceLock':
        return cls(
            workspace_path=data.get('workspace_path', ''),
            owner_pid=data.get('owner_pid', 0),
            acquired_at=data.get('acquired_at', ''),
        )


class WorkspaceRegistry:
    """Thread-safe workspace registry with file_lock protection."""

    def __init__(self, registry_path: Path = REGISTRY_PATH) -> None:
        self.registry_path = registry_path
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

    def acquire_lock(self, workspace_path: str) -> WorkspaceLock:
        """Acquire a lock for a workspace with automatic zombie cleanup.

        Args:
            workspace_path: Path to the workspace directory.

        Returns:
            WorkspaceLock instance.
        """
        current_pid = os.getpid()
        import datetime

        lock = WorkspaceLock(
            workspace_path=workspace_path,
            owner_pid=current_pid,
            acquired_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

        with file_lock(self.registry_path):
            existing = self._load_registry()
            existing_locks = [
                WorkspaceLock.from_dict(lock_data)
                for lock_data in existing.get('locks', [])
            ]

            active_locks = []
            for existing_lock in existing_locks:
                if existing_lock.workspace_path == workspace_path:
                    if is_process_alive(existing_lock.owner_pid):
                        raise RuntimeError(
                            f'Workspace {workspace_path} is locked by PID {existing_lock.owner_pid}'
                        )
                else:
                    if is_process_alive(existing_lock.owner_pid):
                        active_locks.append(existing_lock)

            active_locks.append(lock)
            self._save_registry(
                {'locks': [lock_item.to_dict() for lock_item in active_locks]}
            )

        return lock

    def release_lock(self, workspace_path: str) -> None:
        """Release lock for a workspace.

        Args:
            workspace_path: Path to the workspace directory.
        """
        with file_lock(self.registry_path):
            existing = self._load_registry()
            existing_locks = [
                WorkspaceLock.from_dict(lock_data)
                for lock_data in existing.get('locks', [])
            ]

            active_locks = [
                lock_item
                for lock_item in existing_locks
                if lock_item.workspace_path != workspace_path
            ]

            self._save_registry(
                {'locks': [lock_item.to_dict() for lock_item in active_locks]}
            )

    def _load_registry(self) -> dict[str, Any]:
        if not self.registry_path.exists():
            return {'locks': []}
        try:
            return json.loads(self.registry_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, IOError):
            return {'locks': []}

    def _save_registry(self, data: dict[str, Any]) -> None:
        self.registry_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
        )


def handle_mcp_request(
    registry: ToolRegistry, request: dict[str, Any]
) -> Optional[dict[str, Any]]:
    request_id = request.get('id')
    method = request.get('method')
    params = request.get('params') or {}

    if request_id is None:
        return None

    if method == 'initialize':
        return _ok(
            request_id,
            {
                'protocolVersion': PROTOCOL_VERSION,
                'capabilities': {'tools': {}},
                'serverInfo': SERVER_INFO,
            },
        )
    if method == 'tools/list':
        return _ok(request_id, {'tools': _tools_payload(registry)})
    if method == 'tools/call':
        return _call_tool(registry, request_id, params)
    return _error(request_id, -32601, f"method '{method}' not found")


def serve_mcp_stdio(
    registry: ToolRegistry,
    *,
    stdin: Optional[TextIO] = None,
    stdout: Optional[TextIO] = None,
) -> int:
    reader = stdin or sys.stdin
    writer = stdout or sys.stdout
    for line in _iter_jsonl_lines(reader):
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle_mcp_request(registry, request)
        if response is not None:
            writer.write(json.dumps(response, ensure_ascii=False) + '\n')
            writer.flush()
    return 0


def _iter_jsonl_lines(reader: TextIO) -> Iterable[str]:
    for raw in reader:
        line = raw.strip()
        if line:
            yield line


def _tools_payload(registry: ToolRegistry) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for tool in registry.mcp_metadata():
        payload.append(
            {
                'name': tool['name'],
                'description': tool['description'],
                'inputSchema': tool['input_schema'],
                'annotations': tool['annotations'],
            }
        )
    return payload


def _call_tool(
    registry: ToolRegistry, request_id: Any, params: dict[str, Any]
) -> dict[str, Any]:
    name = params.get('name')
    arguments = params.get('arguments') or {}
    if not isinstance(name, str):
        return _error(request_id, -32602, "tools/call requires string 'name'")
    if not isinstance(arguments, dict):
        return _error(request_id, -32602, "tools/call requires object 'arguments'")
    try:
        result = registry.execute(name, arguments)
    except AgentHarnessError as exc:
        return _ok(
            request_id,
            {
                'content': [{'type': 'text', 'text': str(exc)}],
                'isError': True,
            },
        )
    return _ok(
        request_id,
        {
            'content': [
                {
                    'type': 'text',
                    'text': json.dumps(result, ensure_ascii=False, sort_keys=True),
                }
            ],
            'isError': False,
        },
    )


def _ok(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {'jsonrpc': '2.0', 'id': request_id, 'result': result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        'jsonrpc': '2.0',
        'id': request_id,
        'error': {'code': code, 'message': message},
    }
