"""Candidate repair loop after eval failure (DSK-P1-006).

When a skill candidate's offline eval fails, this module generates actionable
repair tasks instead of silent install or opaque failure.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from teaagent.skill_eval import EvalReport
from teaagent.storage import atomic_write_text


@dataclass
class RepairTask:
    """A single actionable repair task for a failed skill candidate."""

    area: str
    """Category of the repair (e.g. 'artifact', 'content', 'size', 'provenance', 'eval_case')."""

    description: str
    """Human-readable description of what action to take."""

    severity: str
    """'error' (must fix) or 'warning' (should fix)."""

    eval_failure: str
    """The original failure string from the eval report."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RepairTask:
        return cls(
            **{
                k: v
                for k, v in payload.items()
                if k in {'area', 'description', 'severity', 'eval_failure'}
            }
        )


# ═══════════════════════════════════════════════════════════════════════════
# Failure → repair task mapping
# ═══════════════════════════════════════════════════════════════════════════


def _map_structural_failure(failure: str) -> RepairTask | None:
    """Map a structural failure string to a RepairTask, or None if unmatched."""
    if failure == 'missing SKILL.md':
        return RepairTask(
            area='artifact',
            description='Create a SKILL.md file with name, description, and instructions in YAML frontmatter',
            severity='error',
            eval_failure=failure,
        )

    if failure.startswith('SKILL.md exceeds max size'):
        return RepairTask(
            area='size',
            description='Reduce SKILL.md to under the max byte limit by trimming verbose sections or unnecessary examples',
            severity='error',
            eval_failure=failure,
        )

    if failure == 'missing REFERENCE.md':
        return RepairTask(
            area='artifact',
            description='Create a REFERENCE.md file with at least 40 characters of documentation for the skill',
            severity='error',
            eval_failure=failure,
        )

    if failure == 'REFERENCE.md too short for offline eval':
        return RepairTask(
            area='content',
            description='Expand REFERENCE.md to at least 40 characters of meaningful documentation',
            severity='warning',
            eval_failure=failure,
        )

    if failure == 'missing provenance.json':
        return RepairTask(
            area='artifact',
            description='Regenerate the candidate to include provenance.json with source_run_id and content_digest',
            severity='error',
            eval_failure=failure,
        )

    if failure == 'provenance.json missing source_run_id':
        return RepairTask(
            area='provenance',
            description='Add source_run_id field to provenance.json from the original agent run',
            severity='error',
            eval_failure=failure,
        )

    if failure == 'provenance.json missing content_digest':
        return RepairTask(
            area='provenance',
            description='Re-run candidate generation to compute and embed content_digest in provenance.json',
            severity='error',
            eval_failure=failure,
        )

    # Behavioral eval failures detected by prefix
    if failure.startswith('missing expected title: '):
        title = failure[len('missing expected title: ') :].strip().strip("'")
        return RepairTask(
            area='eval_case',
            description=f"Ensure the skill output includes expected title '{title}'",
            severity='error',
            eval_failure=failure,
        )

    if failure.startswith('row count mismatch:'):
        # Parse "row count mismatch: expected N, got M"
        return RepairTask(
            area='eval_case',
            description=f'Adjust output format: {failure}',
            severity='error',
            eval_failure=failure,
        )

    if failure == 'expected valid JSON but output is not parseable':
        return RepairTask(
            area='eval_case',
            description='Fix the skill output to produce valid JSON when asked for structured data',
            severity='error',
            eval_failure=failure,
        )

    if failure.startswith('output contains rejected pattern: '):
        rest = failure[len('output contains rejected pattern: ') :].strip().strip("'")
        return RepairTask(
            area='eval_case',
            description=f"Remove pattern '{rest}' from the skill output; it matches rejected/injection patterns",
            severity='error',
            eval_failure=failure,
        )

    # Catch-all for any other failure
    return RepairTask(
        area='unknown',
        description=f'Fix: {failure}',
        severity='error',
        eval_failure=failure,
    )


def generate_repair_tasks(
    eval_report: EvalReport,
    candidate_dir: Path,
) -> list[RepairTask]:
    """Generate actionable repair tasks from an eval report for a candidate.

    Maps each structural failure and each failed behavioral eval case
    to a specific RepairTask.
    """
    tasks: list[RepairTask] = []

    # Map structural failures
    for failure in eval_report.failures:
        # Check if this failure comes from a behavioral eval case failure
        # (those are already covered by per-result handling below)
        is_behavioral = any(failure in r.failures for r in eval_report.results)
        if is_behavioral:
            continue
        task = _map_structural_failure(failure)
        if task is not None:
            tasks.append(task)

    # Map failed behavioral eval cases
    for result in eval_report.results:
        if not result.passed and result.failures:
            tasks.append(
                RepairTask(
                    area='fixture_validation',
                    description=f"Case '{result.case_name}' failed: {'; '.join(result.failures)}",
                    severity='error',
                    eval_failure='; '.join(result.failures),
                )
            )

    return tasks


# ═══════════════════════════════════════════════════════════════════════════
# Persistence helpers
# ═══════════════════════════════════════════════════════════════════════════


def repair_tasks_path(candidate_dir: Path) -> Path:
    """Return the path to the repair_tasks.json file for a candidate."""
    return candidate_dir / 'repair_tasks.json'


def load_repair_tasks(candidate_dir: Path) -> list[RepairTask]:
    """Load repair tasks from a candidate's repair_tasks.json."""
    path = repair_tasks_path(candidate_dir)
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [RepairTask.from_dict(item) for item in payload if isinstance(item, dict)]


def write_repair_tasks(candidate_dir: Path, tasks: list[RepairTask]) -> Path:
    """Write repair tasks to a candidate's repair_tasks.json. Returns the file path."""
    path = repair_tasks_path(candidate_dir)
    atomic_write_text(
        path,
        json.dumps([t.to_dict() for t in tasks], indent=2, sort_keys=True) + '\n',
    )
    return path
