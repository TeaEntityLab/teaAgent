"""Shared documentation tier classification (DOW-021 / DOW-023)."""

from __future__ import annotations

import re

_ARCHIVE_DATE_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}')

# Paths relative to docs/ (no leading docs/ prefix).
WORKING_CURRENT_TRUTH_DOCS = frozenset(
    {
        'analysis/active-findings-status-ledger-2026-06-06.md',
    }
)


def normalize_docs_rel_path(rel_path: str) -> str:
    """Normalize doc paths from registry (docs/...) or inventory forms."""
    path = rel_path.replace('\\', '/').lstrip('/')
    if path.startswith('docs/'):
        return path[len('docs/') :]
    return path


def is_working_current_truth(rel_path: str) -> bool:
    return normalize_docs_rel_path(rel_path) in WORKING_CURRENT_TRUTH_DOCS


def is_archive_tier(rel_path: str) -> bool:
    """Return True if doc is archive-tier (dated, not in working override)."""
    if is_working_current_truth(rel_path):
        return False
    return bool(_ARCHIVE_DATE_PATTERN.search(rel_path))
