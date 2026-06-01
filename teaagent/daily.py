from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from teaagent.context import CompactionManager
from teaagent.context_pack import ContextPack
from teaagent.llm import estimate_cost_preflight
from teaagent.llm._config import PROVIDER_CONFIGS
from teaagent.memory import MemoryEntry
from teaagent.policy import PermissionMode
from teaagent.run_store import RunStore


@dataclass(frozen=True)
class ContextProfile:
    name: str
    memory_limit: int
    hydrate_lsp: bool
    search_graph: bool
    recent_run_replay: int
    output_reserve_tokens: int

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'memory_limit': self.memory_limit,
            'hydrate_lsp': self.hydrate_lsp,
            'search_graph': self.search_graph,
            'recent_run_replay': self.recent_run_replay,
            'output_reserve_tokens': self.output_reserve_tokens,
        }


CONTEXT_PROFILES: dict[str, ContextProfile] = {
    'lean': ContextProfile(
        name='lean',
        memory_limit=2,
        hydrate_lsp=False,
        search_graph=False,
        recent_run_replay=0,
        output_reserve_tokens=512,
    ),
    'balanced': ContextProfile(
        name='balanced',
        memory_limit=5,
        hydrate_lsp=True,
        search_graph=True,
        recent_run_replay=1,
        output_reserve_tokens=1024,
    ),
    'deep': ContextProfile(
        name='deep',
        memory_limit=10,
        hydrate_lsp=True,
        search_graph=True,
        recent_run_replay=3,
        output_reserve_tokens=2048,
    ),
}


@dataclass(frozen=True)
class TokenBudgetReport:
    provider: str
    model: Optional[str]
    profile: str
    estimated_input_tokens: int
    output_reserve_tokens: int
    estimated_total_tokens: int
    max_context_tokens: Optional[int]
    usage_ratio: Optional[float]
    usage_level: str
    estimated_cost_cents: float
    contributors: dict[str, int]
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'provider': self.provider,
            'model': self.model,
            'profile': self.profile,
            'estimated_input_tokens': self.estimated_input_tokens,
            'output_reserve_tokens': self.output_reserve_tokens,
            'estimated_total_tokens': self.estimated_total_tokens,
            'max_context_tokens': self.max_context_tokens,
            'usage_ratio': self.usage_ratio,
            'usage_level': self.usage_level,
            'estimated_cost_cents': self.estimated_cost_cents,
            'contributors': self.contributors,
            'recommendations': self.recommendations,
        }


@dataclass(frozen=True)
class HarnessHealthReport:
    healthy: bool
    failures: list[str]
    warnings: list[str]
    optional_indexes: dict[str, bool]
    docs_drift_check_available: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            'healthy': self.healthy,
            'failures': self.failures,
            'warnings': self.warnings,
            'optional_indexes': self.optional_indexes,
            'docs_drift_check_available': self.docs_drift_check_available,
        }


@dataclass(frozen=True)
class RunRollup:
    run_id: str
    task: str
    status: str
    updated_at: str
    pending_approval: Optional[dict[str, Any]] = None
    heartbeat: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'run_id': self.run_id,
            'task': self.task,
            'status': self.status,
            'updated_at': self.updated_at,
            'pending_approval': self.pending_approval,
            'heartbeat': self.heartbeat,
        }


@dataclass(frozen=True)
class DailyRecommendation:
    command: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {'command': self.command, 'reason': self.reason}


@dataclass(frozen=True)
class DailyBrief:
    task: Optional[str]
    provider: str
    model: Optional[str]
    permission_mode: str
    ready: bool
    context_profile: dict[str, Any]
    preflight: Optional[dict[str, Any]]
    token_budget: TokenBudgetReport
    harness_health: HarnessHealthReport
    recent_runs: list[RunRollup]
    recommendations: list[DailyRecommendation]

    def to_dict(self) -> dict[str, Any]:
        return {
            'task': self.task,
            'provider': self.provider,
            'model': self.model,
            'permission_mode': self.permission_mode,
            'ready': self.ready,
            'context_profile': self.context_profile,
            'preflight': self.preflight,
            'token_budget': self.token_budget.to_dict(),
            'harness_health': self.harness_health.to_dict(),
            'recent_runs': [run.to_dict() for run in self.recent_runs],
            'recommendations': [item.to_dict() for item in self.recommendations],
        }


def resolve_context_profile(
    name: str = 'balanced', *, memory_limit: Optional[int] = None
) -> ContextProfile:
    try:
        profile = CONTEXT_PROFILES[name]
    except KeyError as exc:
        raise ValueError(
            f"unknown context profile '{name}'. Expected one of: "
            f'{", ".join(sorted(CONTEXT_PROFILES))}'
        ) from exc
    if memory_limit is None:
        return profile
    return ContextProfile(
        name=profile.name,
        memory_limit=memory_limit,
        hydrate_lsp=profile.hydrate_lsp,
        search_graph=profile.search_graph,
        recent_run_replay=profile.recent_run_replay,
        output_reserve_tokens=profile.output_reserve_tokens,
    )


