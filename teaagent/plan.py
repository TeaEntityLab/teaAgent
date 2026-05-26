"""Plan artifact helpers for read-only planning workflows."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from teaagent.preflight import PreflightReport
from teaagent.storage import atomic_write_text

_PLAN_TASK_LINE = re.compile(r'^-\s+\*\*Task:\*\*\s*(.+)\s*$', re.MULTILINE)


@dataclass(frozen=True)
class PlanContract:
    """Parsed plan artifact used to bind execution runs to reviewed plans."""

    path: Path
    rel_path: str
    content_hash: str
    task: str

    def to_dict(self) -> dict[str, str]:
        return {
            'path': str(self.path),
            'rel_path': self.rel_path,
            'content_hash': self.content_hash,
            'task': self.task,
        }


def plan_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def load_plan_contract(
    plan_path: str | Path, *, root: str | Path = '.'
) -> PlanContract:
    workspace = Path(root).resolve()
    path = Path(plan_path)
    if not path.is_absolute():
        path = (workspace / path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f'plan artifact not found: {plan_path}')
    content = path.read_text(encoding='utf-8')
    match = _PLAN_TASK_LINE.search(content)
    if not match:
        raise ValueError('plan artifact missing **Task:** line in Summary section')
    task = match.group(1).strip()
    try:
        rel_path = path.relative_to(workspace).as_posix()
    except ValueError:
        rel_path = path.as_posix()
    return PlanContract(
        path=path,
        rel_path=rel_path,
        content_hash=plan_content_hash(content),
        task=task,
    )


def _slugify(text: str, *, max_len: int = 48) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    if not slug:
        return 'plan'
    return slug[:max_len].strip('-') or 'plan'


def _bullet_lines(items: list[str], *, empty: str) -> list[str]:
    if not items:
        return [f'- {empty}']
    return [f'- {item}' for item in items]


def _plan_assumptions(report: PreflightReport) -> list[str]:
    clarification = report.clarification
    assumptions = [
        'Planning is read-only; no workspace writes occur in this step.',
        f'Provider `{report.provider}` and permission mode `{report.permission_mode.value}` apply to the follow-up run.',
    ]
    if report.model:
        assumptions.append(
            f'Model override `{report.model}` will be used when executing.'
        )
    if report.routing is not None:
        assumptions.append(
            f'Route-model category `{report.routing.category}` may select a provider-specific model at execution time.'
        )
    if clarification.needs_clarification:
        assumptions.append(
            'Task ambiguity is above the clarify threshold; execution should wait for answers or narrower scope.'
        )
    else:
        assumptions.append(
            'Clarification gate reports the task is sufficiently specified to proceed.'
        )
    return assumptions


def _plan_scope(report: PreflightReport) -> list[str]:
    pack = report.context_pack
    scope = [f'Task: {report.task}']
    if pack.candidate_files:
        paths = [
            row['path']
            for row in pack.candidate_files
            if isinstance(row, dict) and row.get('path')
        ]
        if paths:
            scope.append('Candidate paths from task/context mentions:')
            scope.extend(f'  - `{path}`' for path in paths[:12])
    else:
        scope.append(
            'No explicit file paths detected; scope may require discovery during execution.'
        )
    if report.memories:
        scope.append(
            f'{len(report.memories)} matched workspace memories will be injected.'
        )
    return scope


def _plan_steps(report: PreflightReport) -> list[str]:
    clarification = report.clarification
    steps = ['Review this plan artifact and confirm scope, risks, and verification.']
    if clarification.needs_clarification and clarification.question:
        steps.append(f'Answer clarification: {clarification.question}')
    steps.extend(
        [
            'Run read-only preflight or daily checks if harness health changed.',
            f'Execute with `teaagent run` using permission mode `{report.permission_mode.value}` or stricter.',
            'Verify with tests or explicit success checks listed below.',
            'If execution mutates files, use `teaagent agent undo <run_id>` before manual edits stack on top.',
        ]
    )
    return steps


def _plan_files_likely_touched(report: PreflightReport) -> list[str]:
    paths: list[str] = []
    for row in report.context_pack.candidate_files:
        if not isinstance(row, dict):
            continue
        path = row.get('path')
        if isinstance(path, str) and path and path not in paths:
            paths.append(path)
    lower = report.task.lower()
    if 'test' in lower and 'test' not in paths:
        paths.append('tests/ (discover relevant tests)')
    if any(marker in lower for marker in ('readme', 'docs/', 'documentation')):
        paths.append('docs/ (if documentation must change)')
    return paths


def _plan_verification(report: PreflightReport) -> list[str]:
    lower = report.task.lower()
    checks: list[str] = []
    if any(marker in lower for marker in ('pytest', 'test', 'tests', 'unittest')):
        checks.append(
            'Run targeted pytest (or project test command) and confirm green.'
        )
    if any(marker in lower for marker in ('lint', 'ruff', 'mypy', 'typecheck')):
        checks.append('Run configured linters/typecheckers on touched files.')
    if any(marker in lower for marker in ('build', 'compile')):
        checks.append('Run the project build step and confirm success.')
    if not checks:
        checks.append(
            'Define an observable pass/fail check (test output, CLI behavior, or file diff) before execution.'
        )
    if report.clarification.scores.success < 0.85:
        checks.append(
            'Success criteria were weak in clarify scoring; confirm acceptance checks with the user.'
        )
    return checks


def _plan_risk_gates(report: PreflightReport) -> list[str]:
    mode = report.permission_mode.value
    gates = [
        f'Permission mode for execution: `{mode}`.',
        'Destructive workspace tools require explicit approval in `prompt` mode.',
    ]
    if mode in {'workspace-write', 'danger-full-access'}:
        gates.append(
            'Writes are allowed; prefer `teaagent agent undo` immediately after exploratory edits.'
        )
    else:
        gates.append(
            'Execution should stay read-only until scope and verification are approved.'
        )
    health = report.health or {}
    for failure in health.get('failures') or []:
        gates.append(f'Harness health blocker: {failure}')
    for warning in health.get('warnings') or []:
        gates.append(f'Harness warning: {warning}')
    return gates


def render_plan_markdown(report: PreflightReport) -> str:
    data = report.to_dict()
    clarification = data.get('clarification') or {}
    context_pack = data.get('context_pack') or {}
    token_budget = data.get('token_budget') or {}
    lines = [
        '# TeaAgent Plan',
        '',
        '## Summary',
        '',
        f'- **Task:** {report.task}',
        f'- **Ready for execution:** {data.get("ready", False)}',
        f'- **Provider:** {report.provider}',
        f'- **Model:** {report.model or "(default)"}',
        f'- **Permission mode:** {report.permission_mode.value}',
        '',
        '## Assumptions',
        '',
        *_bullet_lines(
            _plan_assumptions(report), empty='No additional assumptions recorded.'
        ),
        '',
        '## Scope',
        '',
        *_plan_scope(report),
        '',
        '## Steps',
        '',
        *[
            f'{index}. {step}'
            for index, step in enumerate(_plan_steps(report), start=1)
        ],
        '',
        '## Files likely touched',
        '',
        *_bullet_lines(
            _plan_files_likely_touched(report),
            empty='No paths inferred; agent may need discovery tools first.',
        ),
        '',
        '## Verification',
        '',
        *_bullet_lines(
            _plan_verification(report), empty='Add explicit verification steps.'
        ),
        '',
        '## Rollback',
        '',
        '- After a mutating run, restore workspace state with `teaagent agent undo` (defaults to last run with a journal).',
        '- Specify `teaagent agent undo <run_id>` when multiple runs occurred.',
        '',
        '## Risk and approval gates',
        '',
        *_bullet_lines(
            _plan_risk_gates(report), empty='No additional risk gates recorded.'
        ),
        '',
        '## Clarification',
        '',
    ]
    questions = clarification.get('questions') or []
    if clarification.get('question'):
        questions = [clarification['question'], *questions]
    if questions:
        lines.extend(f'- {question}' for question in questions)
    else:
        lines.append('- No blocking clarification questions.')
    missing = clarification.get('missing') or []
    if missing:
        lines.extend(['', 'Missing dimensions:', *[f'- {item}' for item in missing]])
    lines.extend(
        [
            '',
            '## Context evidence',
            '',
            f'- Read-only planning: {context_pack.get("read_only", False)}',
            f'- Tools available: {report.tool_count}',
            f'- Matched memories: {len(report.memories)}',
            f'- Estimated prompt pressure: {token_budget.get("estimated_total_tokens", "n/a")}',
            '',
            '## Execute',
            '',
            'When this plan is approved:',
            '',
            '```bash',
            'teaagent run <provider> --from-plan .teaagent/plans/<this-file>.md '
            f'--permission-mode {report.permission_mode.value}',
            '```',
            '',
        ]
    )
    return '\n'.join(lines)


def write_plan_artifact(report: PreflightReport, *, root: str | Path) -> Path:
    workspace = Path(root).resolve()
    plans_dir = workspace / '.teaagent' / 'plans'
    plans_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    filename = f'{stamp}-{_slugify(report.task)}.md'
    path = plans_dir / filename
    atomic_write_text(path, render_plan_markdown(report))
    return path
