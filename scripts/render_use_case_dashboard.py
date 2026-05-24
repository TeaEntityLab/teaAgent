from __future__ import annotations

import argparse
import html
import re
from dataclasses import dataclass
from pathlib import Path

_SURVEY_DATE = re.compile(r'Landscape survey reviewed:\s*\*\*(\d{4}-\d{2}-\d{2})\*\*')
_OPEN_GAPS = re.compile(r'Open partial/planned gaps \(P1/P2\):\s*\*\*(\d+)\*\*')


@dataclass(frozen=True)
class MatrixRow:
    use_case: str
    covered: str
    blast_radius: str
    rollback_path: str
    audit_criticality: str
    required_tests: str
    missing_tests: str


@dataclass(frozen=True)
class MatrixMeta:
    survey_review_date: str
    open_gap_count: str


def parse_matrix_meta(markdown: str) -> MatrixMeta:
    survey_match = _SURVEY_DATE.search(markdown)
    gap_match = _OPEN_GAPS.search(markdown)
    return MatrixMeta(
        survey_review_date=survey_match.group(1) if survey_match else 'unknown',
        open_gap_count=gap_match.group(1) if gap_match else '?',
    )


def parse_matrix_markdown(markdown: str) -> list[MatrixRow]:
    rows: list[MatrixRow] = []
    for line in markdown.splitlines():
        line = line.strip()
        if not line.startswith('|'):
            continue
        if line.startswith('|---') or 'Use Case' in line:
            continue
        parts = [part.strip() for part in line.strip('|').split('|')]
        if len(parts) == 7:
            rows.append(
                MatrixRow(
                    use_case=parts[0],
                    covered=parts[1],
                    blast_radius=parts[2],
                    rollback_path=parts[3],
                    audit_criticality=parts[4],
                    required_tests=parts[5],
                    missing_tests=parts[6],
                )
            )
        elif len(parts) == 4:
            rows.append(
                MatrixRow(
                    use_case=parts[0],
                    covered=parts[1],
                    blast_radius='—',
                    rollback_path='—',
                    audit_criticality='—',
                    required_tests=parts[2],
                    missing_tests=parts[3],
                )
            )
    return rows


def render_html(rows: list[MatrixRow], *, meta: MatrixMeta | None = None) -> str:
    meta = meta or MatrixMeta(survey_review_date='unknown', open_gap_count='?')
    total = len(rows)
    covered = sum(1 for row in rows if row.covered == 'yes')
    percent = 0.0 if total == 0 else (covered / total) * 100.0

    table_rows = '\n'.join(
        (
            '<tr>'
            f'<td>{html.escape(row.use_case)}</td>'
            f'<td class="{row.covered}">{html.escape(row.covered)}</td>'
            f'<td>{html.escape(row.blast_radius)}</td>'
            f'<td>{html.escape(row.rollback_path)}</td>'
            f'<td>{html.escape(row.audit_criticality)}</td>'
            f'<td><code>{html.escape(row.required_tests)}</code></td>'
            f'<td><code>{html.escape(row.missing_tests)}</code></td>'
            '</tr>'
        )
        for row in rows
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TeaAgent Use-case Coverage</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f8fb;
      --surface: #ffffff;
      --text: #19212d;
      --muted: #5c6573;
      --border: #d9dee8;
      --ok: #0f7b44;
      --no: #a33a3a;
    }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    main {{
      max-width: 1100px;
      margin: 24px auto;
      padding: 0 16px;
    }}
    .summary {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;
    }}
    .summary h1 {{
      margin: 0 0 8px;
      font-size: 20px;
    }}
    .summary p {{
      margin: 0;
      color: var(--muted);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
    }}
    th, td {{
      text-align: left;
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
      font-size: 14px;
    }}
    th {{
      background: #f1f4f9;
      color: #2d3748;
      font-weight: 600;
    }}
    td.yes {{
      color: var(--ok);
      font-weight: 600;
    }}
    td.no {{
      color: var(--no);
      font-weight: 600;
    }}
    code {{
      white-space: pre-wrap;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
    }}
  </style>
</head>
<body>
  <main>
    <section class="summary">
      <h1>TeaAgent Use-case Coverage</h1>
      <p>Covered: {covered}/{total} ({percent:.1f}%)</p>
      <p>Landscape survey reviewed: {html.escape(meta.survey_review_date)} · Open partial/planned gaps (P1/P2): {html.escape(meta.open_gap_count)}</p>
    </section>
    <table>
      <thead>
        <tr>
          <th>Use Case</th>
          <th>Covered</th>
          <th>Blast Radius</th>
          <th>Rollback Path</th>
          <th>Audit Criticality</th>
          <th>Required Tests</th>
          <th>Missing Tests</th>
        </tr>
      </thead>
      <tbody>
        {table_rows}
      </tbody>
    </table>
  </main>
</body>
</html>
"""


def render_dashboard(*, matrix_path: Path, output_path: Path) -> None:
    markdown = matrix_path.read_text(encoding='utf-8')
    rows = parse_matrix_markdown(markdown)
    meta = parse_matrix_meta(markdown)
    output_path.write_text(render_html(rows, meta=meta), encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Render docs/use-case-matrix.md as an HTML dashboard.'
    )
    parser.add_argument(
        '--matrix',
        default='docs/use-case-matrix.md',
        help='Path to markdown matrix file.',
    )
    parser.add_argument(
        '--output',
        default='docs/use-case-matrix.html',
        help='Path to generated HTML output.',
    )
    args = parser.parse_args()
    render_dashboard(matrix_path=Path(args.matrix), output_path=Path(args.output))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
