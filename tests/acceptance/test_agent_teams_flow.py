"""Acceptance test for Agent Teams / Swarm Coordination.

Verifies: TeamDef loading, TeamOrchestrator, tool registration.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from teaagent.subagents._team_orchestrator import (
    TeamDef,
    TeamOrchestrator,
    load_team_defs,
)
from teaagent.subagents._types import SubagentDef


def _make_team_json(path: Path) -> None:
    import json
    teams_dir = path / '.teaagent' / 'teams'
    teams_dir.mkdir(parents=True, exist_ok=True)
    (teams_dir / 'code-review.json').write_text(json.dumps({
        'name': 'code-review',
        'description': 'Code review team',
        'max_concurrent': 2,
        'merge_strategy': 'concatenate',
        'specialists': [
            {'name': 'reviewer', 'description': 'Reviews code changes',
             'system_prompt': 'Review the code for bugs and style issues'},
            {'name': 'tester', 'description': 'Suggests tests',
             'system_prompt': 'Suggest test cases for the changes'},
        ],
    }))


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
