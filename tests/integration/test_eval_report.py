"""IT: Eval HTML report generation."""

from __future__ import annotations

from teaagent.eval import EvalCase, EvalCaseResult, EvalReport, JudgeScore, run_eval
from teaagent.eval_report import render_html_report


def _make_report() -> EvalReport:
    cases = [
        EvalCase(name='add', task='1+1', expected_contains=('2',)),
        EvalCase(name='greet', task='say hi', expected_contains=('hello', 'hi')),
        EvalCase(name='fail', task='say xyz', expected_contains=('xyz',)),
    ]

    def runner(case: EvalCase) -> str:
        if case.name == 'add':
            return '2'
        if case.name == 'greet':
            return 'hello world'
        return 'wrong answer'

    return run_eval(cases, runner)


def test_render_html_returns_string():
    report = _make_report()
    html = render_html_report(report)
    assert isinstance(html, str)
    assert len(html) > 0


def test_html_contains_case_names():
    report = _make_report()
    html = render_html_report(report)
    assert 'add' in html
    assert 'greet' in html
    assert 'fail' in html


def test_html_contains_pass_fail_indicators():
    report = _make_report()
    html = render_html_report(report)
    # Some form of pass/fail indicator
    assert 'pass' in html.lower() or '✓' in html or 'PASS' in html
    assert 'fail' in html.lower() or '✗' in html or 'FAIL' in html


def test_html_contains_pass_rate():
    report = _make_report()
    html = render_html_report(report)
    # Pass rate like "66%" or "0.67" should appear
    assert '%' in html or str(round(report.pass_rate, 2)) in html


def test_html_is_valid_html_structure():
    report = _make_report()
    html = render_html_report(report)
    assert '<html' in html.lower() or '<table' in html.lower()
    assert '</html>' in html.lower() or '</table>' in html.lower()


def test_html_with_judge_scores():
    results = [
        EvalCaseResult(
            name='case1',
            output='answer',
            passed=True,
            failures=(),
            judge_score=JudgeScore(score=0.9, reasoning='looks good'),
        )
    ]
    report = EvalReport(results=results)
    html = render_html_report(report)
    assert '0.9' in html or '90' in html
    assert 'looks good' in html


def test_empty_report_renders():
    report = EvalReport(results=[])
    html = render_html_report(report)
    assert isinstance(html, str)
    # No cases — should still produce valid HTML skeleton
    assert '<' in html
