"""Acceptance tests for Lore-compliant commit message generation."""

from __future__ import annotations

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from teaagent.workspace_tools._git import GitToolConfig, git_add


def _init_repo(root: Path) -> None:
    subprocess.run(['git', '-C', str(root), 'init'], check=True, capture_output=True)
    subprocess.run(
        ['git', '-C', str(root), 'config', 'user.email', 'test@test.com'],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', '-C', str(root), 'config', 'user.name', 'Test'],
        check=True,
        capture_output=True,
    )


def test_generate_lore_commit_message() -> None:
    """
    Verify that a commit message follows the Lore/OmX format:
    - Summary
    - Why/What/How
    - Session ID (optional but recommended)
    - OmX Co-author trailer
    """
    with TemporaryDirectory() as td:
        root = Path(td)
        _init_repo(root)
        (root / 'feature.py').write_text('print("hello")', encoding='utf-8')

        config = GitToolConfig(root=root)
        git_add(config, '.')

        # We expect a new way to commit or a helper that generates the message
        # For now, let's assume we want a tool that can synthesize this.
        # We will implement 'lore_commit' in teaagent/workspace_tools/_git.py
        from teaagent.workspace_tools._git import git_lore_commit

        session_id = '019e31d8-c21d-7d60-8767-c4c728f68ebb'
        result = git_lore_commit(
            config,
            summary='Add hello world feature',
            why='User requested a greeting.',
            what='Added feature.py with print statement.',
            session_id=session_id,
        )

        assert result['exit_code'] == 0

        # Verify the actual commit message in git history
        msg = subprocess.run(
            ['git', '-C', str(root), 'log', '-1', '--format=%B'],
            capture_output=True,
            text=True,
            check=True,
        ).stdout

        assert 'Add hello world feature' in msg
        assert 'Why: User requested a greeting.' in msg
        assert 'What: Added feature.py with print statement.' in msg
        assert f'Session-ID: {session_id}' in msg
        assert 'Co-authored-by: OmX <omx@oh-my-codex.dev>' in msg
