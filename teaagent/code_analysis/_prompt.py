from __future__ import annotations

import re
from pathlib import Path

from teaagent.code_analysis._manager import LSPServerManager

_PATH_RE = re.compile(r'(?P<path>[A-Za-z0-9_./\\-]+\.(?:py|pyi|ts|tsx|js|jsx))')


def extract_candidate_paths(*texts: str) -> list[str]:
    seen: set[str] = set()
    paths: list[str] = []
    for text in texts:
        if not text:
            continue
        for match in _PATH_RE.finditer(text):
            raw = match.group('path').strip()
            if raw in seen:
                continue
            seen.add(raw)
            paths.append(raw)
    return paths


def get_lsp_context(
    *,
    candidate_paths: list[str],
    manager: LSPServerManager,
    max_files: int,
    diagnostic_severity_limit: int,
) -> str:
    lines: list[str] = []
    for raw in candidate_paths[:max_files]:
        path = raw
        full = (
            str((manager.root / raw).resolve()) if not Path(raw).is_absolute() else raw
        )
        diagnostics = manager.document_diagnostics(path)
        symbols = manager.document_symbols(path)
        filtered = [
            d
            for d in diagnostics
            if int(d.get('severity', 99)) <= diagnostic_severity_limit
        ]
        if not filtered and not symbols:
            continue
        lines.append(f'--- {full} ---')
        for d in filtered:
            rng = d.get('range', {}) if isinstance(d, dict) else {}
            start = rng.get('start', {}) if isinstance(rng, dict) else {}
            line = int(start.get('line', 0)) + 1
            col = int(start.get('character', 0)) + 1
            msg = str(d.get('message', ''))
            sev = d.get('severity', '?')
            lines.append(f'  diag L{line}:{col} [sev={sev}] {msg}')
        for s in symbols[:20]:
            lines.append(
                f'  symbol {s.kind} {s.symbol} L{s.line}:{s.column} {s.detail}'.rstrip()
            )
    return '\n'.join(lines)
