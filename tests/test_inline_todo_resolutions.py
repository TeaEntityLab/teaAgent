"""Tests for the inline-TODO catalog "implicit deferral" resolutions.

Each test maps to a row that was previously listed as *review-needed* in
``docs/plans/ticket-plans/inline-todos.md`` and is now either implemented for
real or made explicitly honest about being a simulation.
"""

from __future__ import annotations

import shlex
from datetime import datetime

from teaagent.consensus.consensus_validation import (
    ConsensusRequest,
    ConsensusRule,
    ConsensusRuleType,
    ConsensusStatus,
)
from teaagent.domain.agent_factory import AgentFactory
from teaagent.domain.issue_intake import (
    CommandSuggester,
    IssueType,
    ParsedIssue,
    PlanArtifact,
    PlanGenerator,
)
from teaagent.domain.workflow_engine import (
    StepExecution,
    workflow_execution_from_dict,
)
from teaagent.eval_suite import EvalRunner, EvalStore
from teaagent.plugin_system import AgentPlugin, PluginRegistry


def _role_rule() -> ConsensusRule:
    return ConsensusRule(
        rule_id='r1',
        rule_type=ConsensusRuleType.ROLE_BASED,
        required_approvals=0,
        total_voters=3,
        required_roles={'security', 'architecture'},
    )


# --- #1 consensus ROLE_BASED real role lookup -------------------------------


def test_role_based_uses_explicit_voter_role_map() -> None:
    """An explicit voter->role mapping is honoured (real lookup)."""
    rule = _role_rule()
    votes = {'alice': True, 'bob': True}
    roles = {'alice': 'security', 'bob': 'architecture'}

    assert rule.check_consensus(votes, roles) == ConsensusStatus.APPROVED


def test_role_based_pending_when_required_role_missing() -> None:
    rule = _role_rule()
    votes = {'alice': True, 'bob': True}
    # Both map to the same role -> the 'architecture' requirement is unmet.
    roles = {'alice': 'security', 'bob': 'security'}

    assert rule.check_consensus(votes, roles) == ConsensusStatus.PENDING


def test_role_based_falls_back_to_voter_id_as_role() -> None:
    """With no mapping, voter_id is its own role (documented default contract)."""
    rule = _role_rule()
    votes = {'security': True, 'architecture': True}

    assert rule.check_consensus(votes) == ConsensusStatus.APPROVED


def test_request_records_and_roundtrips_voter_roles() -> None:
    request = ConsensusRequest(
        request_id='q1',
        rule_id='r1',
        action='deploy',
        context={},
        requested_by='alice',
    )
    request.add_vote('alice', True, role='security')
    request.add_vote('bob', False)

    assert request.voter_roles == {'alice': 'security'}

    restored = ConsensusRequest.from_dict(request.to_dict())
    assert restored.voter_roles == {'alice': 'security'}
    assert restored.votes == {'alice': True, 'bob': False}


# --- #2 workflow simulated execution is explicitly labelled -----------------


def test_step_execution_simulated_flag_roundtrips() -> None:
    execution_dict = {
        'plan': {'task_description': 'demo', 'steps': []},
        'step_results': {
            '1': {'step_id': 1, 'success': True, 'output': 'x', 'simulated': True},
        },
    }
    restored = workflow_execution_from_dict(execution_dict)
    assert restored.step_results[1].simulated is True


def test_step_execution_simulated_defaults_false() -> None:
    assert StepExecution(step_id=1, success=True).simulated is False


# --- #3 eval baseline comparison is a real diff -----------------------------


def test_eval_baseline_comparison_matches(tmp_path) -> None:
    runner = EvalRunner(EvalStore(tmp_path))
    result = runner._compare_with_baseline('same', {'output': 'same'})

    assert result['matches'] is True
    assert result['diff'] == ''
    assert result['similarity'] == 1.0


def test_eval_baseline_comparison_real_diff(tmp_path) -> None:
    runner = EvalRunner(EvalStore(tmp_path))
    result = runner._compare_with_baseline('hello world', {'output': 'hello there'})

    assert result['matches'] is False
    assert 'hello world' in result['diff']
    assert '--- baseline' in result['diff']
    assert '+++ actual' in result['diff']
    assert 0.0 < result['similarity'] < 1.0


# --- #5 agent removal actually unregisters ----------------------------------


def test_plugin_registry_unregister_agent() -> None:
    registry = PluginRegistry()
    registry.register_agent(
        AgentPlugin(name='temp', description='d', system_prompt='p', tools=())
    )

    assert registry.unregister_agent('temp') is True
    assert registry.get_agent('temp') is None
    assert registry.unregister_agent('temp') is False


def test_factory_remove_agent_unregisters_from_memory() -> None:
    registry = PluginRegistry()
    registry.register_agent(
        AgentPlugin(name='gen', description='d', system_prompt='p', tools=())
    )
    factory = AgentFactory(registry)

    assert factory.remove_agent('gen') is True
    assert registry.get_agent('gen') is None
    # Idempotent: removing a missing agent reports False rather than faking success.
    assert factory.remove_agent('gen') is False


# --- #6 issue-intake command quoting + real explore delegation --------------


def _parsed_issue() -> ParsedIssue:
    return ParsedIssue(
        title='Fix login',
        description='desc',
        issue_type=IssueType.BUG,
        steps_to_reproduce=None,
        expected_behavior=None,
        actual_behavior=None,
        affected_files=['auth.py'],
        affected_components=['auth'],
        priority=None,
        raw_text='raw',
    )


def _plan_artifact(goal: str) -> PlanArtifact:
    return PlanArtifact(
        id='p1',
        title='t',
        goal=goal,
        approach='a',
        steps=[],
        affected_files=[],
        risks=[],
        created_at=datetime.now(),
        ambiguity_score=0.0,
    )


def test_build_command_is_shell_safe() -> None:
    suggester = CommandSuggester()
    goal = 'do a thing; rm -rf "/" && echo $HOME'
    command = suggester._build_command(_plan_artifact(goal), 'workspace-write')

    assert shlex.quote(goal) in command
    assert '--permission-mode workspace-write' in command
    # The raw, unquoted injection must never appear verbatim after --task.
    assert f'--task {goal}' not in command


class _RecordingGatherer:
    """Real (non-mock) collaborator that records the explore call."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def explore(self, issue: ParsedIssue, workspace_root) -> dict:
        self.calls.append(issue.title)
        return {'discovered_files': ['auth/login.py'], 'exploration_enabled': True}


def test_explore_delegates_to_injected_collaborator(tmp_path) -> None:
    gatherer = _RecordingGatherer()
    generator = PlanGenerator(context_gatherer=gatherer)

    context = generator.explore(_parsed_issue(), tmp_path)

    assert gatherer.calls == ['Fix login']
    assert context['discovered_files'] == ['auth/login.py']
    assert context['exploration_enabled'] is True


def test_explore_without_collaborator_returns_deterministic_context(tmp_path) -> None:
    generator = PlanGenerator()
    context = generator.explore(_parsed_issue(), tmp_path)

    assert context['exploration_enabled'] is False
    assert context['affected_files'] == ['auth.py']
    assert context['issue_type'] == 'bug'
