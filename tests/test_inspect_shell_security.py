"""SEC-10: Verify inspect-safe shell allowlist cannot read sensitive files.

cat, head, and tail must NOT be in _INSPECT_EXECUTABLES because they can
read arbitrary files (SSH keys, .env, /etc/shadow) without triggering the
approval flow.  Only the commands listed in _INSPECT_EXECUTABLES may run
without a mutate-level approval.
"""

from __future__ import annotations

import pytest

from teaagent.workspace_tools._config import WorkspaceToolConfig
from teaagent.workspace_tools._shell import (
    _INSPECT_EXECUTABLES,
    classify_shell_command_policy,
    run_shell_inspect,
)

# ---------------------------------------------------------------------------
# Allowlist membership assertions
# ---------------------------------------------------------------------------


def test_cat_not_in_inspect_allowlist():
    assert 'cat' not in _INSPECT_EXECUTABLES, (
        'cat is in _INSPECT_EXECUTABLES — it can read arbitrary files including '
        '~/.ssh/id_rsa, .env, and /etc/shadow without a mutate-level approval'
    )


def test_head_not_in_inspect_allowlist():
    assert 'head' not in _INSPECT_EXECUTABLES, (
        'head is in _INSPECT_EXECUTABLES — it can read the first N lines of any file'
    )


def test_tail_not_in_inspect_allowlist():
    assert 'tail' not in _INSPECT_EXECUTABLES, (
        'tail is in _INSPECT_EXECUTABLES — it can read the last N lines of any file'
    )


# ---------------------------------------------------------------------------
# Policy classification: sensitive file paths must be classified 'mutate'
# ---------------------------------------------------------------------------


def test_inspect_shell_cannot_read_ssh_keys():
    """cat ~/.ssh/id_rsa must be classified as mutate, never inspect.

    Two independent mechanisms block it:
    1. 'cat' is not in _INSPECT_EXECUTABLES.
    2. '~/.ssh/id_rsa' starts with '~' and is caught by shell_arg_escapes_workspace.
    Either alone is sufficient; both must hold.
    """
    assert classify_shell_command_policy('cat ~/.ssh/id_rsa') == 'mutate'
    assert classify_shell_command_policy('cat ~/.ssh/id_ed25519') == 'mutate'
    assert classify_shell_command_policy('cat ~/.ssh/authorized_keys') == 'mutate'


def test_inspect_shell_cannot_read_env_files():
    assert classify_shell_command_policy('cat .env') == 'mutate'
    assert classify_shell_command_policy('head -n 5 .env.production') == 'mutate'
    assert classify_shell_command_policy('tail -n 10 .env.local') == 'mutate'


def test_inspect_shell_cannot_read_shadow():
    assert classify_shell_command_policy('cat /etc/shadow') == 'mutate'
    assert classify_shell_command_policy('head /etc/passwd') == 'mutate'


# ---------------------------------------------------------------------------
# run_shell_inspect rejects these commands at execution time
# ---------------------------------------------------------------------------


def test_run_shell_inspect_raises_for_cat(tmp_path):
    config = WorkspaceToolConfig(root=tmp_path)
    with pytest.raises(ValueError, match='not inspect-safe'):
        run_shell_inspect(config, {'command': 'cat README.md'})
    # Verify that cat is not in the allowlist
    assert 'cat' not in _INSPECT_EXECUTABLES


def test_run_shell_inspect_raises_for_head(tmp_path):
    config = WorkspaceToolConfig(root=tmp_path)
    with pytest.raises(ValueError, match='not inspect-safe'):
        run_shell_inspect(config, {'command': 'head -n 3 README.md'})
    # Verify that head is not in the allowlist
    assert 'head' not in _INSPECT_EXECUTABLES
