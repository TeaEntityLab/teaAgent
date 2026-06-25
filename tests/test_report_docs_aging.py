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
    assert row.tier == 'working'


def test_scan_doc_archive_tier(tmp_path: Path) -> None:
    module = _load_module()
    docs = tmp_path / 'docs'
    docs.mkdir()
    doc = docs / 'analysis' / 'review-2026-06-12.md'
    doc.parent.mkdir(parents=True)
    doc.write_text(
        '# Review\n\n**Last reviewed:** 2020-01-01\n',
        encoding='utf-8',
    )
    entry = module.DocReviewEntry(
        'docs/analysis/review-2026-06-12.md', 'sample-owner', 'when sample changes'
    )
    row = module._scan_doc(entry, repo_root=tmp_path, stale_days=30)
    # Archive-tier docs are identified by date pattern, even if stale
    assert row.tier == 'archive'


def test_is_archive_tier(tmp_path: Path) -> None:
    module = _load_module()
    assert module._is_archive_tier('docs/analysis/foo-2026-06-12.md')
    assert module._is_archive_tier('docs/some-doc-2025-01-01.md')
    assert not module._is_archive_tier('docs/USAGE.md')
    assert not module._is_archive_tier('docs/cli.md')


def test_is_archive_tier_respects_working_current_truth_override() -> None:
    module = _load_module()
    ledger = 'docs/analysis/active-findings-status-ledger-2026-06-06.md'
    assert not module._is_archive_tier(ledger)
    assert not module._is_archive_tier(
        'analysis/active-findings-status-ledger-2026-06-06.md'
    )


def test_generate_docs_aging_excludes_archive_from_stale_list(tmp_path: Path) -> None:
    module = _load_module()
    docs = tmp_path / 'docs'
    docs.mkdir()
    # Create a working-tier stale doc
    working_doc = docs / 'working.md'
    working_doc.write_text(
        '# Working\n\n**Last reviewed:** 2020-01-01\n',
        encoding='utf-8',
    )
    # Create an archive-tier stale doc
    archive_doc = docs / 'analysis' / 'archived-2026-06-12.md'
    archive_doc.parent.mkdir(parents=True)
    archive_doc.write_text(
        '# Archive\n\n**Last reviewed:** 2020-01-01\n',
        encoding='utf-8',
    )
    # Override the registry with our test docs
    original_registry = module.DOC_REVIEW_REGISTRY
    module.DOC_REVIEW_REGISTRY = (
        module.DocReviewEntry('docs/working.md', 'working', 'when working changes'),
        module.DocReviewEntry(
            'docs/analysis/archived-2026-06-12.md', 'archive', 'when archive changes'
        ),
    )
    try:
        output = module.generate_docs_aging_dashboard(repo_root=tmp_path, stale_days=30)
        # Working-tier stale doc should be in the stale section
        assert 'docs/working.md' in output
        assert '### working' in output
        # Archive-tier doc should be in archive section, not stale section
        assert 'Archive Tier' in output
        assert 'docs/analysis/archived-2026-06-12.md' in output
    finally:
        module.DOC_REVIEW_REGISTRY = original_registry


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
