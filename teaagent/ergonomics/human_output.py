from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ReadinessLevel = Literal['blocking', 'warning', 'info']

# ANSI color codes (emoji-free)
_STYLE_RESET = '\033[0m'
_STYLE_BOLD = '\033[1m'
_STYLE_DIM = '\033[2m'
_COLOR_RED = '\033[31m'
_COLOR_GREEN = '\033[32m'
_COLOR_YELLOW = '\033[33m'
_COLOR_CYAN = '\033[36m'
_COLOR_MAGENTA = '\033[35m'


def _label(text: str, color: str) -> str:
    return f'{color}{_STYLE_BOLD}{text}{_STYLE_RESET}'


def _cmd(text: str) -> str:
    return f'{_COLOR_CYAN}{text}{_STYLE_RESET}'


@dataclass(frozen=True)
class ReadinessItem:
    level: ReadinessLevel
    message: str
    next_command: str | None = None


def _preflight_section(payload: dict[str, Any]) -> dict[str, Any]:
    preflight = payload.get('preflight')
    return preflight if isinstance(preflight, dict) else {}


def _health_section(payload: dict[str, Any]) -> dict[str, Any]:
    preflight = _preflight_section(payload)
    health = preflight.get('health')
    if isinstance(health, dict):
        return health
    harness = payload.get('harness_health')
    return harness if isinstance(harness, dict) else {}


def _remediation_for_failure(message: str, *, root: str) -> str | None:
    lowered = message.lower()
    if 'permission denied' in lowered or 'cannot write' in lowered:
        if '.git' in lowered:
            return (
                'Git metadata is not writable here (common in sandboxes). '
                f'Try: teaagent daily "readiness" --dry-run --root {root!r} in a temp dir.'
            )
        return 'Fix workspace permissions or use a writable --root (e.g. a temp directory).'
    if 'network binding' in lowered:
        return (
            'Local MCP/TUI bind may be restricted; read-only agent tasks can still run. '
            'For MCP: teaagent doctor mcp --wizard --root .'
        )
    if 'not initialized' in lowered or '.teaagent' in lowered:
        return 'teaagent setup --root . --provider gpt --permission-mode read-only'
    return None


def build_readiness_items(
    payload: dict[str, Any], *, root: str = '.'
) -> list[ReadinessItem]:
    items: list[ReadinessItem] = []
    preflight = _preflight_section(payload)
    health = _health_section(payload)
    root_display = str(Path(root).resolve())

    for failure in health.get('failures', []) or []:
        if not isinstance(failure, str):
            continue
        items.append(
            ReadinessItem(
                level='blocking',
                message=failure,
                next_command=_remediation_for_failure(failure, root=root_display),
            )
        )

    clarification = preflight.get('clarification')
    if isinstance(clarification, dict) and clarification.get('needs_clarification'):
        items.append(
            ReadinessItem(
                level='warning',
                message='Task needs more detail before a safe run.',
                next_command='teaagent clarify "<your task>"',
            )
        )

    harness = payload.get('harness_health')
    warning_sources: list[str] = []
    if isinstance(harness, dict):
        warning_sources.extend(
            w for w in harness.get('warnings', []) if isinstance(w, str)
        )
    warning_sources.extend(w for w in health.get('warnings', []) if isinstance(w, str))
    seen: set[str] = set()
    for warning in warning_sources:
        if warning in seen:
            continue
        seen.add(warning)
        level: ReadinessLevel = 'warning'
        next_cmd: str | None = None
        if 'not initialized' in warning.lower():
            level = 'blocking'
            next_cmd = (
                f'teaagent setup --root {root_display} --permission-mode read-only'
            )
        elif 'no optional context indexes' in warning.lower():
            level = 'info'
            next_cmd = 'Optional: add memory or GraphQLite indexes (see docs/USAGE.md#setup-model).'
        elif 'pending approvals' in warning.lower():
            next_cmd = (
                'teaagent approval list && teaagent agent attach <run_id> --resume'
            )
        items.append(ReadinessItem(level=level, message=warning, next_command=next_cmd))

    token_budget = payload.get('token_budget')
    if isinstance(token_budget, dict):
        usage = token_budget.get('usage_level')
        if usage in {'high', 'critical'}:
            items.append(
                ReadinessItem(
                    level='warning',
                    message=f'Token budget pressure: {usage}.',
                    next_command='teaagent daily "task" --context-profile lean --dry-run',
                )
            )

    if payload.get('dry_run'):
        items.append(
            ReadinessItem(
                level='info',
                message='Dry-run only — no model call or run record was created.',
                next_command=None,
            )
        )

    ready = payload.get('ready')
    if ready is None:
        ready = preflight.get('ready') or payload.get('would_invoke_model')
    if ready is False and not any(i.level == 'blocking' for i in items):
        items.append(
            ReadinessItem(
                level='blocking',
                message='Workspace is not ready for this task yet.',
                next_command=f'teaagent agent preflight {payload.get("provider", "gpt")} "<task>"',
            )
        )

    return items


