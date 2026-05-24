"""Offline eval gate for skill candidates (P3 self-improvement safety)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from teaagent.skill_candidate_artifacts import validate_candidate_artifacts
from teaagent.skill_review import review_skill
from teaagent.storage import atomic_write_text

DEFAULT_MAX_SKILL_BYTES = 32_000


@dataclass(frozen=True)
class SkillEvalReport:
    passed: bool
    checks: tuple[str, ...]
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            'passed': self.passed,
            'checks': list(self.checks),
            'failures': list(self.failures),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SkillEvalReport:
        return cls(
            passed=bool(payload.get('passed')),
            checks=tuple(str(item) for item in (payload.get('checks') or ())),
            failures=tuple(str(item) for item in (payload.get('failures') or ())),
        )


def eval_report_path(candidate_dir: Path) -> Path:
    return candidate_dir / 'eval_report.json'


def load_eval_report(candidate_dir: Path) -> SkillEvalReport | None:
    path = eval_report_path(candidate_dir)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return SkillEvalReport.from_dict(payload)


def write_eval_report(candidate_dir: Path, report: SkillEvalReport) -> Path:
    path = eval_report_path(candidate_dir)
    atomic_write_text(path, json.dumps(report.to_dict(), sort_keys=True))
    return path


def run_offline_eval(
    candidate_dir: Path,
    *,
    max_skill_bytes: int = DEFAULT_MAX_SKILL_BYTES,
) -> SkillEvalReport:
    """Run deterministic checks before human review or install."""
    checks: list[str] = []
    failures: list[str] = []

    checks.append('required_artifacts')
    artifact_errors = validate_candidate_artifacts(candidate_dir)
    if artifact_errors:
        failures.extend(artifact_errors)

    skill_path = candidate_dir / 'SKILL.md'
    checks.append('skill_size')
    if skill_path.is_file():
        size = skill_path.stat().st_size
        if size > max_skill_bytes:
            failures.append(
                f'SKILL.md exceeds max size ({size} > {max_skill_bytes} bytes)'
            )
    else:
        failures.append('missing SKILL.md')

    checks.append('skill_review')
    if skill_path.is_file():
        review = review_skill(skill_path)
        for finding in review.findings:
            if finding.severity == 'error':
                failures.append(finding.message)

    checks.append('provenance')
    provenance_path = candidate_dir / 'provenance.json'
    if provenance_path.is_file():
        try:
            provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            failures.append('invalid provenance.json')
            provenance = {}
        if not str(provenance.get('source_run_id', '')).strip():
            failures.append('provenance.json missing source_run_id')
        if not str(provenance.get('content_digest', '')).strip():
            failures.append('provenance.json missing content_digest')
    else:
        failures.append('missing provenance.json')

    checks.append('reference_nonempty')
    reference_path = candidate_dir / 'REFERENCE.md'
    if reference_path.is_file():
        if len(reference_path.read_text(encoding='utf-8').strip()) < 40:
            failures.append('REFERENCE.md too short for offline eval')
    else:
        failures.append('missing REFERENCE.md')

    passed = not failures
    return SkillEvalReport(
        passed=passed,
        checks=tuple(checks),
        failures=tuple(failures),
    )
