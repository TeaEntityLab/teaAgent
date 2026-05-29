from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from teaagent.subagents._review import (
    SubagentReviewArtifact,
    _safe_segment,
    list_subagent_reviews,
    load_subagent_review,
)


class TestSafeSegment:
    def test_preserves_alphanumeric(self) -> None:
        assert _safe_segment('hello-world_123') == 'hello-world_123'

    def test_replaces_special_chars(self) -> None:
        assert _safe_segment('run/123:test') == 'run-123-test'

    def test_truncates_to_80_chars(self) -> None:
        long_str = 'a' * 100
        assert len(_safe_segment(long_str)) == 80

    def test_empty_returns_empty(self) -> None:
        assert _safe_segment('') == ''

    def test_none_returns_empty(self) -> None:
        assert _safe_segment(None) == ''


class TestSubagentReviewArtifact:
    def test_to_dict(self) -> None:
        artifact = SubagentReviewArtifact(
            review_id='rev-1',
            parent_run_id='parent-1',
            child_run_id='child-1',
            created_at='2025-01-01T00:00:00',
            isolation='worktree',
            patch_path='reviews/parent-1/rev-1.patch',
            status_path='reviews/parent-1/rev-1.status',
            changed_files=['README.md', 'src/main.py'],
        )
        d = artifact.to_dict()
        assert d['review_id'] == 'rev-1'
        assert d['isolation'] == 'worktree'
        assert d['changed_files'] == ['README.md', 'src/main.py']


class TestListSubagentReviews:
    def test_returns_empty_when_no_reviews_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            reviews = list_subagent_reviews(tmp)
            assert reviews == []

    def test_lists_reviews(self) -> None:
        import json
        from datetime import datetime, timezone

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            reviews_dir = root / '.teaagent' / 'subagent-reviews' / 'parent-1'
            reviews_dir.mkdir(parents=True)

            artifact = {
                'review_id': 'rev-1',
                'parent_run_id': 'parent-1',
                'child_run_id': 'child-1',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'isolation': 'worktree',
                'patch_path': 'reviews/parent-1/rev-1.patch',
                'status_path': 'reviews/parent-1/rev-1.status',
                'changed_files': [],
            }
            (reviews_dir / 'rev-1.json').write_text(
                json.dumps(artifact), encoding='utf-8'
            )

            reviews = list_subagent_reviews(root)
            assert len(reviews) == 1
            assert reviews[0]['review_id'] == 'rev-1'

    def test_filter_by_parent_run_id(self) -> None:
        import json

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            d1 = root / '.teaagent' / 'subagent-reviews' / 'parent-1'
            d2 = root / '.teaagent' / 'subagent-reviews' / 'parent-2'
            d1.mkdir(parents=True)
            d2.mkdir(parents=True)

            for d in (d1, d2):
                (d / 'rev.json').write_text(
                    json.dumps(
                        {
                            'review_id': 'rev',
                            'parent_run_id': d.name,
                            'child_run_id': 'c',
                            'created_at': '2025-01-01T00:00:00',
                            'isolation': 'shared',
                            'patch_path': 'p.patch',
                            'status_path': 's.status',
                            'changed_files': [],
                        }
                    ),
                    encoding='utf-8',
                )

            reviews_p1 = list_subagent_reviews(root, parent_run_id='parent-1')
            assert len(reviews_p1) == 1

    def test_skips_corrupt_json(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root / '.teaagent' / 'subagent-reviews' / 'parent-1'
            d.mkdir(parents=True)
            (d / 'bad.json').write_text('{corrupt}', encoding='utf-8')

            reviews = list_subagent_reviews(root)
            assert reviews == []


class TestLoadSubagentReview:
    def test_raises_on_missing_review(self) -> None:
        with TemporaryDirectory() as tmp, pytest.raises(FileNotFoundError):
            load_subagent_review(tmp, 'nonexistent')

    def test_loads_existing_review(self) -> None:
        import json

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root / '.teaagent' / 'subagent-reviews' / 'parent-1'
            d.mkdir(parents=True)
            (d / 'rev-1.json').write_text(
                json.dumps(
                    {
                        'review_id': 'rev-1',
                        'parent_run_id': 'parent-1',
                        'child_run_id': 'c',
                        'created_at': '2025-01-01T00:00:00',
                        'isolation': 'worktree',
                        'patch_path': 'p.patch',
                        'status_path': 's.status',
                        'changed_files': ['f1.txt'],
                    }
                ),
                encoding='utf-8',
            )

            review = load_subagent_review(root, 'rev-1', parent_run_id='parent-1')
            assert review['review_id'] == 'rev-1'
            assert review['changed_files'] == ['f1.txt']
