"""Adversarial test suite for shell normalization (_normalize_shell_arg).

Tests that the multi-pass normalization in ``ApprovalPolicy._normalize_shell_arg``
defeats common shell obfuscation techniques used to bypass high-risk pattern
detection, including process substitutions, unquoted operators, brace expansions,
and variable interpolation.

Part of Tranche 2: Post-Audit Security & Concurrency Gates.
"""

from __future__ import annotations

from teaagent.policy import ApprovalPolicy


def test_simple_dollar_substitution() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('echo $(echo /prod)')
    assert '/prod' in normalized


def test_nested_dollar_substitution() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg(
        'deploy $(cat $(echo /production)/config)'
    )
    assert '/production' in normalized


def test_dollar_substitution_with_rm() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('rm -rf $(echo /prod/data)')
    assert '/prod' in normalized
    assert 'rm' in normalized


def test_dollar_substitution_in_middle() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg(
        'cp file $(echo /production)/backup'
    )
    assert '/production' in normalized


def test_simple_backtick() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('echo `echo /prod`')
    assert '/prod' in normalized


def test_backtick_with_rm() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('rm -rf `echo /production`')
    assert '/production' in normalized
    assert 'rm' in normalized


def test_multiple_backticks() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('cp `echo /prod/a` `echo /prod/b`')
    assert '/prod' in normalized


def test_backtick_nested_in_command() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg(
        'deploy --target `echo /production/app`'
    )
    assert '/production' in normalized


def test_and_chain() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('echo safe && rm -rf /prod')
    assert 'rm' in normalized
    assert '/prod' in normalized


def test_or_chain() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('false || rm -rf /production')
    assert 'rm' in normalized
    assert '/production' in normalized


def test_double_and_chain() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg(
        'echo start && cd /prod && rm -rf data'
    )
    assert '/prod' in normalized
    assert 'rm' in normalized


def test_mixed_chain() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg(
        'echo ok && false || rm -rf /production/db'
    )
    assert '/production' in normalized
    assert 'rm' in normalized


def test_simple_brace_expansion() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('echo /pr{od,oduction}/app')
    assert '/prod/app' in normalized
    assert '/production/app' in normalized


def test_brace_with_rm() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('rm -rf /pr{od,oduction}')
    assert '/prod' in normalized
    assert '/production' in normalized


def test_brace_three_alternatives() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('cat /da{ta,tabase,tadb}/config')
    assert '/data' in normalized
    assert '/database' in normalized


def test_brace_prefix_expansion() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('rm -rf /prod{uction,}/data')
    assert '/production/data' in normalized
    assert '/prod/data' in normalized


def test_simple_pipe() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('cat /prod/config | rm -rf')
    assert '/prod' in normalized
    assert 'rm' in normalized


def test_pipe_chain() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('echo /production | xargs rm -rf')
    assert '/production' in normalized
    assert 'rm' in normalized


def test_pipe_with_grep() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg(
        'grep database /prod/config | head'
    )
    assert '/prod' in normalized
    assert 'database' in normalized


def test_simple_semicolon() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('echo safe; rm -rf /prod')
    assert 'rm' in normalized
    assert '/prod' in normalized


def test_multiple_semicolons() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg(
        'echo a; echo b; rm -rf /production'
    )
    assert 'rm' in normalized
    assert '/production' in normalized


def test_semicolon_with_cd() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('cd /prod; rm -rf data')
    assert '/prod' in normalized
    assert 'rm' in normalized


def test_unquoted_var() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('rm -rf $TARGET_DIR')
    assert 'rm' in normalized
    assert 'rm' in normalized.lower()


def test_var_with_braces() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('rm -rf ${TARGET_DIR}')
    assert 'rm' in normalized


def test_var_in_path() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('cat $HOME/production/config')
    assert 'production' in normalized


def test_env_var_expansion_attempt() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('rm -rf $PROD_PATH/data')
    assert 'rm' in normalized


def test_simple_process_substitution() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg(
        'diff <(echo /prod/config) /etc/config'
    )
    assert '/prod' in normalized


def test_process_substitution_with_delete() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg(
        'cat <(echo delete /production/db)'
    )
    assert '/production' in normalized
    assert 'delete' in normalized


def test_backtick_and_brace() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('echo `echo /pr{od,oduction}`')
    assert '/prod' in normalized


def test_dollar_sub_and_chain() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg(
        'echo safe && rm -rf $(echo /prod/data)'
    )
    assert '/prod' in normalized
    assert 'rm' in normalized


def test_quoted_obfuscation_with_chain() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('rm -r"f" /pr"od" && echo done')
    assert 'rm' in normalized
    assert '/prod' in normalized


def test_escape_and_substitution() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('r\\m -rf $(echo /prod)')
    assert 'rm' in normalized
    assert '/prod' in normalized


def test_heavily_obfuscated_rm_prod() -> None:
    """Maximum obfuscation: quotes + escapes + subshell + brace."""
    normalized = ApprovalPolicy._normalize_shell_arg(
        'r"m" -r\'f\' /pr{od,oduction}/$(echo data)'
    )
    assert 'rm' in normalized
    assert '/prod' in normalized


def test_empty_command() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('')
    assert normalized == ''


def test_simple_command_no_obfuscation() -> None:
    normalized = ApprovalPolicy._normalize_shell_arg('pytest tests/')
    assert 'pytest' in normalized
    assert 'tests/' in normalized


def _make_policy() -> ApprovalPolicy:
    return ApprovalPolicy()


def test_dollar_sub_detected_as_high_risk() -> None:
    policy = _make_policy()
    assert policy._is_high_risk_operation(
        'workspace_run_shell_mutate',
        {'command': 'echo $(echo /prod/config)'},
    )


def test_backtick_detected_as_high_risk() -> None:
    policy = _make_policy()
    assert policy._is_high_risk_operation(
        'workspace_run_shell_mutate',
        {'command': 'deploy `echo /production`'},
    )


def test_brace_expansion_detected_as_high_risk() -> None:
    policy = _make_policy()
    assert policy._is_high_risk_operation(
        'workspace_run_shell_mutate',
        {'command': 'rm -rf /pr{od,oduction}'},
    )


def test_chained_command_detected_as_high_risk() -> None:
    policy = _make_policy()
    assert policy._is_high_risk_operation(
        'workspace_run_shell_mutate',
        {'command': 'echo safe && rm -rf /prod'},
    )


def test_safe_command_not_flagged() -> None:
    policy = _make_policy()
    assert not policy._is_high_risk_operation(
        'workspace_run_shell_mutate',
        {'command': 'pytest tests/'},
    )
