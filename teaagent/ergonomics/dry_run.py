from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from teaagent.daily import build_daily_brief, resolve_context_profile
from teaagent.policy import PermissionMode
from teaagent.preflight import preflight


def build_dry_run_payload(
    *,
    task: str,
    root: str | Path,
    provider: str,
    model: Optional[str] = None,
    permission_mode: PermissionMode = PermissionMode.PROMPT,
    route: bool = False,
    memory_limit: Optional[int] = None,
    context_profile: str = 'balanced',
    runs_limit: int = 5,
) -> dict[str, Any]:
    profile = resolve_context_profile(context_profile, memory_limit=memory_limit)
    report = preflight(
        task,
        root=root,
        provider=provider,
        model=model,
        permission_mode=permission_mode,
        route=route,
        memory_limit=profile.memory_limit,
        context_profile=profile.name,
    )
    brief = build_daily_brief(
        task=task,
        root=root,
        provider=provider,
        model=report.model,
        permission_mode=permission_mode,
        route=route,
        memory_limit=profile.memory_limit,
        runs_limit=runs_limit,
        context_profile=profile.name,
    )
    registry_tools = report.tool_count
    return {
        'dry_run': True,
        'task': task,
        'provider': provider,
        'model': report.model,
        'permission_mode': permission_mode.value,
        'preflight': report.to_dict(),
        'token_budget': brief.token_budget.to_dict(),
        'tool_count': registry_tools,
        'would_invoke_model': report.to_dict()['ready'],
        'recommendations': [item.to_dict() for item in brief.recommendations],
    }
