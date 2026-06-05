"""Optional real-model dynamic skill eval profile (DSK-P2-002).

Runs the same EvalCase suite against a live LLM adapter instead of the
deterministic FakeToolAdapter.  Results are stored separately from the
offline report so that real-model eval never blocks CI/PRs.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from teaagent.skill_eval import (
    EvalReport,
    EvalRunResult,
)
from teaagent.storage import atomic_write_text


def real_eval_report_path(candidate_dir: Path) -> Path:
    return candidate_dir / 'eval_report_real.json'


def load_real_eval_report(candidate_dir: Path) -> EvalReport | None:
    path = real_eval_report_path(candidate_dir)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return EvalReport.from_dict(payload)


def write_real_eval_report(candidate_dir: Path, report: EvalReport) -> Path:
    path = real_eval_report_path(candidate_dir)
    atomic_write_text(path, json.dumps(report.to_dict(), sort_keys=True))
    return path


def run_real_model_eval(
    candidate_dir: Path,
    *,
    model: str = 'gpt-4o',
    provider: str = 'gpt',
) -> EvalReport:
    """Evaluate a skill candidate against a real LLM using the same EvalCase suite.

    Uses a lazy import for ``create_llm_adapter`` so that environments without
    LLM dependencies can still import this module.
    """
    from teaagent.llm import LLMMessage, LLMRequest, create_llm_adapter
    from teaagent.skill_eval_fixtures import get_default_eval_cases

    skill_path = candidate_dir / 'SKILL.md'
    skill_md = skill_path.read_text(encoding='utf-8') if skill_path.is_file() else ''

    adapter = create_llm_adapter(provider, model=model)

    eval_cases = get_default_eval_cases()
    eval_results: list[EvalRunResult] = []
    failures: list[str] = []

    for case in eval_cases:
        case_failures: list[str] = []

        system_prompt = (
            f'{skill_md}\n\n'
            'You are a helpful assistant. Respond to the user request below.'
        )
        request = LLMRequest(
            messages=[LLMMessage(role='user', content=case.input_text)],
            system=system_prompt,
            max_tokens=2048,
            temperature=0.2,
        )

        try:
            response = adapter.complete(request)
            output = response.content
        except Exception as exc:
            output = ''
            case_failures.append(f'adapter error: {exc}')

        for title in case.expected_titles:
            if title not in output:
                case_failures.append(f'missing expected title: {title!r}')

        if case.expected_row_count is not None:
            actual_rows = len([ln for ln in output.split('\n') if ln.strip()])
            if actual_rows != case.expected_row_count:
                case_failures.append(
                    f'row count mismatch: expected {case.expected_row_count}, '
                    f'got {actual_rows}'
                )

        if case.expected_json:
            try:
                json.loads(output)
            except json.JSONDecodeError:
                case_failures.append('expected valid JSON but output is not parseable')

        for pattern in case.reject_patterns:
            if pattern.lower() in output.lower():
                case_failures.append(f'output contains rejected pattern: {pattern!r}')

        passed = not case_failures
        eval_results.append(
            EvalRunResult(
                case_name=case.name,
                passed=passed,
                failures=case_failures,
                output=output,
            )
        )
        failures.extend(case_failures)

    all_cases_passed = all(r.passed for r in eval_results)
    overall_passed = not failures and all_cases_passed

    summary: dict[str, Any] = {
        'total_cases': len(eval_results),
        'passed_cases': sum(1 for r in eval_results if r.passed),
        'failed_cases': sum(1 for r in eval_results if not r.passed),
        'model': model,
        'provider': provider,
    }

    return EvalReport(
        candidate_name=candidate_dir.name,
        passed=overall_passed,
        results=eval_results,
        summary=summary,
        created_at=datetime.now(timezone.utc).isoformat(),
        checks=('real_model_eval',),
        failures=tuple(set(failures)),
        content_digest='',
    )
