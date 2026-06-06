"""Acceptance test for scope budget enforcement (PLAN-002).

Verifies that scope budget fields (allowed_files, allowed_commands, non_goals,
risk, spend, duration) block out-of-scope actions.
"""

from __future__ import annotations

from teaagent.scope_budget import (
    ScopeBudget,
    ScopeBudgetEnforcer,
    ScopeVeto,
    check_all,
    check_command,
    check_duration,
    check_file_access,
    check_non_goal,
    check_risk_level,
    check_spend,
    check_tool_call,
)


class TestScopeBudgetModel:
    """ScopeBudget dataclass construction and round-trip."""

    def test_default_budget(self) -> None:
        """All fields default to unrestricted."""
        b = ScopeBudget()
        assert b.allowed_files is None
        assert b.allowed_commands is None
        assert b.non_goals == []
        assert b.max_risk_level is None
        assert b.max_spend_cents is None
        assert b.max_duration_seconds is None

    def test_round_trip_dict(self) -> None:
        b = ScopeBudget(
            allowed_files=['src/**/*.py'],
            allowed_commands=['pytest'],
            non_goals=['refactor CI'],
            max_risk_level='low',
            max_spend_cents=500.0,
            max_duration_seconds=3600.0,
        )
        d = b.to_dict()
        b2 = ScopeBudget.from_dict(d)
        assert b2.allowed_files == ['src/**/*.py']
        assert b2.allowed_commands == ['pytest']
        assert b2.non_goals == ['refactor CI']
        assert b2.max_risk_level == 'low'
        assert b2.max_spend_cents == 500.0
        assert b2.max_duration_seconds == 3600.0

    def test_from_dict_none(self) -> None:
        assert ScopeBudget.from_dict(None) is None
        assert ScopeBudget.from_dict({}) is not None


class TestFileAccessEnforcement:
    """allowed_files enforcement."""

    def test_unrestricted(self) -> None:
        budget = ScopeBudget()  # no restriction
        result = check_file_access('anything.go', budget)
        assert result.allowed

    def test_allowed_glob(self) -> None:
        budget = ScopeBudget(allowed_files=['src/**/*.py'])
        assert check_file_access('src/main.py', budget).allowed
        assert check_file_access('src/utils/helper.py', budget).allowed
        assert not check_file_access('README.md', budget).allowed
        assert not check_file_access('tests/test_main.py', budget).allowed

    def test_allowed_glob_filename_only(self) -> None:
        budget = ScopeBudget(allowed_files=['*.py'])
        assert check_file_access('main.py', budget).allowed
        # PurePath.match treats basename-only patterns as matching the
        # last component — "*.py" matches any .py file at any depth.
        assert check_file_access('src/main.py', budget).allowed

    def test_empty_denies_all(self) -> None:
        budget = ScopeBudget(allowed_files=[])
        assert not check_file_access('any.txt', budget).allowed


class TestCommandEnforcement:
    """allowed_commands enforcement."""

    def test_unrestricted(self) -> None:
        budget = ScopeBudget()
        assert check_command('rm -rf /', budget).allowed

    def test_allowed_prefix(self) -> None:
        budget = ScopeBudget(allowed_commands=['pytest', 'ruff check'])
        assert check_command('pytest tests/', budget).allowed
        assert check_command('ruff check src/', budget).allowed
        assert not check_command('rm -rf /', budget).allowed
        assert not check_command('python3 -m pip install', budget).allowed

    def test_empty_denies_all(self) -> None:
        budget = ScopeBudget(allowed_commands=[])
        assert not check_command('ls', budget).allowed


class TestNonGoalEnforcement:
    """non_goals enforcement."""

    def test_no_non_goals(self) -> None:
        budget = ScopeBudget()
        assert check_non_goal('refactor CI pipeline', budget).allowed

    def test_match_non_goal(self) -> None:
        budget = ScopeBudget(non_goals=['refactor CI', 'update README'])
        assert not check_non_goal('refactor CI pipeline', budget).allowed
        assert not check_non_goal('update README with badges', budget).allowed
        assert check_non_goal('implement new feature', budget).allowed


class TestRiskEnforcement:
    """max_risk_level enforcement."""

    def test_unrestricted(self) -> None:
        budget = ScopeBudget()
        assert check_risk_level('high', budget).allowed

    def test_block_high(self) -> None:
        budget = ScopeBudget(max_risk_level='low')
        assert check_risk_level('low', budget).allowed
        assert not check_risk_level('medium', budget).allowed
        assert not check_risk_level('high', budget).allowed

    def test_medium_block_high(self) -> None:
        budget = ScopeBudget(max_risk_level='medium')
        assert check_risk_level('low', budget).allowed
        assert check_risk_level('medium', budget).allowed
        assert not check_risk_level('high', budget).allowed


