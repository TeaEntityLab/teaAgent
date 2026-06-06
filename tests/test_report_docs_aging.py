"""Tests for documentation aging dashboard."""

from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_module():
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'report_docs_aging.py'
    spec = spec_from_file_location('report_docs_aging_test', script)
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_generate_docs_aging_dashboard_groups_by_owner(tmp_path: Path) -> None:
    module = _load_module()
    docs = tmp_path / 'docs'
    docs.mkdir()
    doc = docs / 'sample.md'
    doc.write_text(
        '# Sample\n\n**Last reviewed:** 2020-01-01\n',
        encoding='utf-8',
    )
    entry = module.DocReviewEntry(
        'docs/sample.md', 'sample-owner', 'when sample changes'
    )
    row = module._scan_doc(entry, repo_root=tmp_path, stale_days=30)
    assert row.status == 'stale_by_age'
    assert row.owner == 'sample-owner'


def test_check_docs_aging_dashboard_passes_for_repo() -> None:
    root = Path(__file__).resolve().parents[1]
    module = _load_module()
    output_path = root / 'docs' / 'generated' / 'docs-aging-dashboard.md'
    if not output_path.is_file():
        module.write_docs_aging_dashboard(
            repo_root=root,
            output_path=output_path,
        )
    errors = module.check_docs_aging_dashboard(
        repo_root=root,
        output_path=output_path,
    )
    assert errors == []
