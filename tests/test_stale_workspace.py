from __future__ import annotations

import subprocess
from pathlib import Path

from teaagent.cockpit import StaleWorkspaceReport, assess_stale_workspace


def _init_git_repo(path: Path) -> None:
    subprocess.run(['git', 'init', '--initial-branch=main'], cwd=path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'test'], cwd=path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@test.local'], cwd=path, check=True, capture_output=True)


def _make_initial_commit(path: Path) -> None:
    (path / 'README.md').write_text('# test\n')
    subprocess.run(['git', 'add', 'README.md'], cwd=path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'initial'], cwd=path, check=True, capture_output=True)


# ── test_stale_report_dataclass ─────────────────────────────────────────────


def test_stale_report_dataclass():
    """Construct StaleWorkspaceReport with all fields, verify defaults."""
    report = StaleWorkspaceReport()
    assert report.dirty_git is False
    assert report.branch == ''
    assert report.diverged_from_main is False
    assert report.commits_behind == 0
    assert report.commits_ahead == 0
    assert report.pending_approvals == 0
    assert report.candidate_count == 0

    partial = StaleWorkspaceReport(dirty_git=True, branch='feature/x', commits_ahead=3)
    assert partial.dirty_git is True
    assert partial.branch == 'feature/x'
    assert partial.diverged_from_main is False
    assert partial.commits_behind == 0
    assert partial.commits_ahead == 3
    assert partial.pending_approvals == 0
    assert partial.candidate_count == 0

    full = StaleWorkspaceReport(
        dirty_git=True,
        branch='dev',
        diverged_from_main=True,
        commits_behind=5,
        commits_ahead=2,
        pending_approvals=1,
        candidate_count=3,
    )
    d = full.to_dict()
    assert d['dirty_git'] is True
    assert d['branch'] == 'dev'
    assert d['diverged_from_main'] is True
    assert d['commits_behind'] == 5
    assert d['commits_ahead'] == 2
    assert d['pending_approvals'] == 1
    assert d['candidate_count'] == 3


# ── test_assess_clean_workspace ─────────────────────────────────────────────


def test_assess_clean_workspace(tmp_path: Path):
    """Init a git repo, make initial commit, assert clean state."""
    _init_git_repo(tmp_path)
    _make_initial_commit(tmp_path)

    report = assess_stale_workspace(tmp_path)
    assert report.dirty_git is False
    assert report.branch == 'main'
    assert report.diverged_from_main is False  # no origin/main
    assert report.commits_behind == 0
    assert report.commits_ahead == 0
    assert report.pending_approvals == 0
    assert report.candidate_count == 0


# ── test_assess_dirty_workspace ─────────────────────────────────────────────


def test_assess_dirty_workspace(tmp_path: Path):
    """Create a dirty file, assert dirty_git=True."""
    _init_git_repo(tmp_path)
    _make_initial_commit(tmp_path)

    (tmp_path / 'dirty.txt').write_text('uncommitted\n')
    report = assess_stale_workspace(tmp_path)
    assert report.dirty_git is True


# ── test_assess_branch_name ─────────────────────────────────────────────────


def test_assess_branch_name(tmp_path: Path):
    """Check that branch detection works."""
    _init_git_repo(tmp_path)
    _make_initial_commit(tmp_path)

    subprocess.run(['git', 'checkout', '-b', 'feature/foo'], cwd=tmp_path, check=True, capture_output=True)
    report = assess_stale_workspace(tmp_path)
    assert report.branch == 'feature/foo'


# ── test_assess_no_git_repo ─────────────────────────────────────────────────


def test_assess_no_git_repo(tmp_path: Path):
    """Gracefully handle non-git directory — returns clean defaults."""
    report = assess_stale_workspace(tmp_path)
    assert report.dirty_git is False
    assert report.branch == ''
    assert report.diverged_from_main is False
    assert report.commits_behind == 0
    assert report.commits_ahead == 0
    assert report.pending_approvals == 0
    assert report.candidate_count == 0


# ── test_assess_divergence ──────────────────────────────────────────────────


