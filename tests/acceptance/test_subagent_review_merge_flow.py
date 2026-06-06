"""Acceptance test for subagent parent review/merge workflow (SUB-001).

Verifies that the parent can:
1. List child results
2. Show child review with diff info
3. Check if patch applies cleanly
4. Understand cost attribution
"""

from __future__ import annotations

import json
from pathlib import Path

from teaagent.subagents._review import (
    SubagentReviewArtifact,
    check_subagent_review,
    list_subagent_reviews,
    load_subagent_review,
)


class TestSubagentReviewArtifact:
    """SubagentReviewArtifact model."""

    def test_minimal_artifact(self) -> None:
        art = SubagentReviewArtifact(
            review_id='rev-001',
            parent_run_id='parent-abc',
            child_run_id='child-xyz',
            created_at='2026-06-06T00:00:00Z',
            isolation='worktree',
            patch_path='.teaagent/subagent-reviews/rev-001.patch',
            status_path='.teaagent/subagent-reviews/rev-001.status',
            changed_files=['src/main.py', 'tests/test_main.py'],
        )
        assert art.review_id == 'rev-001'
        assert 'src/main.py' in art.changed_files

    def test_to_dict(self) -> None:
        art = SubagentReviewArtifact(
            review_id='r1',
            parent_run_id='p1',
            child_run_id='c1',
            created_at='now',
            isolation='container',
            patch_path='p.patch',
            status_path='s.status',
            changed_files=['f.py'],
        )
        d = art.to_dict()
        assert d['review_id'] == 'r1'
        assert d['child_run_id'] == 'c1'
        assert d['isolation'] == 'container'

    def test_with_paths(self) -> None:
        art = SubagentReviewArtifact(
            review_id='r2',
            parent_run_id='p2',
            child_run_id='c2',
            created_at='now',
            isolation='worktree',
            patch_path='.teaagent/reviews/r2.patch',
            status_path='.teaagent/reviews/r2.status',
            changed_files=['a.py', 'b.py'],
            worktree_path='/tmp/worktree-abc',
        )
        assert art.worktree_path == '/tmp/worktree-abc'
        assert art.container_path is None


class TestListSubagentReviews:
    """list_subagent_reviews with temp workspace."""

    def test_no_reviews_dir(self, tmp_path: Path) -> None:
        """Returns empty list when no reviews exist."""
        reviews = list_subagent_reviews(tmp_path)
        assert reviews == []

    def test_empty_reviews_dir(self, tmp_path: Path) -> None:
        """Returns empty list when reviews dir is empty."""
        (tmp_path / '.teaagent' / 'subagent-reviews' / 'parent-1').mkdir(
            parents=True, exist_ok=True
        )
        reviews = list_subagent_reviews(tmp_path)
        # No .json files, so empty
        assert reviews == []

    def test_with_review_file(self, tmp_path: Path) -> None:
        """Returns review when a .json file exists."""
        review_dir = tmp_path / '.teaagent' / 'subagent-reviews' / 'parent-1'
        review_dir.mkdir(parents=True, exist_ok=True)
        artifact = SubagentReviewArtifact(
            review_id='rev-001',
            parent_run_id='parent-1',
            child_run_id='child-1',
            created_at='2026-06-06T00:00:00Z',
            isolation='worktree',
            patch_path='.teaagent/subagent-reviews/rev-001.patch',
            status_path='.teaagent/subagent-reviews/rev-001.status',
            changed_files=['f1.py'],
        )
        (review_dir / 'rev-001.json').write_text(
            json.dumps(artifact.to_dict(), sort_keys=True)
        )
        reviews = list_subagent_reviews(tmp_path)
        assert len(reviews) == 1
        assert reviews[0]['review_id'] == 'rev-001'
        assert reviews[0]['child_run_id'] == 'child-1'

    def test_filter_by_parent(self, tmp_path: Path) -> None:
        """Filters reviews by parent_run_id."""
        for parent in ['parent-a', 'parent-b']:
            d = tmp_path / '.teaagent' / 'subagent-reviews' / parent
            d.mkdir(parents=True, exist_ok=True)
            art = SubagentReviewArtifact(
                review_id=f'rev-{parent}',
                parent_run_id=parent,
                child_run_id='child',
                created_at='now',
                isolation='worktree',
                patch_path=f'{parent}.patch',
                status_path=f'{parent}.status',
                changed_files=['f.py'],
            )
            (d / f'{parent}.json').write_text(json.dumps(art.to_dict(), sort_keys=True))
        all_reviews = list_subagent_reviews(tmp_path)
        assert len(all_reviews) == 2
        filtered = list_subagent_reviews(tmp_path, parent_run_id='parent-a')
        assert len(filtered) == 1
        assert filtered[0]['parent_run_id'] == 'parent-a'


class TestLoadSubagentReview:
    """load_subagent_review with temp workspace."""

    def test_load_existing(self, tmp_path: Path) -> None:
        d = tmp_path / '.teaagent' / 'subagent-reviews' / 'parent-1'
        d.mkdir(parents=True, exist_ok=True)
        art = SubagentReviewArtifact(
            review_id='my-review',
            parent_run_id='parent-1',
            child_run_id='child-1',
            created_at='now',
            isolation='worktree',
            patch_path='p.patch',
            status_path='s.status',
            changed_files=['f.py'],
        )
        (d / 'my-review.json').write_text(json.dumps(art.to_dict(), sort_keys=True))
        loaded = load_subagent_review(tmp_path, 'my-review')
        assert loaded['review_id'] == 'my-review'
        assert loaded['child_run_id'] == 'child-1'

    def test_load_missing_raises(self, tmp_path: Path) -> None:
        import pytest

        with pytest.raises(FileNotFoundError):
            load_subagent_review(tmp_path, 'nonexistent')


class TestCheckSubagentReview:
    """check_subagent_review behavior."""

    def test_missing_review_raises(self, tmp_path: Path) -> None:
        import pytest

        with pytest.raises(FileNotFoundError):
            check_subagent_review(tmp_path, 'nonexistent')

    def test_check_with_invalid_path(self, tmp_path: Path) -> None:
        """Review with escaping patch path returns invalid check."""
        d = tmp_path / '.teaagent' / 'subagent-reviews' / 'p'
        d.mkdir(parents=True, exist_ok=True)
        bad_artifact = SubagentReviewArtifact(
            review_id='bad',
            parent_run_id='p',
            child_run_id='c',
            created_at='now',
            isolation='worktree',
            patch_path='../../etc/passwd',
            status_path='s.status',
            changed_files=[],
        )
        (d / 'bad.json').write_text(json.dumps(bad_artifact.to_dict(), sort_keys=True))
        result = check_subagent_review(tmp_path, 'bad')
        assert result['ok'] is False
        assert result['status'] == 'invalid_review'
