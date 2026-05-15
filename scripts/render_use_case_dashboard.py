from __future__ import annotations

import argparse
import html
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MatrixRow:
    use_case: str
    covered: str
    required_tests: str
    missing_tests: str


def parse_matrix_markdown(markdown: str) -> list[MatrixRow]:
    rows: list[MatrixRow] = []
    for line in markdown.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        if line.startswith("|---") or "Use Case" in line:
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) != 4:
            continue
        rows.append(
            MatrixRow(
                use_case=parts[0],
                covered=parts[1],
                required_tests=parts[2],
                missing_tests=parts[3],
            )
        )
    return rows


def render_html(rows: list[MatrixRow]) -> str:
    total = len(rows)
    covered = sum(1 for row in rows if row.covered == "yes")
    percent = 0.0 if total == 0 else (covered / total) * 100.0

    table_rows = "\n".join(
        (
            "<tr>"
            f"<td>{html.escape(row.use_case)}</td>"
            f"<td class=\"{row.covered}\">{html.escape(row.covered)}</td>"
            f"<td><code>{html.escape(row.required_tests)}</code></td>"
            f"<td><code>{html.escape(row.missing_tests)}</code></td>"
            "</tr>"
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
    </section>
    <table>
      <thead>
        <tr>
          <th>Use Case</th>
          <th>Covered</th>
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
    rows = parse_matrix_markdown(matrix_path.read_text(encoding="utf-8"))
    output_path.write_text(render_html(rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render docs/use-case-matrix.md as an HTML dashboard."
    )
    parser.add_argument(
        "--matrix",
        default="docs/use-case-matrix.md",
        help="Path to markdown matrix file.",
    )
    parser.add_argument(
        "--output",
        default="docs/use-case-matrix.html",
        help="Path to generated HTML output.",
    )
    args = parser.parse_args()
    render_dashboard(matrix_path=Path(args.matrix), output_path=Path(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
