"""AC-NEW: Protected paths (.git, .teaagent) default deny rules.

Verifies that the built-in protected directory rules block writes to .git/
and .teaagent/ directories by default, preventing accidental repository or
configuration corruption (a mainstream standard from Codex and Claude Code).

Acceptance criteria:
- load_file_policy with include_protected_dirs=True (default) includes deny
  rules for .git/* and .teaagent/* paths.
- Writing to .git/config or .teaagent/config.json via workspace_write_file is
  blocked by the default policy.
- The default protected rules are prepended so user rules cannot override them.
- load_file_policy with include_protected_dirs=False returns no protected rules.
"""

from __future__ import annotations

import pytest

from teaagent.errors import ToolPermissionError
from teaagent.file_policy import (
    FilePolicy,
    build_protected_dir_rules,
    load_file_policy,
)


def test_build_protected_dir_rules_returns_git_and_teaagent():
    rules = build_protected_dir_rules()
    ids = [r.id for r in rules]
    assert 'protect-git-dir' in ids
    assert 'protect-teaagent-dir' in ids


def test_protected_rules_block_git_path():
    rules = build_protected_dir_rules()
    policy = FilePolicy(rules=rules)
    with pytest.raises(ToolPermissionError, match='\\.git'):
        policy.assert_allowed(
            tool_name='workspace_write_file',
            arguments={'path': '.git/config'},
        )


def test_protected_rules_block_teaagent_path():
    rules = build_protected_dir_rules()
    policy = FilePolicy(rules=rules)
    with pytest.raises(ToolPermissionError, match='\\.teaagent'):
        policy.assert_allowed(
            tool_name='workspace_write_file',
            arguments={'path': '.teaagent/config.json'},
        )


def test_protected_rules_allow_normal_paths():
    rules = build_protected_dir_rules()
    policy = FilePolicy(rules=rules)
    policy.assert_allowed(
        tool_name='workspace_write_file',
        arguments={'path': 'src/main.py'},
    )


def test_load_file_policy_includes_protected_dirs_by_default(tmp_path):
    policy = load_file_policy(tmp_path)
    ids = [r.id for r in policy.rules]
    assert 'protect-git-dir' in ids
    assert 'protect-teaagent-dir' in ids


def test_load_file_policy_without_protected_dirs(tmp_path):
    policy = load_file_policy(tmp_path, include_protected_dirs=False)
    assert len(policy.rules) == 0


def test_user_rules_combined_with_protected_dirs(tmp_path):
    (tmp_path / '.teaagent').mkdir()
    (tmp_path / '.teaagent' / 'policy.yaml').write_text(
        'version: 1\nrules:\n  - id: my-rule\n    tool_pattern: "workspace_run_shell_*"\n    action: deny\n    message: "shell blocked"\n',
        encoding='utf-8',
    )
    policy = load_file_policy(tmp_path)
    ids = [r.id for r in policy.rules]
    assert ids[0] == 'protect-git-dir', 'protected rules must come first'
    assert ids[1] == 'protect-teaagent-dir', 'protected rules must come first'
    assert 'my-rule' in ids, 'user rules should also be present'


def test_protected_rule_does_not_block_read():
    rules = build_protected_dir_rules()
    policy = FilePolicy(rules=rules)
    policy.assert_allowed(
        tool_name='workspace_read_file',
        arguments={'path': '.git/config'},
    )
