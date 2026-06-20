"""S-P2-3: GitBranchSandbox run_id sanitization tests.

Ensures that a ``run_id`` containing unsafe characters (path separators, shell
metacharacters, git ref syntax, etc.) is sanitized to ``[A-Za-z0-9._-]`` before
being embedded in a branch name.
"""

from __future__ import annotations

from teaagent.sandbox._git_branch import GitBranchSandbox, _sanitize_run_id


def test_sanitize_run_id_strips_unsafe_characters() -> None:
    assert _sanitize_run_id('safe-run_id.123') == 'safe-run_id.123'
    assert _sanitize_run_id('run/../../etc') == 'run....etc'
    assert _sanitize_run_id('run;rm -rf /') == 'runrm-rf'
    assert _sanitize_run_id('run$(whoami)') == 'runwhoami'
    assert _sanitize_run_id('run`id`') == 'runid'
    assert _sanitize_run_id('run|nc evil') == 'runncevil'
    assert _sanitize_run_id('a b\tc') == 'abc'


def test_sanitize_run_id_empty_fallback() -> None:
    assert _sanitize_run_id('') == 'run'
    assert _sanitize_run_id(';;;') == 'run'
    assert _sanitize_run_id('/;|') == 'run'


def test_sanitize_run_id_preserves_allowed_punctuation() -> None:
    assert _sanitize_run_id('my.run-id_v2') == 'my.run-id_v2'


def test_git_branch_sandbox_uses_sanitized_run_id(tmp_path) -> None:
    sandbox = GitBranchSandbox(root=tmp_path, run_id='run/../../etc;rm -rf /')
    assert sandbox._branch_name == 'teaagent-sandbox-run....etcrm-rf'
    # No path separators or shell metacharacters leak into the branch name.
    assert '/' not in sandbox._branch_name
    assert ';' not in sandbox._branch_name
    assert ' ' not in sandbox._branch_name
    assert '$' not in sandbox._branch_name


def test_git_branch_sandbox_safe_run_id_unchanged(tmp_path) -> None:
    sandbox = GitBranchSandbox(root=tmp_path, run_id='abc-123_run.456')
    assert sandbox._branch_name == 'teaagent-sandbox-abc-123_run.456'


def test_git_branch_sandbox_empty_run_id_falls_back(tmp_path) -> None:
    sandbox = GitBranchSandbox(root=tmp_path, run_id='')
    assert sandbox._branch_name == 'teaagent-sandbox-run'
