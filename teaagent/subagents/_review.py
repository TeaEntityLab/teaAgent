from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from teaagent.storage import atomic_write_text
from teaagent.subagents._isolation import _git_subprocess_env
from teaagent.subagents._types import SubagentLineage

_REVIEW_PATHSPEC = ['--', '.', ':!.teaagent']


@dataclass(frozen=True)
class SubagentReviewArtifact:
    review_id: str
    parent_run_id: str
    child_run_id: str
    created_at: str
    isolation: str
    patch_path: str
    status_path: str
    changed_files: list[str]
    worktree_path: Optional[str] = None
    container_path: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def capture_subagent_review(
    *,
    parent_root: Path,
    child_root: Path,
    parent_run_id: str,
    child_run_id: str,
    lineage: SubagentLineage,
) -> dict[str, Any] | None:
    """Persist an isolated child workspace diff before cleanup.

    Worktree/container subagents are intentionally cleaned up after execution.
    This artifact gives the parent run a stable patch to inspect and merge.
    """

    parent = parent_root.resolve()
    child = child_root.resolve()
    if parent == child:
        return None
    if not _is_git_worktree(child):
        return None

    # Intent-to-add lets `git diff HEAD` include untracked files in the patch.
    _git(child, ['add', '-N', *_REVIEW_PATHSPEC], check=False)
    diff = _git(child, ['diff', '--binary', 'HEAD', *_REVIEW_PATHSPEC], check=False)
    status = _git(child, ['status', '--porcelain=v1', *_REVIEW_PATHSPEC], check=False)
    if not diff.stdout.strip() and not status.stdout.strip():
        return None

    names = _git(child, ['diff', '--name-only', 'HEAD', *_REVIEW_PATHSPEC], check=False)
    changed_files = [line.strip() for line in names.stdout.splitlines() if line.strip()]
    review_id = _safe_segment(child_run_id) or _safe_segment(parent_run_id) or 'review'
    review_dir = (
        parent / '.teaagent' / 'subagent-reviews' / _safe_segment(parent_run_id)
    )
    review_dir.mkdir(parents=True, exist_ok=True)
    patch_file = review_dir / f'{review_id}.patch'
    status_file = review_dir / f'{review_id}.status'
    meta_file = review_dir / f'{review_id}.json'

    atomic_write_text(patch_file, diff.stdout)
    atomic_write_text(status_file, status.stdout)
    artifact = SubagentReviewArtifact(
        review_id=review_id,
        parent_run_id=parent_run_id,
        child_run_id=child_run_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        isolation=lineage.isolation,
        patch_path=patch_file.relative_to(parent).as_posix(),
        status_path=status_file.relative_to(parent).as_posix(),
        changed_files=changed_files,
        worktree_path=lineage.worktree_path,
        container_path=lineage.container_path,
    )
    atomic_write_text(meta_file, json.dumps(artifact.to_dict(), sort_keys=True))
    return artifact.to_dict()


def list_subagent_reviews(
    root: str | Path = '.', *, parent_run_id: Optional[str] = None
) -> list[dict[str, Any]]:
    base = Path(root).resolve() / '.teaagent' / 'subagent-reviews'
    if not base.exists():
        return []
    dirs = (
        [base / _safe_segment(parent_run_id)]
        if parent_run_id
        else sorted(base.iterdir())
    )
    reviews: list[dict[str, Any]] = []
    for directory in dirs:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob('*.json')):
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                payload['metadata_path'] = path.relative_to(
                    Path(root).resolve()
                ).as_posix()
                reviews.append(payload)
    return sorted(reviews, key=lambda row: str(row.get('created_at', '')), reverse=True)


def load_subagent_review(
    root: str | Path,
    review_id: str,
    *,
    parent_run_id: Optional[str] = None,
) -> dict[str, Any]:
    wanted = _safe_segment(review_id)
    for review in list_subagent_reviews(root, parent_run_id=parent_run_id):
        if review.get('review_id') == wanted:
            return review
    raise FileNotFoundError(f"subagent review '{review_id}' not found")


def check_subagent_review(
    root: str | Path,
    review_id: str,
    *,
    parent_run_id: Optional[str] = None,
    with_cost: bool = True,
) -> dict[str, Any]:
    """Check if a subagent review patch can be applied cleanly.

    Args:
        root: Workspace root.
        review_id: Review identifier.
        parent_run_id: Optional parent run ID filter.
        with_cost: If True (default), attach per-child cost ledger.

    Returns:
        Dict with ``ok``, ``status``, ``review``, ``stdout``, ``stderr``,
        and optionally ``cost_ledger``.
    """
    result = _run_review_patch(
        root, review_id, parent_run_id=parent_run_id, apply_patch=False
    )
    if with_cost and result.get('review'):
        child_run_id = result['review'].get('child_run_id', '')
        child_name = result['review'].get('review_id', child_run_id)[:12]
        if child_run_id:
            try:
                from teaagent.subagents._cost import build_child_cost_ledger

                ledger = build_child_cost_ledger(
                    Path(root).resolve(),
                    [(child_run_id, child_name)],
                )
                result['cost_ledger'] = ledger.to_dict()
            except Exception:
                pass
    return result


def apply_subagent_review(
    root: str | Path,
    review_id: str,
    *,
    parent_run_id: Optional[str] = None,
) -> dict[str, Any]:
    return _run_review_patch(
        root, review_id, parent_run_id=parent_run_id, apply_patch=True
    )


def _run_review_patch(
    root: str | Path,
    review_id: str,
    *,
    parent_run_id: Optional[str],
    apply_patch: bool,
) -> dict[str, Any]:
    workspace = Path(root).resolve()
    review = load_subagent_review(workspace, review_id, parent_run_id=parent_run_id)
    patch_path = (workspace / str(review['patch_path'])).resolve()
    try:
        patch_path.relative_to(workspace)
    except ValueError:
        return {
            'ok': False,
            'status': 'invalid_review',
            'review': review,
            'stdout': '',
            'stderr': 'review patch_path escapes workspace',
        }
    if not patch_path.is_file():
        return {
            'ok': False,
            'status': 'missing_patch',
            'review': review,
            'stdout': '',
            'stderr': f'review patch not found: {patch_path}',
        }
    cmd = ['git', 'apply']
    if apply_patch:
        cmd.append('--3way')
    else:
        cmd.append('--check')
    cmd.append(str(patch_path))
    result = subprocess.run(
        cmd,
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
        env=_git_subprocess_env(),
    )
    status = 'applied' if apply_patch and result.returncode == 0 else 'applicable'
    if result.returncode != 0:
        status = 'conflict' if apply_patch else 'not_applicable'
    return {
        'ok': result.returncode == 0,
        'status': status,
        'review': review,
        'stdout': result.stdout,
        'stderr': result.stderr,
    }


def _is_git_worktree(path: Path) -> bool:
    result = _git(path, ['rev-parse', '--is-inside-work-tree'], check=False)
    return result.returncode == 0 and result.stdout.strip() == 'true'


def _git(
    cwd: Path, args: list[str], *, check: bool
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ['git', *args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        env=_git_subprocess_env(),
    )


def _safe_segment(value: Optional[str]) -> str:
    raw = (value or '').strip()
    safe = re.sub(r'[^A-Za-z0-9_.-]+', '-', raw).strip('.-')
    return safe[:80]
