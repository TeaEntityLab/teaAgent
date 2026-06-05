"""DSK-P0-002: Direct Active-Skill Write Quarantine tests.

Verify that writes to active skill directories are blocked in the
approval layer with actionable error messages, while the candidate
install path and explicit dev opt-in continue to work.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from teaagent.approval_manager import (
    ApprovalManager,
    PermissionMode,
    _is_skill_dev_opt_in,
    is_protected_skill_path,
)
from teaagent.errors import DenialReasonCode, ToolPermissionError


class TestIsProtectedSkillPath:
    def test_opencode_skill_dir_is_protected(self, tmp_path: Path) -> None:
        target = tmp_path / '.opencode' / 'skill' / 'rss' / 'SKILL.md'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
        assert is_protected_skill_path(tmp_path, target) is True

    def test_opencode_skills_dir_is_protected(self, tmp_path: Path) -> None:
        target = tmp_path / '.opencode' / 'skills' / 'rss' / 'SKILL.md'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
        assert is_protected_skill_path(tmp_path, target) is True

    def test_claude_skills_dir_is_protected(self, tmp_path: Path) -> None:
        target = tmp_path / '.claude' / 'skills' / 'test-skill' / 'SKILL.md'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
        assert is_protected_skill_path(tmp_path, target) is True

    def test_config_agent_skills_dir_is_protected(self, tmp_path: Path) -> None:
        target = tmp_path / '.config' / 'agent' / 'skills' / 'test-skill' / 'SKILL.md'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
        assert is_protected_skill_path(tmp_path, target) is True

    def test_candidate_path_is_not_protected(self, tmp_path: Path) -> None:
        target = tmp_path / '.teaagent' / 'skill-candidates' / 'test-skill' / 'SKILL.md'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
        assert is_protected_skill_path(tmp_path, target) is False

    def test_regular_source_file_is_not_protected(self, tmp_path: Path) -> None:
        target = tmp_path / 'src' / 'main.py'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
        assert is_protected_skill_path(tmp_path, target) is False

    def test_outside_workspace_is_not_protected(self, tmp_path: Path) -> None:
        target = Path('/tmp/something/.opencode/skill/SKILL.md')
        assert is_protected_skill_path(tmp_path, target) is False

    def test_protected_dir_itself_is_protected(self, tmp_path: Path) -> None:
        target = tmp_path / '.opencode' / 'skill'
        target.mkdir(parents=True, exist_ok=True)
        assert is_protected_skill_path(tmp_path, target) is True

    def test_candidate_dir_itself_is_not_protected(self, tmp_path: Path) -> None:
        target = tmp_path / '.teaagent' / 'skill-candidates'
        target.mkdir(parents=True, exist_ok=True)
        assert is_protected_skill_path(tmp_path, target) is False


class TestAssertSkillPathNotProtected:
    def _make_manager(
        self, workspace_root: str | Path, **kwargs: object
    ) -> ApprovalManager:
        return ApprovalManager(
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            workspace_root=str(workspace_root),
            **kwargs,
        )

    def test_write_to_opencode_skill_is_blocked(self, tmp_path: Path) -> None:
        manager = self._make_manager(tmp_path)
        with pytest.raises(ToolPermissionError) as exc_info:
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-1',
                destructive=True,
                arguments={'path': '.opencode/skill/rss/SKILL.md'},
            )
        assert exc_info.value.reason_code == DenialReasonCode.SKILL_WRITE_BLOCKED

    def test_write_to_config_agent_skills_is_blocked(self, tmp_path: Path) -> None:
        manager = self._make_manager(tmp_path)
        with pytest.raises(ToolPermissionError) as exc_info:
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-2',
                destructive=True,
                arguments={'path': '.config/agent/skills/test-skill/SKILL.md'},
            )
        assert exc_info.value.reason_code == DenialReasonCode.SKILL_WRITE_BLOCKED

    def test_write_to_claude_skills_is_blocked(self, tmp_path: Path) -> None:
        manager = self._make_manager(tmp_path)
        with pytest.raises(ToolPermissionError) as exc_info:
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-3',
                destructive=True,
                arguments={'path': '.claude/skills/test-skill/SKILL.md'},
            )
        assert exc_info.value.reason_code == DenialReasonCode.SKILL_WRITE_BLOCKED

    def test_write_to_opencode_skills_is_blocked(self, tmp_path: Path) -> None:
        manager = self._make_manager(tmp_path)
        with pytest.raises(ToolPermissionError) as exc_info:
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-4',
                destructive=True,
                arguments={'path': '.opencode/skills/test-skill/SKILL.md'},
            )
        assert exc_info.value.reason_code == DenialReasonCode.SKILL_WRITE_BLOCKED

    def test_write_to_candidate_path_is_allowed(self, tmp_path: Path) -> None:
        manager = self._make_manager(tmp_path)
        manager.assert_allowed(
            tool_name='workspace_write_file',
            call_id='call-5',
            destructive=True,
            arguments={'path': '.teaagent/skill-candidates/test-skill/SKILL.md'},
        )

    def test_write_to_normal_source_file_is_allowed(self, tmp_path: Path) -> None:
        manager = self._make_manager(tmp_path)
        manager.assert_allowed(
            tool_name='workspace_write_file',
            call_id='call-6',
            destructive=True,
            arguments={'path': 'src/utils.py'},
        )

    def test_write_to_outside_workspace_is_blocked_by_containment_first(
        self, tmp_path: Path
    ) -> None:
        manager = self._make_manager(tmp_path)
        with pytest.raises(ToolPermissionError) as exc_info:
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-7',
                destructive=True,
                arguments={'path': '/etc/passwd'},
            )
        assert exc_info.value.reason_code == DenialReasonCode.WORKSPACE_WRITE_MODE

    def test_skill_quarantine_blocks_before_permission_mode_check(
        self, tmp_path: Path
    ) -> None:
        manager = ApprovalManager(
            permission_mode=PermissionMode.READ_ONLY,
            workspace_root=str(tmp_path),
        )
        with pytest.raises(ToolPermissionError) as exc_info:
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-8',
                destructive=True,
                arguments={'path': '.opencode/skill/SKILL.md'},
            )
        assert exc_info.value.reason_code == DenialReasonCode.SKILL_WRITE_BLOCKED

    def test_non_destructive_tool_not_checked(self, tmp_path: Path) -> None:
        manager = self._make_manager(tmp_path)
        manager.assert_allowed(
            tool_name='workspace_read_file',
            call_id='call-9',
            destructive=False,
            read_only=True,
            arguments={'path': '.opencode/skill/SKILL.md'},
        )


class TestErrorMessage:
    def test_error_message_contains_candidate_path(self, tmp_path: Path) -> None:
        manager = ApprovalManager(
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            workspace_root=str(tmp_path),
        )
        with pytest.raises(ToolPermissionError) as exc_info:
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-10',
                destructive=True,
                arguments={'path': '.opencode/skill/rss/SKILL.md'},
            )
        msg = str(exc_info.value)
        assert '.teaagent/skill-candidates/' in msg
        assert '--skill-dev-opt-in' in msg
        assert '.opencode/skill/rss/SKILL.md' in msg

    def test_error_message_contains_actionable_guidance(self, tmp_path: Path) -> None:
        manager = ApprovalManager(
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            workspace_root=str(tmp_path),
        )
        with pytest.raises(ToolPermissionError) as exc_info:
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-11',
                destructive=True,
                arguments={'path': '.config/agent/skills/my-skill/SKILL.md'},
            )
        msg = str(exc_info.value)
        assert 'candidate install' in msg.lower()


class TestDevOptIn:
    def _make_manager(
        self, workspace_root: str | Path, **kwargs: object
    ) -> ApprovalManager:
        return ApprovalManager(
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            workspace_root=str(workspace_root),
            **kwargs,
        )

    def test_env_var_bypasses_guard(self, tmp_path: Path) -> None:
        manager = self._make_manager(tmp_path)
        with patch.dict(os.environ, {'TEAAGENT_SKILL_DEV_OPT_IN': 'true'}, clear=False):
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-12',
                destructive=True,
                arguments={'path': '.opencode/skill/rss/SKILL.md'},
            )

    def test_env_var_false_does_not_bypass(self, tmp_path: Path) -> None:
        manager = self._make_manager(tmp_path)
        with (
            patch.dict(os.environ, {'TEAAGENT_SKILL_DEV_OPT_IN': 'false'}, clear=False),
            pytest.raises(ToolPermissionError),
        ):
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-13',
                destructive=True,
                arguments={'path': '.opencode/skill/rss/SKILL.md'},
            )

    def test_config_key_bypasses_guard(self, tmp_path: Path) -> None:
        config_dir = tmp_path / '.teaagent'
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / 'config.json').write_text(
            json.dumps({'skill_dev_opt_in': True}), encoding='utf-8'
        )

        manager = self._make_manager(tmp_path)
        manager.assert_allowed(
            tool_name='workspace_write_file',
            call_id='call-14',
            destructive=True,
            arguments={'path': '.opencode/skill/rss/SKILL.md'},
        )

    def test_config_key_false_does_not_bypass(self, tmp_path: Path) -> None:
        config_dir = tmp_path / '.teaagent'
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / 'config.json').write_text(
            json.dumps({'skill_dev_opt_in': False}), encoding='utf-8'
        )

        manager = self._make_manager(tmp_path)
        with pytest.raises(ToolPermissionError):
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-15',
                destructive=True,
                arguments={'path': '.opencode/skill/rss/SKILL.md'},
            )

    def test_env_overrides_config(self, tmp_path: Path) -> None:
        config_dir = tmp_path / '.teaagent'
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / 'config.json').write_text(
            json.dumps({'skill_dev_opt_in': False}), encoding='utf-8'
        )

        manager = self._make_manager(tmp_path)
        with patch.dict(os.environ, {'TEAAGENT_SKILL_DEV_OPT_IN': 'true'}, clear=False):
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-16',
                destructive=True,
                arguments={'path': '.opencode/skill/rss/SKILL.md'},
            )


class TestIsSkillDevOptIn:
    def test_env_true(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {'TEAAGENT_SKILL_DEV_OPT_IN': 'true'}, clear=False):
            assert _is_skill_dev_opt_in(tmp_path) is True

    def test_env_yes(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {'TEAAGENT_SKILL_DEV_OPT_IN': 'yes'}, clear=False):
            assert _is_skill_dev_opt_in(tmp_path) is True

    def test_env_one(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {'TEAAGENT_SKILL_DEV_OPT_IN': '1'}, clear=False):
            assert _is_skill_dev_opt_in(tmp_path) is True

    def test_env_false(self, tmp_path: Path) -> None:
        with patch.dict(
            os.environ, {'TEAAGENT_SKILL_DEV_OPT_IN': 'false'}, clear=False
        ):
            assert _is_skill_dev_opt_in(tmp_path) is False

    def test_env_unset_config_true(self, tmp_path: Path) -> None:
        config_dir = tmp_path / '.teaagent'
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / 'config.json').write_text(
            json.dumps({'skill_dev_opt_in': True}), encoding='utf-8'
        )
        with patch.dict(os.environ, {}, clear=False):
            assert _is_skill_dev_opt_in(tmp_path) is True

    def test_no_env_no_config(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {}, clear=False):
            assert _is_skill_dev_opt_in(tmp_path) is False


class TestPathArgumentKeys:
    def test_target_path_key_is_checked(self, tmp_path: Path) -> None:
        manager = ApprovalManager(
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            workspace_root=str(tmp_path),
        )
        with pytest.raises(ToolPermissionError):
            manager.assert_allowed(
                tool_name='workspace_apply_patch',
                call_id='call-17',
                destructive=True,
                arguments={'target_path': '.opencode/skill/rss/SKILL.md'},
            )

    def test_file_key_is_checked(self, tmp_path: Path) -> None:
        manager = ApprovalManager(
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            workspace_root=str(tmp_path),
        )
        with pytest.raises(ToolPermissionError):
            manager.assert_allowed(
                tool_name='workspace_delete_file',
                call_id='call-18',
                destructive=True,
                arguments={'file': '.opencode/skill/rss/SKILL.md'},
            )

    def test_file_path_key_is_checked(self, tmp_path: Path) -> None:
        manager = ApprovalManager(
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            workspace_root=str(tmp_path),
        )
        with pytest.raises(ToolPermissionError):
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-19',
                destructive=True,
                arguments={
                    'file_path': '.opencode/skill/rss/SKILL.md',
                    'path': 'src/ok.py',
                },
            )

    def test_multiple_paths_first_protected_blocks(self, tmp_path: Path) -> None:
        manager = ApprovalManager(
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            workspace_root=str(tmp_path),
        )
        with pytest.raises(ToolPermissionError):
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-20',
                destructive=True,
                arguments={
                    'path': '.opencode/skill/rss/SKILL.md',
                    'file_path': 'src/ok.py',
                },
            )
