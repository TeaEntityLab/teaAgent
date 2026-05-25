"""Large-repo context_pack: deterministic hits and bounded preflight latency."""

from __future__ import annotations

import io
import json
import time
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main
from teaagent.hybrid_search import LocalHybridSearchBackend


def test_large_repo_context_pack_hits_target_file_within_slo(tmp_path: Path) -> None:
    pkg = tmp_path / 'teaagent' / 'core'
    pkg.mkdir(parents=True)
    for index in range(40):
        (pkg / f'module_{index:02d}.py').write_text(
            f'def fn_{index}():\n    return {index}\n',
            encoding='utf-8',
        )
    target = pkg / 'runner.py'
    target.write_text(
        'def run_audit_chain():\n    """audit chain regressions in tests"""\n    pass\n',
        encoding='utf-8',
    )
    LocalHybridSearchBackend().index(
        root=tmp_path, args={'include': 'teaagent/**', 'collection': 'large-repo-at'}
    )
    task = 'review teaagent/core/runner.py audit chain regressions in tests'

    started = time.perf_counter()
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(['agent', 'preflight', 'gpt', task, '--root', str(tmp_path)])
    elapsed = time.perf_counter() - started
    payload = json.loads(out.getvalue())

    assert code == 0
    assert elapsed < 8.0, f'preflight took {elapsed:.2f}s on large fixture repo'
    paths = [entry['path'] for entry in payload['context_pack']['candidate_files']]
    assert 'teaagent/core/runner.py' in paths
    assert payload['context_pack']['read_only'] is True
    graph = payload['context_pack'].get('graph_rag') or {}
    assert graph.get('status') in {'indexed', 'not_indexed', 'partial'}