def test_assess_divergence_from_main(tmp_path: Path):
    """Set up origin/main with additional commit to test divergence detection."""
    _init_git_repo(tmp_path)
    _make_initial_commit(tmp_path)

    # Create a local commit so branch is ahead
    (tmp_path / 'local.txt').write_text('local\n')
    subprocess.run(['git', 'add', 'local.txt'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'local change'], cwd=tmp_path, check=True, capture_output=True)

    # Create origin/main reference pointing back to initial commit
    main_hash = subprocess.run(
        ['git', 'rev-parse', 'main~1'], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    subprocess.run(
        ['git', 'update-ref', 'refs/remotes/origin/main', main_hash], cwd=tmp_path, check=True
    )

    report = assess_stale_workspace(tmp_path)
    assert report.diverged_from_main is True
    # Behind from perspective of local vs origin/main: 0 behind, 1 ahead
    assert report.commits_ahead == 1
    assert report.commits_behind == 0


# ── test_assess_behind_main ────────────────────────────────────────────────


def test_assess_behind_main(tmp_path: Path):
    """Set up origin/main ahead to test behind detection."""
    _init_git_repo(tmp_path)
    _make_initial_commit(tmp_path)

    # Create origin/main pointing to a future commit (by making commit, then rewinding local)
    main_hash = subprocess.run(
        ['git', 'rev-parse', 'HEAD'], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()

    (tmp_path / 'upstream.txt').write_text('upstream\n')
    subprocess.run(['git', 'add', 'upstream.txt'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'upstream change'], cwd=tmp_path, check=True, capture_output=True)

    # Point origin/main to the upstream commit, rewind local to original
    upstream_hash = subprocess.run(
        ['git', 'rev-parse', 'HEAD'], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    subprocess.run(['git', 'update-ref', 'refs/remotes/origin/main', upstream_hash], cwd=tmp_path, check=True)
    subprocess.run(['git', 'reset', '--hard', main_hash], cwd=tmp_path, check=True, capture_output=True)

    report = assess_stale_workspace(tmp_path)
    assert report.diverged_from_main is True
    assert report.commits_behind == 1
    assert report.commits_ahead == 0


# ── test_assess_pending_approvals ───────────────────────────────────────────


def test_assess_pending_approvals(tmp_path: Path):
    """Quarantine JSONL with entries produces pending_approvals > 0."""
    tea_dir = tmp_path / '.teaagent'
    tea_dir.mkdir()
    quarantine = tea_dir / 'memory-quarantine.jsonl'
    quarantine.write_text(
        '{"memory_id":"a","content":"x","quarantine":true}\n'
        '{"memory_id":"b","content":"y","quarantine":true}\n'
    )
    report = assess_stale_workspace(tmp_path)
    assert report.pending_approvals == 2


# ── test_assess_candidate_count ─────────────────────────────────────────────


def test_assess_candidate_count(tmp_path: Path):
    """Skill candidates with non-installed status are counted."""
    candidates_dir = tmp_path / '.teaagent' / 'skill-candidates'
    candidates_dir.mkdir(parents=True)

    import json

    for cid, status in [
        ('aa', 'proposed'),
        ('bb', 'review_passed'),
        ('cc', 'installed'),
        ('dd', 'eval_failed'),
    ]:
        d = candidates_dir / cid
        d.mkdir()
        (d / 'candidate.json').write_text(
            json.dumps({'candidate_id': cid, 'name': cid, 'description': '', 'status': status})
        )
    report = assess_stale_workspace(tmp_path)
    # installed should not be counted; 3 unreviewed
    assert report.candidate_count == 3


# ── test_assess_empty_quarantine ────────────────────────────────────────────


def test_assess_empty_quarantine(tmp_path: Path):
    """Empty quarantine directory yields 0 pending approvals."""
    tea_dir = tmp_path / '.teaagent'
    tea_dir.mkdir()
    # No quarantine file exists
    report = assess_stale_workspace(tmp_path)
    assert report.pending_approvals == 0


# ── test_assess_no_candidates_dir ───────────────────────────────────────────


def test_assess_no_candidates_dir(tmp_path: Path):
    """No skill-candidates directory yields candidate_count == 0."""
    report = assess_stale_workspace(tmp_path)
    assert report.candidate_count == 0
