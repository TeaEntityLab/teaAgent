from __future__ import annotations

import contextlib
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from teaagent.intent import ClarificationResult, clarify_task
from teaagent.memory import MemoryCatalog, MemoryEntry
from teaagent.model_routing import ModelRoute, route_model
from teaagent.policy import PermissionMode
from teaagent.workspace_tools import build_workspace_tool_registry


@dataclass(frozen=True)
class PreflightReport:
    task: str
    provider: str
    model: Optional[str]
    permission_mode: PermissionMode
    clarification: ClarificationResult
    routing: Optional[ModelRoute]
    memories: list[MemoryEntry]
    tool_count: int
    health: dict[str, Any] = field(
        default_factory=lambda: {'healthy': True, 'failures': []}
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            'task': self.task,
            'provider': self.provider,
            'model': self.model,
            'permission_mode': self.permission_mode.value,
            'clarification': self.clarification.to_dict(),
            'routing': self.routing.to_dict() if self.routing else None,
            'memories': [entry.to_dict() for entry in self.memories],
            'tool_count': self.tool_count,
            'health': self.health,
            'ready': not self.clarification.needs_clarification
            and self.health['healthy'],
        }


def check_env_health(
    root: Path, critical_paths: list[Path] | None = None
) -> dict[str, Any]:
    """Check for common environment bottlenecks (permissions, network)."""
    failures = []

    # 1. Check writability of root and critical paths
    paths_to_check = [root] + (critical_paths or [])
    for p in paths_to_check:
        if p.exists():
            test_file = p / f'.teaagent_health_{socket.gethostname()}'
            try:
                test_file.write_text('health check', encoding='utf-8')
                test_file.unlink()
            except PermissionError:
                failures.append(f'Permission denied: Cannot write to {p}')
            except Exception as exc:
                failures.append(f'Disk error on {p}: {exc}')

    # 2. Check network binding ability (important for MCP/TUI)
    with contextlib.suppress(Exception):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(('127.0.0.1', 0))
        except socket.error as exc:
            failures.append(f'Network binding restricted: {exc}')
        finally:
            s.close()

    return {'healthy': len(failures) == 0, 'failures': failures}


def preflight(
    task: str,
    *,
    root: str | Path = '.',
    provider: str,
    model: Optional[str] = None,
    permission_mode: PermissionMode = PermissionMode.PROMPT,
    route: bool = False,
    memory_limit: int = 5,
) -> PreflightReport:
    root_path = Path(root)
    clarification = clarify_task(task)
    routing = route_model(task, provider=provider, model=model) if route else None
    memories = MemoryCatalog(root_path).search(task, limit=memory_limit)
    registry = build_workspace_tool_registry(root_path)

    health = check_env_health(
        root_path, critical_paths=[root_path / '.teaagent', root_path / '.git']
    )

    return PreflightReport(
        task=task,
        provider=provider,
        model=routing.model if routing else model,
        permission_mode=permission_mode,
        clarification=clarification,
        routing=routing,
        memories=memories,
        tool_count=len(registry.mcp_metadata()),
        health=health,
    )
