from __future__ import annotations

from teaagent.code_analysis import extract_candidate_paths, get_lsp_context
from teaagent.code_analysis._types import CodeReference


class _FakeManager:
    def __init__(self):
        from pathlib import Path

        self.root = Path('.')

    def document_diagnostics(self, path: str):
        if path.endswith('.py'):
            return [
                {
                    'message': 'bad import',
                    'severity': 1,
                    'range': {'start': {'line': 2, 'character': 4}},
                }
            ]
        return []

    def document_symbols(self, path: str):
        if path.endswith('.py'):
            return [
                CodeReference(
                    symbol='main',
                    file_path=path,
                    line=10,
                    column=1,
                    kind='function',
                    detail='() -> None',
                )
            ]
        return []


def test_extract_candidate_paths_from_task_and_spec():
    paths = extract_candidate_paths(
        'Please inspect src/app.py and lib/util.ts', 'also check src/app.py again'
    )
    assert paths == ['src/app.py', 'lib/util.ts']


def test_get_lsp_context_renders_diagnostics_and_symbols():
    ctx = get_lsp_context(
        candidate_paths=['src/app.py'],
        manager=_FakeManager(),
        max_files=3,
        diagnostic_severity_limit=2,
    )
    assert 'bad import' in ctx
    assert 'symbol function main' in ctx
