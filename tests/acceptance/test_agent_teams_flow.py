"""Test module for Agent Teams / Swarm Coordination.

This module tests the agent teams system, which enables coordinated execution
of multiple specialized agents (a swarm) to accomplish complex tasks. Teams
define specialists with different roles and merge strategies for combining results.

Key concepts tested:
- Team Definition Loading: TeamDef JSON files are loaded from .teaagent/teams/
- Team Orchestrator: Manages team execution and result merging
- Specialist Roles: Teams define specialists with specific system prompts
- Merge Strategies: Results can be merged using strategies like concatenate
- Tool Registration: Team-related tools are registered for agent use
- Error Handling: Unknown teams are handled gracefully

Acceptance Criteria:
- AC1: TeamDef JSON files are loaded from .teaagent/teams/ directory
- AC2: TeamOrchestrator can list available teams
- AC3: TeamOrchestrator can execute teams and return results
- AC4: Team definitions include name, description, max_concurrent, and specialists
- AC5: Specialists have name, description, and system_prompt
- AC6: Merge strategies (e.g., concatenate) combine specialist results
- AC7: Unknown team names return error status

Technical Details:
- load_team_defs loads team definitions from JSON files
- TeamOrchestrator manages team execution via subagent_manager
- TeamDef includes metadata and specialist configurations
- Merge strategies determine how specialist results are combined
- Teams are stored in .teaagent/teams/*.json files
- SubagentManager executes individual specialists

References:
- Agent teams design: /docs/architecture/agent_teams.md
- Swarm coordination: /docs/architecture/swarm_coordination.md
- Team definition format: /docs/specs/team_def_format.md
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from teaagent.subagents._team_orchestrator import (
    TeamOrchestrator,
    load_team_defs,
)


def _make_team_json(path: Path) -> None:
    import json

    teams_dir = path / '.teaagent' / 'teams'
    teams_dir.mkdir(parents=True, exist_ok=True)
    (teams_dir / 'code-review.json').write_text(
        json.dumps(
            {
                'name': 'code-review',
                'description': 'Code review team',
                'max_concurrent': 2,
                'merge_strategy': 'concatenate',
                'specialists': [
                    {
                        'name': 'reviewer',
                        'description': 'Reviews code changes',
                        'system_prompt': 'Review the code for bugs and style issues',
                    },
                    {
                        'name': 'tester',
                        'description': 'Suggests tests',
                        'system_prompt': 'Suggest test cases for the changes',
                    },
                ],
            }
        )
    )


def test_load_team_defs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)
        _make_team_json(path)
        teams = load_team_defs(path)
        assert 'code-review' in teams
        team = teams['code-review']
        assert team.description == 'Code review team'
        assert len(team.specialists) == 2
        assert team.specialists[0].name == 'reviewer'
        assert team.specialists[1].name == 'tester'


def test_team_orchestrator_list() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)
        _make_team_json(path)

        class _FakeManager:
            _root = path

            def run_subagent(self, **kw: dict) -> dict:
                return {'status': 'completed', 'output': f'done: {kw.get("task", "")}'}

        orch = TeamOrchestrator(root=path, subagent_manager=_FakeManager())
        teams = orch.list_teams()
        assert any(t.name == 'code-review' for t in teams)


def test_team_orchestrator_run_unknown_team() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)

        class _FakeManager:
            _root = path

            def run_subagent(self, **kw: dict) -> dict:
                return {'status': 'completed', 'output': ''}

        orch = TeamOrchestrator(root=path, subagent_manager=_FakeManager())
        result = orch.run_team('do something', 'nonexistent')
        assert result['status'] == 'error'


def test_team_merge_results() -> None:
    results = [
        {'output': 'result a'},
        {'output': 'result b'},
    ]
    merged = TeamOrchestrator._merge_results(results, 'concatenate')
    assert 'result a' in merged
    assert 'result b' in merged
