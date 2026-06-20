"""S-P2-2: explicit symlink rejection in ``_assert_paths_in_workspace``.

Defense in depth — the approval gate rejects symlinked path targets even
though the tool layer also rejects symlinks. This ensures the approval
gate cannot be bypassed via a symlink that resolves inside the workspace
root.
"""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from teaagent.approval_manager import (
    ApprovalManager,
    PermissionMode,
    ToolPermissionError,
)


def _manager(workspace: str) -> ApprovalManager:
    return ApprovalManager(
        permission_mode=PermissionMode.ALLOW,
        workspace_root=workspace,
    )


def test_symlink_in_path_value_is_rejected() -> None:
    """A path value that is a symlink is rejected before resolution."""
    with TemporaryDirectory() as tmp:
        real_dir = Path(tmp) / 'real'
        real_dir.mkdir()
        link = Path(tmp) / 'link'
        os.symlink(real_dir, link)

        manager = _manager(tmp)
        with pytest.raises(ToolPermissionError) as exc_info:
            manager._assert_paths_in_workspace(
                'workspace_write_file',
                'call-1',
                {'path': 'link'},
            )
        assert 'symlink' in str(exc_info.value).lower()


def test_symlink_in_named_path_key_is_rejected() -> None:
    """A named path-key value that is a symlink is rejected."""
    with TemporaryDirectory() as tmp:
        real_file = Path(tmp) / 'real.txt'
        real_file.write_text('data')
        link = Path(tmp) / 'link.txt'
        os.symlink(real_file, link)

        manager = _manager(tmp)
        with pytest.raises(ToolPermissionError) as exc_info:
            manager._assert_paths_in_workspace(
                'workspace_write_file',
                'call-2',
                {'file_path': 'link.txt'},
            )
        assert 'symlink' in str(exc_info.value).lower()


def test_non_symlink_path_within_root_is_allowed() -> None:
    """A regular (non-symlink) path within the workspace root is allowed."""
    with TemporaryDirectory() as tmp:
        (Path(tmp) / 'sub').mkdir()
        manager = _manager(tmp)
        # Should not raise.
        manager._assert_paths_in_workspace(
            'workspace_write_file',
            'call-3',
            {'path': 'sub/file.txt'},
        )


def test_symlink_resolving_inside_root_still_rejected() -> None:
    """A symlink whose target is inside the root is still rejected."""
    with TemporaryDirectory() as tmp:
        target = Path(tmp) / 'inside.txt'
        target.write_text('data')
        link = Path(tmp) / 'alias.txt'
        os.symlink(target, link)

        manager = _manager(tmp)
        with pytest.raises(ToolPermissionError) as exc_info:
            manager._assert_paths_in_workspace(
                'workspace_write_file',
                'call-4',
                {'path': 'alias.txt'},
            )
        assert 'symlink' in str(exc_info.value).lower()