def build_token_budget_report(
    *,
    task: str,
    provider: str,
    model: Optional[str],
    context_pack: ContextPack,
    memories: list[MemoryEntry],
    tool_count: int,
    profile: ContextProfile,
    recent_runs: list[RunRollup] | None = None,
) -> TokenBudgetReport:
    selected_model = model or _default_model(provider)
    contributors = {
        'task': _estimate_tokens(task),
        'memories': _estimate_json_tokens([entry.to_dict() for entry in memories]),
        'context_pack': _estimate_json_tokens(context_pack.to_dict()),
        'tool_metadata': max(0, tool_count) * 80,
        'recent_run_replay': _estimate_json_tokens(
            [run.to_dict() for run in recent_runs or []]
        ),
        'expected_output_reserve': profile.output_reserve_tokens,
    }
    estimated_input = sum(
        value for key, value in contributors.items() if key != 'expected_output_reserve'
    )
    estimated_total = estimated_input + profile.output_reserve_tokens
    max_context = _model_context_limit(provider, selected_model)
    usage_ratio = round(estimated_total / max_context, 4) if max_context else None
    usage_level = (
        CompactionManager(max_context_tokens=max_context).get_usage_level(
            estimated_total
        )
        if max_context
        else 'unknown'
    )
    cost = estimate_cost_preflight(
        provider,
        selected_model or '',
        approx_input_chars=estimated_input * 4,
        max_output_tokens=profile.output_reserve_tokens,
    )
    return TokenBudgetReport(
        provider=provider,
        model=selected_model,
        profile=profile.name,
        estimated_input_tokens=estimated_input,
        output_reserve_tokens=profile.output_reserve_tokens,
        estimated_total_tokens=estimated_total,
        max_context_tokens=max_context,
        usage_ratio=usage_ratio,
        usage_level=usage_level,
        estimated_cost_cents=cost,
        contributors=contributors,
        recommendations=_token_recommendations(usage_level),
    )


def build_harness_health_report(
    root: str | Path,
    base_health: dict[str, Any],
    recent_runs: list[RunRollup] | None = None,
) -> HarnessHealthReport:
    root_path = Path(root).resolve()
    warnings: list[str] = list(base_health.get('warnings', []))
    if not (root_path / '.teaagent').exists():
        warnings.append('.teaagent directory is not initialized yet')
    dirty = _git_dirty_warning(root_path)
    if dirty:
        warnings.append(dirty)
    optional_indexes = {
        'hybrid_search': (root_path / '.teaagent' / 'hybrid_search.sqlite3').is_file(),
        'knowledge': (root_path / '.teaagent' / 'knowledge').exists(),
        'graphqlite': (root_path / '.teaagent' / 'graphqlite.db').is_file(),
    }
    if not any(optional_indexes.values()):
        warnings.append('no optional context indexes are available')
    pending = [run.run_id for run in recent_runs or [] if run.pending_approval]
    if pending:
        warnings.append(f'pending approvals in recent runs: {", ".join(pending)}')
    return HarnessHealthReport(
        healthy=bool(base_health.get('healthy', False)),
        failures=list(base_health.get('failures', [])),
        warnings=_dedupe(warnings),
        optional_indexes=optional_indexes,
        docs_drift_check_available=(
            root_path / 'scripts' / 'refresh_competitive_docs.py'
        ).is_file(),
    )


def build_daily_brief(
    *,
    task: Optional[str],
    root: str | Path,
    provider: str,
    model: Optional[str] = None,
    permission_mode: PermissionMode = PermissionMode.PROMPT,
    route: bool = False,
    memory_limit: Optional[int] = None,
    runs_limit: int = 5,
    context_profile: str = 'balanced',
    readonly: bool = False,
) -> DailyBrief:
    from teaagent.preflight import preflight

    profile = resolve_context_profile(context_profile, memory_limit=memory_limit)
    effective_task = task or 'daily readiness check'
    report = preflight(
        effective_task,
        root=root,
        provider=provider,
        model=model,
        permission_mode=permission_mode,
        route=route,
        memory_limit=profile.memory_limit,
        context_profile=profile.name,
        readonly=readonly,
    )
    store = RunStore(root, readonly=readonly)
    recent_runs = _recent_run_rollups(store, runs_limit)
    
    # Add corruption warnings to harness health if not already present
    run_health = store.health_report()
    if not run_health['healthy'] and 'corrupt_runs' not in harness_health.warnings:
        harness_health.warnings.append(
            f"Run store corruption: {run_health['corrupt_runs']} corrupt runs detected"
        )
    token_budget = build_token_budget_report(
        task=effective_task,
        provider=provider,
        model=report.model,
        context_pack=report.context_pack,
        memories=report.memories,
        tool_count=report.tool_count,
        profile=profile,
        recent_runs=recent_runs[: profile.recent_run_replay],
    )
    harness_health = build_harness_health_report(root, report.health, recent_runs)
    recommendations = _daily_recommendations(
        task=task,
        provider=provider,
        permission_mode=permission_mode,
        ready=report.to_dict()['ready'],
        token_budget=token_budget,
        harness_health=harness_health,
    )
    return DailyBrief(
        task=task,
        provider=provider,
        model=report.model,
        permission_mode=permission_mode.value,
        ready=report.to_dict()['ready'] and harness_health.healthy,
        context_profile=profile.to_dict(),
        preflight=report.to_dict(),
        token_budget=token_budget,
        harness_health=harness_health,
        recent_runs=recent_runs,
        recommendations=recommendations,
    )


