"""Task-specific offline eval cases stored as eval_dataset.json per candidate."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from teaagent.storage import atomic_write_text

EVAL_DATASET_FILENAME = 'eval_dataset.json'


def eval_dataset_path(candidate_dir: Path) -> Path:
    return candidate_dir / EVAL_DATASET_FILENAME


def write_default_eval_dataset(
    candidate_dir: Path,
    *,
    task: str,
    final_answer: str,
    skill_name: str,
) -> Path:
    """Write a default eval_dataset.json derived from the source run."""
    excerpt = final_answer.strip()
    if len(excerpt) > 48:
        excerpt = excerpt[:48]
    cases: list[dict[str, Any]] = [
        {
            'id': 'source_task_min_length',
            'check': 'source_task_min_length',
            'min_length': 15,
        },
        {
            'id': 'skill_frontmatter',
            'check': 'skill_md_contains',
            'substring': '---',
        },
        {
            'id': 'skill_names_skill',
            'check': 'skill_md_contains',
            'substring': f'name: {skill_name}',
        },
        {
            'id': 'block_obvious_injection',
            'check': 'skill_md_not_contains',
            'substring': 'ignore previous instructions',
        },
    ]
    if excerpt:
        cases.append(
            {
                'id': 'reference_preserves_answer_excerpt',
                'check': 'reference_contains',
                'substring': excerpt,
            }
        )
    if task.strip():
        token = task.strip().split()[0]
        if len(token) >= 4:
            cases.append(
                {
                    'id': 'reference_mentions_task_token',
                    'check': 'reference_contains',
                    'substring': token,
                }
            )
    payload = {'schema_version': 1, 'cases': cases}
    path = eval_dataset_path(candidate_dir)
    atomic_write_text(path, json.dumps(payload, indent=2) + '\n')
    return path


def load_eval_dataset(candidate_dir: Path) -> dict[str, Any] | None:
    path = eval_dataset_path(candidate_dir)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _provenance_task(candidate_dir: Path) -> str:
    path = candidate_dir / 'provenance.json'
    if not path.is_file():
        return ''
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return ''
    return str(payload.get('source_task', '')).strip()


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ''
    return path.read_text(encoding='utf-8')


def _run_case(candidate_dir: Path, case: dict[str, Any]) -> str | None:
    """Return an error message when the case fails."""
    check = str(case.get('check', '')).strip()
    case_id = str(case.get('id', check)).strip()

    if check == 'source_task_min_length':
        task = _provenance_task(candidate_dir)
        minimum = int(case.get('min_length', 1))
        if len(task) < minimum:
            return f'{case_id}: source_task shorter than {minimum} chars'
        return None

    if check == 'source_task_contains':
        task = _provenance_task(candidate_dir)
        needle = str(case.get('substring', ''))
        if needle and needle not in task:
            return f'{case_id}: source_task missing substring {needle!r}'
        return None

    if check == 'skill_md_contains':
        text = _read_text(candidate_dir / 'SKILL.md')
        needle = str(case.get('substring', ''))
        if needle and needle not in text:
            return f'{case_id}: SKILL.md missing substring {needle!r}'
        return None

    if check == 'skill_md_not_contains':
        text = _read_text(candidate_dir / 'SKILL.md')
        needle = str(case.get('substring', ''))
        if needle and needle.lower() in text.lower():
            return f'{case_id}: SKILL.md must not contain {needle!r}'
        return None

    if check == 'reference_contains':
        text = _read_text(candidate_dir / 'REFERENCE.md')
        needle = str(case.get('substring', ''))
        if needle and needle not in text:
            return f'{case_id}: REFERENCE.md missing substring {needle!r}'
        return None

    if check == 'regex':
        target_name = str(case.get('target', 'skill_md'))
        pattern = str(case.get('pattern', ''))
        if not pattern:
            return f'{case_id}: regex case missing pattern'
        paths = {
            'skill_md': candidate_dir / 'SKILL.md',
            'reference': candidate_dir / 'REFERENCE.md',
        }
        path = paths.get(target_name, candidate_dir / 'SKILL.md')
        text = _read_text(path)
        flags = re.IGNORECASE if case.get('ignore_case') else 0
        if not re.search(pattern, text, flags):
            return f'{case_id}: {target_name} did not match /{pattern}/'
        return None

    return f'{case_id}: unknown check type {check!r}'


def run_eval_dataset_checks(candidate_dir: Path) -> tuple[list[str], list[str]]:
    """Run eval_dataset.json cases. Returns (checks_run, failures)."""
    dataset = load_eval_dataset(candidate_dir)
    if dataset is None:
        return [], []
    cases = dataset.get('cases')
    if not isinstance(cases, list):
        return ['eval_dataset'], ['eval_dataset.json has no cases array']
    checks: list[str] = []
    failures: list[str] = []
    for raw in cases:
        if not isinstance(raw, dict):
            failures.append('eval_dataset case must be an object')
            continue
        case_id = str(raw.get('id', 'case')).strip()
        checks.append(f'eval_dataset:{case_id}')
        error = _run_case(candidate_dir, raw)
        if error:
            failures.append(error)
    return checks, failures
