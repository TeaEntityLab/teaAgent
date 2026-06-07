"""Offline eval gate for skill candidates — structural checks + deterministic fixture-based behavioral eval (DSK-P1-001)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from teaagent.skill_candidate_artifacts import (
    candidate_bundle_digest,
    validate_candidate_artifacts,
)
from teaagent.skill_eval_dataset import run_eval_dataset_checks
from teaagent.skill_review import review_skill
from teaagent.storage import atomic_write_text

DEFAULT_MAX_SKILL_BYTES = 32_000

# ═══════════════════════════════════════════════════════════════════════════
# DSK-P1-001 behavioral-eval dataclasses
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class EvalCase:
    """A single eval scenario with pass criteria."""

    name: str
    input_text: str
    expected_titles: list[str]
    expected_row_count: int | None
    expected_json: bool
    reject_patterns: list[str]


@dataclass
class EvalRunResult:
    """Outcome of one eval case."""

    case_name: str
    passed: bool
    failures: list[str]
    output: str


@dataclass
class EvalReport:
    """Full eval report for a skill candidate."""

    candidate_name: str
    passed: bool
    results: list[EvalRunResult]
    summary: dict[str, Any]
    created_at: str
    checks: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()
    content_digest: str = ''
    skill_md_hash: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'candidate_name': self.candidate_name,
            'passed': self.passed,
            'results': [asdict(r) for r in self.results],
            'summary': self.summary,
            'created_at': self.created_at,
            'checks': list(self.checks),
            'failures': list(self.failures),
            'content_digest': self.content_digest,
            'skill_md_hash': self.skill_md_hash,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> EvalReport:
        raw_results = payload.get('results') or []
        results: list[EvalRunResult] = []
        for item in raw_results:
            if isinstance(item, dict):
                results.append(EvalRunResult(**item))
        return cls(
            candidate_name=str(payload.get('candidate_name', '')),
            passed=bool(payload.get('passed', False)),
            results=results,
            summary=payload.get('summary') or {},
            created_at=str(payload.get('created_at', '')),
            checks=tuple(payload.get('checks') or ()),
            failures=tuple(payload.get('failures') or ()),
            content_digest=str(payload.get('content_digest', '')),
            skill_md_hash=str(payload.get('skill_md_hash', '')),
        )


@dataclass
class EvalFixture:
    """Deterministic test fixture for behavioral eval."""

    name: str
    content: str
    expected_titles: list[str]
    expected_row_count: int | None


# ═══════════════════════════════════════════════════════════════════════════
# Legacy report (internal / historical compatibility)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class SkillEvalReport:
    passed: bool
    checks: tuple[str, ...]
    failures: tuple[str, ...]
    content_digest: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'passed': self.passed,
            'checks': list(self.checks),
            'failures': list(self.failures),
            'content_digest': self.content_digest,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SkillEvalReport:
        return cls(
            passed=bool(payload.get('passed')),
            checks=tuple(str(item) for item in (payload.get('checks') or ())),
            failures=tuple(str(item) for item in (payload.get('failures') or ())),
            content_digest=str(payload.get('content_digest', '') or ''),
        )


# ═══════════════════════════════════════════════════════════════════════════
# Fixture-passthrough adapter for offline eval (format + schema validation only)
# ═══════════════════════════════════════════════════════════════════════════


class FakeToolAdapter:
    """Fixture-passthrough adapter for offline skill evaluation.

    Returns fixture content verbatim — it does NOT evaluate whether the skill
    would actually produce such output. The ``fixture_validation`` check
    attests only that fixtures are well-formed and match SKILL.md format
    requirements; it does NOT attest behavioral correctness.
    """

    def __init__(self, skill_md: str) -> None:
        self.skill_md = skill_md

    def run(self, input_text: str, fixture_content: str) -> str:
        if fixture_content:
            return fixture_content
        return f'[no fixture] Received: {input_text[:80]}'


# ═══════════════════════════════════════════════════════════════════════════
# Path & persistence
# ═══════════════════════════════════════════════════════════════════════════


def eval_report_path(candidate_dir: Path) -> Path:
    return candidate_dir / 'eval_report.json'


def load_eval_report(candidate_dir: Path) -> EvalReport | None:
    path = eval_report_path(candidate_dir)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return EvalReport.from_dict(payload)


def write_eval_report(candidate_dir: Path, report: EvalReport) -> Path:
    path = eval_report_path(candidate_dir)
    atomic_write_text(path, json.dumps(report.to_dict(), sort_keys=True))
    return path


# ═══════════════════════════════════════════════════════════════════════════
# Offline eval runner (structural + behavioral)
# ═══════════════════════════════════════════════════════════════════════════

_FORMAT_SPECIFIERS: dict[str, str] = {
    'json': 'json',
    'markdown': 'markdown',
    ' md ': 'markdown',
    'xml': 'xml',
    'rss': 'xml',
    'table': 'table',
    'list': 'list',
}


def _detect_expected_formats(skill_md: str) -> dict[str, str]:
    """Extract format requirements from SKILL.md content.

    Returns a deduplicated mapping of matched keyword -> canonical format name.
    """
    detected: dict[str, str] = {}
    normalized = skill_md.lower()
    for keyword, fmt in _FORMAT_SPECIFIERS.items():
        if keyword in normalized and fmt not in detected.values():
            detected[keyword] = fmt
    return detected


def _output_matches_format(output: str, fmt: str) -> bool:
    """Check whether a single eval case output satisfies the expected format."""
    if not output.strip():
        return False
    if fmt == 'json':
        try:
            json.loads(output)
            return True
        except json.JSONDecodeError:
            return False
    if fmt == 'markdown':
        return bool(re.search(r'^#{1,6}\s', output, re.MULTILINE)) or bool(
            re.search(r'^[-*]\s', output, re.MULTILINE)
        )
    if fmt == 'xml':
        return '<?xml' in output or bool(re.search(r'^<\w+', output, re.MULTILINE))
    if fmt == 'table':
        return '|' in output and output.count('\n') >= 2
    if fmt == 'list':
        return bool(re.search(r'^[-*]\s', output, re.MULTILINE)) or bool(
            re.search(r'^\d+[.\)]\s', output, re.MULTILINE)
        )
    return False


def _check_required_artifacts(
    candidate_dir: Path,
    checks: list[str],
    failures: list[str],
) -> None:
    checks.append('required_artifacts')
    artifact_errors = validate_candidate_artifacts(candidate_dir)
    if artifact_errors:
        failures.extend(artifact_errors)


def _check_skill_size(
    candidate_dir: Path,
    max_skill_bytes: int,
    checks: list[str],
    failures: list[str],
) -> None:
    checks.append('skill_size')
    skill_path = candidate_dir / 'SKILL.md'
    if skill_path.is_file():
        size = skill_path.stat().st_size
        if size > max_skill_bytes:
            failures.append(
                f'SKILL.md exceeds max size ({size} > {max_skill_bytes} bytes)'
            )
    else:
        failures.append('missing SKILL.md')


def _check_skill_review_file(
    candidate_dir: Path,
    checks: list[str],
    failures: list[str],
) -> None:
    checks.append('skill_review')
    skill_path = candidate_dir / 'SKILL.md'
    if skill_path.is_file():
        review = review_skill(skill_path)
        for finding in review.findings:
            if finding.severity == 'error':
                failures.append(finding.message)


def _check_provenance_file(
    candidate_dir: Path,
    checks: list[str],
    failures: list[str],
) -> None:
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


def _check_reference_file(
    candidate_dir: Path,
    checks: list[str],
    failures: list[str],
) -> None:
    checks.append('reference_nonempty')
    reference_path = candidate_dir / 'REFERENCE.md'
    if reference_path.is_file():
        if len(reference_path.read_text(encoding='utf-8').strip()) < 40:
            failures.append('REFERENCE.md too short for offline eval')
    else:
        failures.append('missing REFERENCE.md')


def _validate_eval_case(
    case: Any,
    output: str,
) -> list[str]:
    case_failures: list[str] = []
    for title in case.expected_titles:
        if title not in output:
            case_failures.append(f'missing expected title: {title!r}')
    if case.expected_row_count is not None:
        actual_rows = len([ln for ln in output.split('\n') if ln.strip()])
        if actual_rows != case.expected_row_count:
            case_failures.append(
                f'row count mismatch: expected {case.expected_row_count}, got {actual_rows}'
            )
    if case.expected_json:
        try:
            json.loads(output)
        except json.JSONDecodeError:
            case_failures.append('expected valid JSON but output is not parseable')
    for pattern in case.reject_patterns:
        if pattern.lower() in output.lower():
            case_failures.append(f'output contains rejected pattern: {pattern!r}')
    return case_failures


def _find_case_fixture(
    case: Any,
    fixture_map: dict[str, EvalFixture],
) -> EvalFixture | None:
    fixture = fixture_map.get(case.name)
    if fixture is None:
        for fname, ef in fixture_map.items():
            if case.name.startswith(fname) or fname.startswith(case.name):
                return ef
    return fixture


def _run_eval_cases(
    eval_cases: list[Any],
    fixture_map: dict[str, EvalFixture],
    adapter: FakeToolAdapter,
) -> list[EvalRunResult]:
    eval_results: list[EvalRunResult] = []
    for case in eval_cases:
        fixture = _find_case_fixture(case, fixture_map)
        fixture_content = fixture.content if fixture else ''
        output = adapter.run(case.input_text, fixture_content)
        case_failures = _validate_eval_case(case, output)
        passed = not case_failures
        eval_results.append(
            EvalRunResult(
                case_name=case.name,
                passed=passed,
                failures=case_failures,
                output=output,
            )
        )
    return eval_results


def _check_fixture_formats(
    eval_results: list[EvalRunResult],
    skill_md: str,
    failures: list[str],
) -> None:
    expected_formats = _detect_expected_formats(skill_md)
    if expected_formats:
        passing_outputs = [r.output for r in eval_results if r.passed]
        for fmt_name, fmt_key in expected_formats.items():
            if not any(_output_matches_format(o, fmt_key) for o in passing_outputs):
                failures.append(
                    f'output does not reflect SKILL.md format requirements: '
                    f"'{fmt_name}' format expected but not found in any passing case output"
                )


def run_offline_eval(
    candidate_dir: Path,
    *,
    max_skill_bytes: int = DEFAULT_MAX_SKILL_BYTES,
    fixture_dir: Path | None = None,
) -> EvalReport:
    from teaagent.skill_eval_fixtures import (
        get_default_eval_cases,
        get_default_eval_fixtures,
    )

    checks: list[str] = []
    failures: list[str] = []

    _check_required_artifacts(candidate_dir, checks, failures)
    _check_skill_size(candidate_dir, max_skill_bytes, checks, failures)
    _check_skill_review_file(candidate_dir, checks, failures)
    _check_provenance_file(candidate_dir, checks, failures)
    _check_reference_file(candidate_dir, checks, failures)

    dataset_checks, dataset_failures = run_eval_dataset_checks(candidate_dir)
    checks.extend(dataset_checks)
    failures.extend(dataset_failures)

    skill_path = candidate_dir / 'SKILL.md'
    skill_md = skill_path.read_text(encoding='utf-8') if skill_path.is_file() else ''
    adapter = FakeToolAdapter(skill_md)

    eval_cases = get_default_eval_cases()
    fixtures = get_default_eval_fixtures()
    fixture_map: dict[str, EvalFixture] = {f.name: f for f in fixtures}

    eval_results = _run_eval_cases(eval_cases, fixture_map, adapter)

    checks.append('fixture_validation')
    _check_fixture_formats(eval_results, skill_md, failures)

    skill_md_hash = (
        hashlib.sha256(skill_md.encode('utf-8')).hexdigest() if skill_md else ''
    )

    content_digest = ''
    if not failures:
        content_digest = candidate_bundle_digest(candidate_dir)

    all_cases_passed = all(r.passed for r in eval_results)
    overall_passed = not failures and all_cases_passed

    summary: dict[str, Any] = {
        'total_cases': len(eval_results),
        'passed_cases': sum(1 for r in eval_results if r.passed),
        'failed_cases': sum(1 for r in eval_results if not r.passed),
    }

    return EvalReport(
        candidate_name=candidate_dir.name,
        passed=overall_passed,
        results=eval_results,
        summary=summary,
        created_at=datetime.now(timezone.utc).isoformat(),
        checks=tuple(checks),
        failures=tuple(failures),
        content_digest=content_digest,
        skill_md_hash=skill_md_hash,
    )
