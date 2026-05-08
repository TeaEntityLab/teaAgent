from __future__ import annotations

from dataclasses import dataclass
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "provider": self.provider,
            "model": self.model,
            "permission_mode": self.permission_mode.value,
            "clarification": self.clarification.to_dict(),
            "routing": self.routing.to_dict() if self.routing else None,
            "memories": [entry.to_dict() for entry in self.memories],
            "tool_count": self.tool_count,
            "ready": not self.clarification.needs_clarification,
        }


def preflight(
    task: str,
    *,
    root: str | Path = ".",
    provider: str,
    model: Optional[str] = None,
    permission_mode: PermissionMode = PermissionMode.PROMPT,
    route: bool = False,
    memory_limit: int = 5,
) -> PreflightReport:
    clarification = clarify_task(task)
    routing = route_model(task, provider=provider, model=model) if route else None
    memories = MemoryCatalog(root).search(task, limit=memory_limit)
    registry = build_workspace_tool_registry(root)
    return PreflightReport(
        task=task,
        provider=provider,
        model=routing.model if routing else model,
        permission_mode=permission_mode,
        clarification=clarification,
        routing=routing,
        memories=memories,
        tool_count=len(registry.mcp_metadata()),
    )
