# test-type: adversarial
"""Q6 (approval split-plan, owner decision 2026-10-27): path checks fail closed on OSError.

Findings F3 and F5 in docs/reviews/approval-manager-split-risk.md: the symlink
component check and the protected-skill check used to return "allow" when the
filesystem raised OSError. An error while checking a path means the path cannot
be shown to be safe, so both checks must block.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from teaagent.approval.manager import (
    ApprovalManager,
    PermissionMode,
    is_protected_skill_path,
)
from teaagent.errors import DenialReasonCode, ToolPermissionError


def _raise_oserror(self: Path, *args: object, **kwargs: object) -> bool:
    raise OSError('simulated filesystem error')


def _manager(workspace: Path) -> ApprovalManager:
    return ApprovalManager(
        permission_mode=PermissionMode.ALLOW,
        workspace_root=str(workspace),
    )


def test_symlink_component_check_blocks_when_is_symlink_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_has_symlink_component reports a component as unsafe when lstat fails."""
    monkeypatch.setattr(type(tmp_path), 'is_symlink', _raise_oserror)

    assert ApprovalManager._has_symlink_component(tmp_path, 'notes/todo.txt') is True


def test_path_argument_is_blocked_when_symlink_check_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An in-workspace path whose symlink check errors is denied, not allowed."""
    manager = _manager(tmp_path)
    monkeypatch.setattr(type(tmp_path), 'is_symlink', _raise_oserror)

    with pytest.raises(ToolPermissionError) as exc_info:
        manager._assert_paths_in_workspace(
            'workspace_write_file',
            'call-oserror-1',
            {'path': 'notes/todo.txt'},
        )
    assert exc_info.value.reason_code == DenialReasonCode.SYMLINK_BLOCKED


def test_is_protected_skill_path_blocks_when_resolve_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """is_protected_skill_path treats an unresolvable skill path as protected."""
    target = tmp_path / '.claude' / 'skills' / 'helper.md'
    monkeypatch.setattr(type(target), 'resolve', _raise_oserror)

    assert is_protected_skill_path(tmp_path, target) is True


def test_skill_write_is_blocked_when_protection_check_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A write whose protected-skill check errors is denied with SKILL_WRITE_BLOCKED."""
    # Stub the opt-in lookup so only the protected-path check touches resolve().
    monkeypatch.setattr(
        'teaagent.approval.manager._is_skill_dev_opt_in',
        lambda _root: False,
    )
    manager = _manager(tmp_path)
    original_resolve = type(tmp_path).resolve

    def _resolve_fails_for_skill_dirs(
        self: Path, *args: object, **kwargs: object
    ) -> Path:
        # Only the skill target fails; the workspace root still resolves.
        if 'skills' in self.parts:
            raise OSError('simulated filesystem error')
        return original_resolve(self, *args, **kwargs)  # type: ignore[no-any-return]

    monkeypatch.setattr(type(tmp_path), 'resolve', _resolve_fails_for_skill_dirs)

    with pytest.raises(ToolPermissionError) as exc_info:
        manager._assert_skill_path_not_protected(
            'workspace_write_file',
            'call-oserror-2',
            {'path': '.claude/skills/helper.md'},
        )
    assert exc_info.value.reason_code == DenialReasonCode.SKILL_WRITE_BLOCKED


def test_outside_workspace_is_still_not_protected(tmp_path: Path) -> None:
    """ValueError from relative_to (path outside the workspace) keeps returning False."""
    workspace = tmp_path / 'ws'
    workspace.mkdir()
    outside = tmp_path / 'elsewhere' / '.claude' / 'skills' / 'helper.md'

    assert is_protected_skill_path(workspace, outside) is False