class TestSpendEnforcement:
    """max_spend_cents enforcement."""

    def test_unrestricted(self) -> None:
        budget = ScopeBudget()
        assert check_spend(1_000_000.0, budget).allowed

    def test_exceeds_cap(self) -> None:
        budget = ScopeBudget(max_spend_cents=500.0)
        assert check_spend(400.0, budget).allowed
        assert not check_spend(600.0, budget).allowed

    def test_at_cap_is_allowed(self) -> None:
        budget = ScopeBudget(max_spend_cents=500.0)
        assert check_spend(500.0, budget).allowed


class TestDurationEnforcement:
    """max_duration_seconds enforcement."""

    def test_unrestricted(self) -> None:
        budget = ScopeBudget()
        assert check_duration(99_999.0, budget).allowed

    def test_exceeds_cap(self) -> None:
        budget = ScopeBudget(max_duration_seconds=60.0)
        assert check_duration(30.0, budget).allowed
        assert not check_duration(90.0, budget).allowed


class TestCheckAll:
    """check_all runs all applicable checks."""

    def test_all_pass(self) -> None:
        budget = ScopeBudget(allowed_files=['*.txt'], allowed_commands=['cat'])
        results = check_all(
            file_path='readme.txt',
            command='cat readme.txt',
            budget=budget,
        )
        assert all(r.allowed for r in results)

    def test_file_blocked(self) -> None:
        budget = ScopeBudget(allowed_files=['*.txt'])
        results = check_all(file_path='main.py', budget=budget)
        assert not results[0].allowed
        assert 'allowed_files' in results[0].field

    def test_command_blocked(self) -> None:
        budget = ScopeBudget(allowed_commands=['pytest'])
        results = check_all(command='rm -rf /', budget=budget)
        assert not results[0].allowed


class TestToolAwareCheck:
    """check_tool_call routes tool names to the right checks."""

    def test_file_tool(self) -> None:
        budget = ScopeBudget(allowed_files=['src/**'])
        results = check_tool_call('read_file', {'file_path': 'README.md'}, budget)
        assert not results[0].allowed

    def test_shell_tool(self) -> None:
        budget = ScopeBudget(allowed_commands=['pytest'])
        results = check_tool_call('shell', {'command': 'docker rm'}, budget)
        assert not results[0].allowed

    def test_unknown_tool_no_check(self) -> None:
        budget = ScopeBudget(allowed_files=['src/**'])
        results = check_tool_call('some_unknown_tool', {'file_path': 'bad.txt'}, budget)
        assert len(results) == 0  # unknown tool = no automatic check

    def test_no_args_no_check(self) -> None:
        budget = ScopeBudget(allowed_files=['src/**'])
        results = check_tool_call('read_file', {}, budget)
        assert len(results) == 0  # no file_path arg = skip check


class TestScopeBudgetEnforcer:
    """ScopeBudgetEnforcer integration."""

    def test_inactive_no_budget(self) -> None:
        enforcer = ScopeBudgetEnforcer()
        assert not enforcer.active

    def test_inactive_empty_budget(self) -> None:
        enforcer = ScopeBudgetEnforcer(ScopeBudget())
        assert not enforcer.active  # all unset = inactive

    def test_active_with_constraint(self) -> None:
        enforcer = ScopeBudgetEnforcer(ScopeBudget(allowed_files=['*.py']))
        assert enforcer.active

    def test_check_file(self) -> None:
        budget = ScopeBudget(allowed_files=['*.py'])
        enforcer = ScopeBudgetEnforcer(budget)
        results = enforcer.check_file('readme.md')
        assert len(results) == 1
        assert not results[0].allowed

    def test_check_command(self) -> None:
        budget = ScopeBudget(allowed_commands=['pytest'])
        enforcer = ScopeBudgetEnforcer(budget)
        results = enforcer.check_command('make deploy')
        assert not results[0].allowed

    def test_check_tool(self) -> None:
        budget = ScopeBudget(allowed_files=['*.py'])
        enforcer = ScopeBudgetEnforcer(budget)
        results = enforcer.check_tool('read_file', {'file_path': 'readme.md'})
        assert not results[0].allowed

    def test_no_budget_always_allowed(self) -> None:
        enforcer = ScopeBudgetEnforcer()
        assert enforcer.check_file('any.txt')[0].allowed
        assert enforcer.check_command('rm -rf /')[0].allowed

    def test_set_budget_late(self) -> None:
        enforcer = ScopeBudgetEnforcer()
        assert not enforcer.active
        enforcer.budget = ScopeBudget(allowed_files=['*.py'])
        assert enforcer.active


class TestScopeVeto:
    """ScopeVeto exception."""

    def test_raise_and_fields(self) -> None:
        try:
            raise ScopeVeto('file not allowed', field='allowed_files')
        except ScopeVeto as e:
            assert e.reason == 'file not allowed'
            assert e.field == 'allowed_files'
            assert 'scope:allowed_files' in str(e)
            assert 'file not allowed' in str(e)
