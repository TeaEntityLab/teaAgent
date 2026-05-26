from __future__ import annotations

import contextlib
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from teaagent.context_pack import ContextPack, build_context_pack
from teaagent.daily import (
    TokenBudgetReport,
    build_harness_health_report,
    build_token_budget_report,
    resolve_context_profile,
)
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
    context_pack: ContextPack
    token_budget: Optional[TokenBudgetReport] = None
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
            'context_pack': self.context_pack.to_dict(),
            'token_budget': self.token_budget.to_dict() if self.token_budget else None,
            'health': self.health,
            'ready': not self.clarification.needs_clarification
            and self.health['healthy'],
        }


def check_env_health(
    root: Path, critical_paths: list[Path] | None = None, *, readonly: bool = False
) -> dict[str, Any]:
    """Check for common environment bottlenecks (permissions, network)."""
    failures = []

    # 1. Check writability of root and critical paths (skip in readonly mode)
    if not readonly:
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
    context_profile: str = 'balanced',
    readonly: bool = False,
) -> PreflightReport:
    root_path = Path(root)
    profile = resolve_context_profile(context_profile, memory_limit=memory_limit)
    clarification = clarify_task(task)
    routing = route_model(task, provider=provider, model=model) if route else None
    memories = MemoryCatalog(root_path, readonly=readonly).search(task, limit=profile.memory_limit)
    context_pack = build_context_pack(
        task,
        root=root_path,
        memory_limit=profile.memory_limit,
        hydrate_lsp=profile.hydrate_lsp,
        search_graph=profile.search_graph,
        readonly=readonly,
    )
    registry = build_workspace_tool_registry(root_path)

    health = check_env_health(
        root_path, critical_paths=[root_path / '.teaagent', root_path / '.git'], readonly=readonly
    )
    health['warnings'] = build_harness_health_report(root_path, health).warnings
    token_budget = build_token_budget_report(
        task=task,
        provider=provider,
        model=routing.model if routing else model,
        context_pack=context_pack,
        memories=memories,
        tool_count=len(registry.mcp_metadata()),
        profile=profile,
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
        context_pack=context_pack,
        token_budget=token_budget,
        health=health,
    )