def format_readiness_summary(
    payload: dict[str, Any], *, root: str = '.', title: str = 'TeaAgent readiness'
) -> str:
    items = build_readiness_items(payload, root=root)
    preflight = _preflight_section(payload)
    provider = payload.get('provider') or preflight.get('provider') or 'gpt'
    ready = payload.get(
        'ready', preflight.get('ready', payload.get('would_invoke_model'))
    )
    lines = [
        title,
        f'  Provider: {provider}',
        f'  Ready: {"yes" if ready else "no"}',
    ]
    if payload.get('dry_run'):
        lines.append('  Mode: dry-run (inspect only)')
    token_budget = payload.get('token_budget')
    if isinstance(token_budget, dict) and token_budget.get('usage_level'):
        lines.append(f'  Token budget: {token_budget["usage_level"]}')

    if not items:
        lines.append('  No issues reported.')
        lines.append('  Next: teaagent run "<task>" --permission-mode read-only')
        return '\n'.join(lines)

    for level in ('blocking', 'warning', 'info'):
        level_items = [i for i in items if i.level == level]
        if not level_items:
            continue
        lines.append(f'  {level.capitalize()}:')
        for item in level_items:
            lines.append(f'    - {item.message}')
            if item.next_command:
                lines.append(f'      → {item.next_command}')

    recommendations = payload.get('recommendations')
    if isinstance(recommendations, list) and recommendations:
        first = recommendations[0]
        if isinstance(first, dict) and first.get('command'):
            lines.append(f'  Suggested: {first["command"]}')
    elif ready:
        task = payload.get('task') or 'summarize this repo'
        lines.append(
            f'  Next: teaagent run "{task}" --permission-mode read-only --root {root}'
        )
    return '\n'.join(lines)


def format_setup_summary(payload: dict[str, Any], *, root: str = '.') -> str:
    ok = bool(payload.get('ok'))
    status_text = 'OK' if ok else 'NEEDS ATTENTION'
    status_color = _COLOR_GREEN if ok else _COLOR_RED
    lines = [
        f'TeaAgent Setup  [{_label(status_text, status_color)}]',
        f'  Root: {payload.get("root", root)}',
    ]
    configured = payload.get('configured')
    if isinstance(configured, dict):
        if configured.get('provider'):
            lines.append(f'  Provider: {configured["provider"]}')
        if configured.get('permission_mode'):
            lines.append(f'  Permission mode: {configured["permission_mode"]}')
            lines.append('')

    # --- Blocking items ---
    warnings = payload.get('warnings') or []
    checks = payload.get('checks') or {}
    blocking_items: list[str] = []
    for check_name, check_value in checks.items():
        if isinstance(check_value, dict) and check_value.get('ok') is False:
            msg = check_value.get('message', '')
            if msg:
                blocking_items.append(
                    f'    {_label("FAIL", _COLOR_RED)} {check_name}: {msg}'
                )

    for warning in warnings:
        lowered = warning.lower()
        if any(
            kw in lowered for kw in ('fail', 'error', 'missing', 'not found', 'denied')
        ):
            blocking_items.append(f'    {_label("FAIL", _COLOR_RED)} {warning}')

    if blocking_items:
        lines.append(f'  {_label("Blocking", _COLOR_RED)}:')
        lines.extend(blocking_items)
        for item in blocking_items:
            if 'provider' in item.lower():
                lines.append(f'           {_cmd("teaagent doctor model <provider>")}')
            if 'key' in item.lower() or 'api_key' in item.lower():
                lines.append(
                    f'           {_cmd("teaagent setup --provider <name> --api-key <key>")}'
                )
        lines.append('')

    # --- Warnings ---
    warning_items = [
        w
        for w in warnings
        if not any(
            kw in w.lower()
            for kw in ('fail', 'error', 'missing', 'not found', 'denied')
        )
    ]
    if warning_items:
        lines.append(f'  {_label("Warnings", _COLOR_YELLOW)}:')
        for w in warning_items[:5]:
            lines.append(f'    - {w}')
        lines.append('')

    # --- Next steps ---
    safe = payload.get('safe_command')
    if safe:
        lines.append(f'  {_label("Next", _COLOR_GREEN)}: {_cmd(safe)}')
    next_steps = payload.get('next_steps') or []
    if next_steps:
        for i, step in enumerate(next_steps[:5], 1):
            if isinstance(step, str):
                lines.append(f'    {i}. {_cmd(step)}')
        lines.append('')

    # --- Files written ---
    files_written = payload.get('files_written') or []
    if files_written:
        lines.append(f'  {_label("Files written", _STYLE_DIM)}:')
        for f in files_written[:5]:
            lines.append(f'    - {f}')

    return '\n'.join(lines)