def _recent_run_rollups(store: RunStore, limit: int) -> list[RunRollup]:
    rollups: list[RunRollup] = []
    for summary in store.list_runs(limit=max(0, limit)):
        pending = None
        heartbeat = None
        try:
            pending = store.pending_approval_for_run(summary.run_id)
            heartbeat = store.heartbeat_for_run(summary.run_id)
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            pass
        rollups.append(
            RunRollup(
                run_id=summary.run_id,
                task=summary.task,
                status=summary.status,
                updated_at=summary.updated_at,
                pending_approval=pending,
                heartbeat=heartbeat,
            )
        )
    return rollups


def _daily_recommendations(
    *,
    task: Optional[str],
    provider: str,
    permission_mode: PermissionMode,
    ready: bool,
    token_budget: TokenBudgetReport,
    harness_health: HarnessHealthReport,
) -> list[DailyRecommendation]:
    recommendations: list[DailyRecommendation] = []
    if not ready:
        recommendations.append(
            DailyRecommendation(
                command=f'teaagent agent preflight {provider} "{task or "task"}"',
                reason='Resolve readiness or clarification warnings before running.',
            )
        )
    elif task:
        recommendations.append(
            DailyRecommendation(
                command=(
                    f'teaagent agent run {provider} "{task}" '
                    f'--permission-mode {permission_mode.value}'
                ),
                reason='Run the checked task with the currently selected safety mode.',
            )
        )
    else:
        recommendations.append(
            DailyRecommendation(
                command=f'teaagent agent preflight {provider} "your task"',
                reason='Add a task to get a concrete context and token estimate.',
            )
        )
    if token_budget.usage_level in {'yellow', 'red'}:
        recommendations.append(
            DailyRecommendation(
                command=f'teaagent agent daily {provider} "{task or "task"}" --context-profile lean',
                reason='Use a lean profile to reduce context pressure.',
            )
        )
    if harness_health.failures:
        recommendations.append(
            DailyRecommendation(
                command='teaagent doctor project --root .',
                reason='Fix harness health failures before long-running work.',
            )
        )
    return recommendations


def _token_recommendations(usage_level: str) -> list[str]:
    if usage_level == 'red':
        return [
            'switch to lean context profile',
            'start with preflight or read-only mode',
        ]
    if usage_level == 'yellow':
        return ['consider lean context profile for long sessions']
    if usage_level == 'unknown':
        return ['model context window unknown; keep output reserve conservative']
    return []


def _default_model(provider: str) -> Optional[str]:
    config = PROVIDER_CONFIGS.get(provider)
    return config.default_model if config else None


def _model_context_limit(provider: str, model: Optional[str]) -> Optional[int]:
    name = (model or '').lower()
    if 'gemini-1.5' in name or 'gemini-2' in name:
        return 1_000_000
    if 'claude' in name:
        return 200_000
    if 'gpt-4o' in name or 'gpt-5' in name or 'openai/' in name:
        return 128_000
    if 'deepseek' in name:
        return 64_000
    if provider in {'gpt', 'openrouter', 'aigateway'}:
        return 128_000
    if provider == 'claude':
        return 200_000
    if provider == 'gemini':
        return 1_000_000
    if provider in {'deepseek', 'opencodezen', 'opencodezen-go'}:
        return 64_000
    return None


def _estimate_json_tokens(value: Any) -> int:
    return _estimate_tokens(json.dumps(value, sort_keys=True, default=str))


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def _git_dirty_warning(root: Path) -> Optional[str]:
    if not (root / '.git').exists():
        return None
    try:
        result = subprocess.run(
            ['git', 'status', '--short'],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return 'git status unavailable'
    if result.returncode != 0:
        return 'git status unavailable'
    count = len([line for line in result.stdout.splitlines() if line.strip()])
    return f'git worktree has {count} changed path(s)' if count else None


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped
