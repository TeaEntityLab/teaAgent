# test-type: behavior
"""Tests for documentation aging dashboard."""

from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

from test_support import repo_is_shallow


def _load_module():
    scripts_dir = Path(__file__).resolve().parents[1] / 'scripts'
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    script = scripts_dir / 'report_docs_aging.py'
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
    if repo_is_shallow():
        pytest.skip(
            reason='shallow clone: docs aging check needs full git history (actions/checkout fetch-depth: 0)'
        )
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


def test_corpus_cost_section_counts_full_docs_tree(tmp_path: Path) -> None:
    """B-04: corpus-cost signal must walk all of docs/, not the curated
    registry — and flag working-tier docs unreferenced by INDEX.md."""
    module = _load_module()
    docs = tmp_path / 'docs'
    docs.mkdir()
    (docs / 'INDEX.md').write_text('# Index\n\n[linked](linked.md)\n', encoding='utf-8')
    (docs / 'linked.md').write_text('# Linked\n', encoding='utf-8')
    (docs / 'orphan.md').write_text('# Orphan\n', encoding='utf-8')
    (docs / 'archive').mkdir()
    (docs / 'archive' / 'old-2020-01-01.md').write_text('# Old\n', encoding='utf-8')

    lines = module._corpus_cost_section(tmp_path)
    text = '\n'.join(lines)
    assert 'Total docs:** 4' in text
    assert 'Live corpus (non-archive):** 3' in text
    assert 'unreferenced by INDEX.md:** 1' in text
    assert 'orphan.md' in text
    assert 'linked.md' not in text.split('Dead-weight')[-1]


def test_archive_growth_buckets_by_first_add_month() -> None:
    """Synthetic git-log input: earliest add month wins for re-added paths,
    only archive paths are counted, untracked paths are skipped, and only the
    six most recent months present are reported (oldest first)."""
    module = _load_module()
    log_lines = [
        '@@commit 2026-06',
        '',
        'docs/analysis/a-2026-06-01.md',
        'docs/cli.md',
        '',
        '@@commit 2026-05',
        '',
        'docs/analysis/a-2026-06-01.md',
        'docs/analysis/b-2026-05-02.md',
        '',
        '@@commit 2026-01',
        '',
        'docs/analysis/c-2026-01-01.md',
        '',
    ]
    first = module._first_add_months(log_lines)
    assert first['docs/analysis/a-2026-06-01.md'] == '2026-05'
    assert first['docs/cli.md'] == '2026-06'

    archive = [
        'docs/analysis/a-2026-06-01.md',
        'docs/analysis/b-2026-05-02.md',
        'docs/analysis/c-2026-01-01.md',
        'docs/analysis/untracked-2026-07-01.md',
    ]
    assert module._archive_growth(first, archive) == [('2026-01', 1), ('2026-05', 2)]

    eight_months = {
        f'docs/x-{month}.md': month
        for month in (
            '2025-10',
            '2025-11',
            '2025-12',
            '2026-01',
            '2026-02',
            '2026-03',
            '2026-04',
            '2026-05',
        )
    }
    growth = module._archive_growth(eight_months, list(eight_months))
    assert [month for month, _ in growth] == [
        '2025-12',
        '2026-01',
        '2026-02',
        '2026-03',
        '2026-04',
        '2026-05',
    ]


def test_real_dashboard_reports_archive_growth() -> None:
    if repo_is_shallow():
        pytest.skip(
            reason='shallow clone: archive growth needs full git history (actions/checkout fetch-depth: 0)'
        )
    root = Path(__file__).resolve().parents[1]
    module = _load_module()
    output = module.generate_docs_aging_dashboard(repo_root=root)
    assert '### Archive-tier growth (files added per month, last 6 months)' in output
    assert '| 2026-' in output
