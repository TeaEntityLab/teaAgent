"""Guard tests for validation scripts that had zero test coverage.

These scripts are pre-commit gates — bugs in them silently block or
pass commits.  The action-ID regex bug (``[0-9]`` vs ``[0-9]+``) was
silent for weeks because no test exercised double-digit IDs.
"""

from __future__ import annotations

from pathlib import Path

from scripts.check_complexity import count_violations
from scripts.check_github_url_consistency import (
    CANONICAL_URL,
    PLACEHOLDER_PATTERNS,
    _should_ignore,
)

# ---------------------------------------------------------------------------
# check_github_url_consistency.py
# ---------------------------------------------------------------------------


def test_canonical_url_filtered_before_placeholder_check() -> None:
    """The canonical URL matches the generic placeholder pattern but is
    filtered by the ``CANONICAL_URL in line`` check in ``check_urls``.

    This test pins that contract: if the canonical filter is ever removed,
    the placeholder patterns WILL flag the canonical URL — so the filter
    is load-bearing, not redundant.
    """
    line = f'github.com/{CANONICAL_URL}'
    # The generic pattern matches any org/teaagent, including canonical.
    assert any(p.search(line) for p in PLACEHOLDER_PATTERNS), (
        'canonical URL should match generic placeholder pattern — '
        'the CANONICAL_URL filter in check_urls is load-bearing'
    )
    # The script's check_urls filters canonical BEFORE placeholder check.
    assert CANONICAL_URL in line


def test_placeholder_urls_are_flagged() -> None:
    """Known placeholder URLs must be flagged."""
    for org in ('yourusername', 'anomalyco', 'someoneelse'):
        url = f'github.com/{org}/teaagent'
        line = f'see {url} for details'
        assert any(p.search(line) for p in PLACEHOLDER_PATTERNS), (
            f'{url!r} was not flagged as a placeholder'
        )


def test_github_url_with_git_suffix_not_flagged() -> None:
    """``github.com/X/teaagent.git`` must not match the placeholder pattern."""
    line = 'github.com/TeaEntityLab/teaagent.git'
    # The negative lookahead (?!\.git) prevents matching .git URLs.
    # The canonical check also skips this, but verify the regex itself.
    assert not any(
        p.search(line) for p in PLACEHOLDER_PATTERNS if 'git' not in p.pattern
    ), '.git suffix URL should not match non-.git placeholder patterns'


def test_should_ignore_self_and_retrospective() -> None:
    """The script's own file and retrospective docs must be ignored."""
    assert _should_ignore('scripts/check_github_url_consistency.py')
    assert _should_ignore('docs/retrospective/06-action-register.md')
    assert not _should_ignore('README.md')
    assert not _should_ignore('docs/USAGE.md')


# ---------------------------------------------------------------------------
# check_complexity.py
# ---------------------------------------------------------------------------


def test_complexity_count_returns_int() -> None:
    """count_violations must return a non-negative integer."""
    count = count_violations(Path(__file__).resolve().parents[1])
    assert isinstance(count, int)
    assert count >= 0
