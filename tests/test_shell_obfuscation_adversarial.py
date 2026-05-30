"""Adversarial test suite for shell normalization (_normalize_shell_arg).

Tests that the multi-pass normalization in ``ApprovalPolicy._normalize_shell_arg``
defeats common shell obfuscation techniques used to bypass high-risk pattern
detection, including process substitutions, unquoted operators, brace expansions,
and variable interpolation.

Part of Tranche 2: Post-Audit Security & Concurrency Gates.
"""

from __future__ import annotations

import unittest

from teaagent.policy import ApprovalPolicy


class ShellObfuscationDollarSubstitutionTests(unittest.TestCase):
    """$() command substitution must be surfaced in normalized output."""

    def test_simple_dollar_substitution(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg('echo $(echo /prod)')
        self.assertIn('/prod', normalized)

    def test_nested_dollar_substitution(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'deploy $(cat $(echo /production)/config)'
        )
        self.assertIn('/production', normalized)

    def test_dollar_substitution_with_rm(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg('rm -rf $(echo /prod/data)')
        self.assertIn('/prod', normalized)
        self.assertIn('rm', normalized)

    def test_dollar_substitution_in_middle(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'cp file $(echo /production)/backup'
        )
        self.assertIn('/production', normalized)


class ShellObfuscationBacktickTests(unittest.TestCase):
    """Backtick subshells must be extracted and surfaced."""

    def test_simple_backtick(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg('echo `echo /prod`')
        self.assertIn('/prod', normalized)

    def test_backtick_with_rm(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg('rm -rf `echo /production`')
        self.assertIn('/production', normalized)
        self.assertIn('rm', normalized)

    def test_multiple_backticks(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'cp `echo /prod/a` `echo /prod/b`'
        )
        self.assertIn('/prod', normalized)

    def test_backtick_nested_in_command(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'deploy --target `echo /production/app`'
        )
        self.assertIn('/production', normalized)


class ShellObfuscationChainingTests(unittest.TestCase):
    """&& and || chaining must preserve all segments in normalized output."""

    def test_and_chain(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'echo safe && rm -rf /prod'
        )
        self.assertIn('rm', normalized)
        self.assertIn('/prod', normalized)

    def test_or_chain(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'false || rm -rf /production'
        )
        self.assertIn('rm', normalized)
        self.assertIn('/production', normalized)

    def test_double_and_chain(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'echo start && cd /prod && rm -rf data'
        )
        self.assertIn('/prod', normalized)
        self.assertIn('rm', normalized)

    def test_mixed_chain(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'echo ok && false || rm -rf /production/db'
        )
        self.assertIn('/production', normalized)
        self.assertIn('rm', normalized)


class ShellObfuscationBraceExpansionTests(unittest.TestCase):
    """Brace expansion must be expanded to catch alternation-based bypasses."""

    def test_simple_brace_expansion(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg('echo /pr{od,oduction}/app')
        self.assertIn('/prod/app', normalized)
        self.assertIn('/production/app', normalized)

    def test_brace_with_rm(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg('rm -rf /pr{od,oduction}')
        self.assertIn('/prod', normalized)
        self.assertIn('/production', normalized)

    def test_brace_three_alternatives(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'cat /da{ta,tabase,tadb}/config'
        )
        self.assertIn('/data', normalized)
        self.assertIn('/database', normalized)

    def test_brace_prefix_expansion(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'rm -rf /prod{uction,}/data'
        )
        self.assertIn('/production/data', normalized)
        self.assertIn('/prod/data', normalized)


class ShellObfuscationPipeTests(unittest.TestCase):
    """Pipe operators must preserve all segments."""

    def test_simple_pipe(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg('cat /prod/config | rm -rf')
        self.assertIn('/prod', normalized)
        self.assertIn('rm', normalized)

    def test_pipe_chain(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'echo /production | xargs rm -rf'
        )
        self.assertIn('/production', normalized)
        self.assertIn('rm', normalized)

    def test_pipe_with_grep(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'grep database /prod/config | head'
        )
        self.assertIn('/prod', normalized)
        self.assertIn('database', normalized)


class ShellObfuscationSemicolonTests(unittest.TestCase):
    """Semicolons must preserve all command segments."""

    def test_simple_semicolon(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'echo safe; rm -rf /prod'
        )
        self.assertIn('rm', normalized)
        self.assertIn('/prod', normalized)

    def test_multiple_semicolons(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'echo a; echo b; rm -rf /production'
        )
        self.assertIn('rm', normalized)
        self.assertIn('/production', normalized)

    def test_semicolon_with_cd(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'cd /prod; rm -rf data'
        )
        self.assertIn('/prod', normalized)
        self.assertIn('rm', normalized)


class ShellObfuscationUnquotedVarTests(unittest.TestCase):
    """Unquoted $var references must appear in normalized output."""

    def test_unquoted_var(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg('rm -rf $TARGET_DIR')
        self.assertIn('rm', normalized)
        self.assertIn('rm', normalized.lower())

    def test_var_with_braces(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg('rm -rf ${TARGET_DIR}')
        self.assertIn('rm', normalized)

    def test_var_in_path(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg('cat $HOME/production/config')
        self.assertIn('production', normalized)

    def test_env_var_expansion_attempt(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'rm -rf $PROD_PATH/data'
        )
        self.assertIn('rm', normalized)


class ShellObfuscationProcessSubstitutionTests(unittest.TestCase):
    """Process substitution <(...) must be extracted."""

    def test_simple_process_substitution(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'diff <(echo /prod/config) /etc/config'
        )
        self.assertIn('/prod', normalized)

    def test_process_substitution_with_delete(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'cat <(echo delete /production/db)'
        )
        self.assertIn('/production', normalized)
        self.assertIn('delete', normalized)


class ShellObfuscationCombinedTechniquesTests(unittest.TestCase):
    """Combined obfuscation techniques must all be defeated."""

    def test_backtick_and_brace(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'echo `echo /pr{od,oduction}`'
        )
        self.assertIn('/prod', normalized)

    def test_dollar_sub_and_chain(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'echo safe && rm -rf $(echo /prod/data)'
        )
        self.assertIn('/prod', normalized)
        self.assertIn('rm', normalized)

    def test_quoted_obfuscation_with_chain(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'rm -r"f" /pr"od" && echo done'
        )
        self.assertIn('rm', normalized)
        self.assertIn('/prod', normalized)

    def test_escape_and_substitution(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg(
            'r\\m -rf $(echo /prod)'
        )
        self.assertIn('rm', normalized)
        self.assertIn('/prod', normalized)

    def test_heavily_obfuscated_rm_prod(self) -> None:
        """Maximum obfuscation: quotes + escapes + subshell + brace."""
        normalized = ApprovalPolicy._normalize_shell_arg(
            'r"m" -r\'f\' /pr{od,oduction}/$(echo data)'
        )
        self.assertIn('rm', normalized)
        self.assertIn('/prod', normalized)

    def test_empty_command(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg('')
        self.assertEqual(normalized, '')

    def test_simple_command_no_obfuscation(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg('pytest tests/')
        self.assertIn('pytest', normalized)
        self.assertIn('tests/', normalized)


class ShellObfuscationHighRiskIntegrationTests(unittest.TestCase):
    """Integration tests: verify _is_high_risk_operation catches obfuscated commands."""

    def _make_policy(self) -> ApprovalPolicy:
        return ApprovalPolicy()

    def test_dollar_sub_detected_as_high_risk(self) -> None:
        policy = self._make_policy()
        self.assertTrue(
            policy._is_high_risk_operation(
                'workspace_run_shell_mutate',
                {'command': 'echo $(echo /prod/config)'},
            )
        )

    def test_backtick_detected_as_high_risk(self) -> None:
        policy = self._make_policy()
        self.assertTrue(
            policy._is_high_risk_operation(
                'workspace_run_shell_mutate',
                {'command': 'deploy `echo /production`'},
            )
        )

    def test_brace_expansion_detected_as_high_risk(self) -> None:
        policy = self._make_policy()
        self.assertTrue(
            policy._is_high_risk_operation(
                'workspace_run_shell_mutate',
                {'command': 'rm -rf /pr{od,oduction}'},
            )
        )

    def test_chained_command_detected_as_high_risk(self) -> None:
        policy = self._make_policy()
        self.assertTrue(
            policy._is_high_risk_operation(
                'workspace_run_shell_mutate',
                {'command': 'echo safe && rm -rf /prod'},
            )
        )

    def test_safe_command_not_flagged(self) -> None:
        policy = self._make_policy()
        self.assertFalse(
            policy._is_high_risk_operation(
                'workspace_run_shell_mutate',
                {'command': 'pytest tests/'},
            )
        )


if __name__ == '__main__':
    unittest.main()