def format_preflight_summary(payload: dict[str, Any], *, root: str = '.') -> str:
    """Format preflight readiness payload as a human-readable colored summary."""
    preflight = payload.get('preflight') or payload
    ready = bool(
        payload.get('ready')
        or preflight.get('ready')
        or payload.get('would_invoke_model')
    )
    status_text = 'READY' if ready else 'BLOCKED'
    status_color = _COLOR_GREEN if ready else _COLOR_RED
    provider = payload.get('provider') or preflight.get('provider') or 'gpt'
    lines = [
        f'Preflight  [{_label(status_text, status_color)}]',
        f'  Provider: {provider}',
    ]

    if payload.get('dry_run'):
        lines.append('  Mode: dry-run (inspect only, no model call)')

    # --- Token budget ---
    token_budget = preflight.get('token_budget') or payload.get('token_budget')
    if isinstance(token_budget, dict) and token_budget.get('usage_level'):
        usage = token_budget['usage_level']
        usage_color = (
            _COLOR_GREEN
            if usage == 'low'
            else (_COLOR_YELLOW if usage == 'medium' else _COLOR_RED)
        )
        lines.append(f'  Token budget: {_label(usage, usage_color)}')

    # --- Tasks requiring clarification ---
    clarification = preflight.get('clarification')
    if isinstance(clarification, dict) and clarification.get('needs_clarification'):
        lines.append('')
        lines.append(f'  {_label("Needs clarification", _COLOR_YELLOW)}:')
        msg = clarification.get('message', '')
        if msg:
            lines.append(f'    {msg}')
        clarify_cmd = "teaagent clarify '<your task>'"
        lines.append(f'    -> {_cmd(clarify_cmd)}')

    # --- Health failures ---
    health = preflight.get('health') or payload.get('harness_health') or {}
    failures = health.get('failures') or []
    if failures:
        lines.append('')
        lines.append(f'  {_label("Blocking", _COLOR_RED)}:')
        for failure in failures:
            lines.append(f'    - {failure}')
            remediation = _remediation_for_failure(failure, root=root)
            if remediation:
                lines.append(f'      -> {_cmd(remediation)}')

    # --- Warnings ---
    warnings = health.get('warnings') or payload.get('warnings') or []
    if warnings:
        lines.append('')
        lines.append(f'  {_label("Warnings", _COLOR_YELLOW)}:')
        for warning in warnings[:5]:
            lines.append(f'    - {warning}')

    # --- Recommendations ---
    recommendations = (
        payload.get('recommendations') or preflight.get('recommendations') or []
    )
    if recommendations:
        lines.append('')
        lines.append(f'  {_label("Recommendations", _COLOR_GREEN)}:')
        for rec in recommendations[:3]:
            if isinstance(rec, dict):
                cmd = rec.get('command', '')
                reason = rec.get('reason', '')
                if cmd:
                    lines.append(f'    {_cmd(cmd)}')
                if reason:
                    lines.append(f'    ({reason})')
            elif isinstance(rec, str):
                lines.append(f'    {rec}')

    # --- Next command ---
    if ready and not recommendations:
        lines.append('')
        next_cmd = 'teaagent run "<task>" --permission-mode read-only'
        lines.append(f'  {_label("Next", _COLOR_GREEN)}: {_cmd(next_cmd)}')

    return '\n'.join(lines)


def format_ascii_table(
    headers: list[str], rows: list[dict[str, Any]], keys: list[str]
) -> str:
    """Format a list of records into a beautifully aligned ASCII table."""
    if not rows:
        return '(no records)'

    # Calculate column widths
    widths = {key: len(header) for key, header in zip(keys, headers, strict=True)}
    for row in rows:
        for key in keys:
            val = str(row.get(key, '') or '')
            widths[key] = max(widths[key], len(val))

    # Form separator and header lines
    sep = '+' + '+'.join('-' * (widths[key] + 2) for key in keys) + '+'
    header_line = (
        '|'
        + '|'.join(
            f' {header:<{widths[key]}} '
            for key, header in zip(keys, headers, strict=True)
        )
        + '|'
    )

    lines = [sep, header_line, sep]
    for row in rows:
        row_line = (
            '|'
            + '|'.join(
                f' {str(row.get(key, "") or ""):<{widths[key]}} ' for key in keys
            )
            + '|'
        )
        lines.append(row_line)
    lines.append(sep)
    return '\n'.join(lines)
