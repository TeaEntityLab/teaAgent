"""HTML report renderer for EvalReport.

Usage::

    from teaagent.eval import run_eval
    from teaagent.eval_report import render_html_report

    report = run_eval(cases, run_case)
    html = render_html_report(report)
    Path('report.html').write_text(html, encoding='utf-8')
"""

from __future__ import annotations

import html as _html
from typing import Any


def render_html_report(report: Any, *, title: str = 'TeaAgent Eval Report') -> str:
    """Render *report* as a self-contained HTML string.

    Parameters
    ----------
    report:
        An :class:`~teaagent.eval.EvalReport` instance.
    title:
        ``<title>`` text for the HTML page.

    Returns
    -------
    str
        Complete HTML document as a string.
    """
    results = getattr(report, 'results', [])
    pass_rate = getattr(report, 'pass_rate', 0.0)
    total = len(results)
    passed_count = sum(1 for r in results if getattr(r, 'passed', False))

    rows = []
    for r in results:
        name = _esc(getattr(r, 'name', ''))
        output = _esc(str(getattr(r, 'output', ''))[:300])
        passed = getattr(r, 'passed', False)
        failures = getattr(r, 'failures', ())
        judge = getattr(r, 'judge_score', None)

        status_cell = (
            '<td class="pass">PASS ✓</td>'
            if passed
            else f'<td class="fail">FAIL ✗<br><small>{_esc("; ".join(failures))}</small></td>'
        )

        score_cell = ''
        reasoning_cell = ''
        if judge is not None:
            score = getattr(judge, 'score', '')
            reasoning = _esc(str(getattr(judge, 'reasoning', '')))
            score_cell = f'<td>{score}</td>'
            reasoning_cell = f'<td><small>{reasoning}</small></td>'
        else:
            score_cell = '<td>—</td>'
            reasoning_cell = '<td></td>'

        rows.append(
            f'<tr>{status_cell}<td>{name}</td>'
            f'<td><pre>{output}</pre></td>'
            f'{score_cell}{reasoning_cell}</tr>'
        )

    rows_html = '\n'.join(rows)
    pass_pct = f'{pass_rate * 100:.1f}%'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{_esc(title)}</title>
  <style>
    body {{ font-family: sans-serif; margin: 2em; }}
    h1 {{ color: #333; }}
    .summary {{ margin-bottom: 1em; font-size: 1.1em; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 0.4em 0.6em; text-align: left; vertical-align: top; }}
    th {{ background: #f0f0f0; }}
    .pass {{ color: green; font-weight: bold; }}
    .fail {{ color: red; font-weight: bold; }}
    pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; font-size: 0.85em; }}
  </style>
</head>
<body>
  <h1>{_esc(title)}</h1>
  <div class="summary">
    <strong>Pass rate:</strong> {pass_pct} ({passed_count}/{total})
  </div>
  <table>
    <thead>
      <tr><th>Status</th><th>Name</th><th>Output</th><th>Score</th><th>Reasoning</th></tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</body>
</html>"""


def _esc(text: str) -> str:
    return _html.escape(str(text))
