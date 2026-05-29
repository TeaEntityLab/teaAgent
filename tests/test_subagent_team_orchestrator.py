from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from teaagent.subagents._team_orchestrator import (
    TeamDef,
    TeamOrchestrator,
    load_team_defs,
)
from teaagent.subagents._types import SubagentDef


class TestTeamDef:
    def test_default_construction(self) -> None:
        team = TeamDef(name='test-team')
        assert team.name == 'test-team'
        assert team.specialists == ()
        assert team.max_concurrent == 3
        assert team.merge_strategy == 'concatenate'

    def test_with_specialists(self) -> None:
        spec = SubagentDef(name='helper', description='helper agent')
        team = TeamDef(name='team', description='my team', specialists=(spec,), max_concurrent=2)
        assert team.name == 'team'
        assert len(team.specialists) == 1
        assert team.specialists[0].name == 'helper'


class TestLoadTeamDefs:
    def test_returns_empty_when_no_teams_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            teams = load_team_defs(Path(tmp))
            assert teams == {}

    def test_loads_yaml_team(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            teams_dir = root / '.teaagent' / 'teams'
            teams_dir.mkdir(parents=True)
            (teams_dir / 'research.yaml').write_text(
                'name: research\n'
                'description: Research team\n'
                'specialists:\n'
                '  - name: searcher\n'
                '    description: Web searcher\n'
                '    system_prompt: search the web\n'
                'merge_strategy: concatenate\n',
                encoding='utf-8',
            )
            teams = load_team_defs(root)
            assert 'research' in teams
            assert teams['research'].description == 'Research team'
            assert len(teams['research'].specialists) == 1
            assert teams['research'].specialists[0].name == 'searcher'

    def test_loads_json_team(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            teams_dir = root / '.teaagent' / 'teams'
            teams_dir.mkdir(parents=True)
            data = {
                'name': 'code',
                'description': 'Code team',
                'specialists': [
                    {
                        'name': 'writer',
                        'description': 'Code writer',
                        'system_prompt': 'write code',
                    }
                ],
                'merge_strategy': 'concatenate',
            }
            (teams_dir / 'code.json').write_text(json.dumps(data), encoding='utf-8')
            teams = load_team_defs(root)
            assert 'code' in teams
            assert len(teams['code'].specialists) == 1

    def test_skips_unknown_file_types(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            teams_dir = root / '.teaagent' / 'teams'
            teams_dir.mkdir(parents=True)
            (teams_dir / 'notes.txt').write_text('hello', encoding='utf-8')
            teams = load_team_defs(root)
            assert teams == {}

    def test_skips_yaml_without_name(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            teams_dir = root / '.teaagent' / 'teams'
            teams_dir.mkdir(parents=True)
            (teams_dir / 'bad.yaml').write_text(
                'description: no name here\n', encoding='utf-8'
            )
            teams = load_team_defs(root)
            assert teams == {}

    def test_skips_yaml_returning_non_dict(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            teams_dir = root / '.teaagent' / 'teams'
            teams_dir.mkdir(parents=True)
            (teams_dir / 'just_str.yaml').write_text('just a string', encoding='utf-8')
            teams = load_team_defs(root)
            assert teams == {}

    def test_skips_missing_name_field(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            teams_dir = root / '.teaagent' / 'teams'
            teams_dir.mkdir(parents=True)
            (teams_dir / 'no_name.json').write_text(
                json.dumps({'description': 'no name here'}), encoding='utf-8'
            )
            teams = load_team_defs(root)
            assert teams == {}


class TestTeamOrchestrator:
    def test_list_teams(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = MagicMock()
            orchestrator = TeamOrchestrator(root=root, subagent_manager=manager)
            teams = orchestrator.list_teams()
            assert teams == []

    def test_get_team_returns_none_for_unknown(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            orchestrator = TeamOrchestrator(root=root, subagent_manager=MagicMock())
            assert orchestrator.get_team('nonexistent') is None

    def test_run_team_returns_error_for_unknown_team(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            orchestrator = TeamOrchestrator(root=root, subagent_manager=MagicMock())
            result = orchestrator.run_team('do something', 'nonexistent')
            assert result['status'] == 'error'

    def test_run_team_with_specialists(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            teams_dir = root / '.teaagent' / 'teams'
            teams_dir.mkdir(parents=True)
            (teams_dir / 'dev.yaml').write_text(
                'name: dev\n'
                'description: Dev team\n'
                'max_concurrent: 2\n'
                'specialists:\n'
                '  - name: backend\n'
                '    description: Backend specialist\n'
                '    system_prompt: build backend\n'
                '  - name: frontend\n'
                '    description: Frontend specialist\n'
                '    system_prompt: build frontend\n',
                encoding='utf-8',
            )

            manager = MagicMock()
            manager.run_subagent.return_value = {
                'status': 'completed',
                'results': 'done',
                'output': 'task output',
            }

            orchestrator = TeamOrchestrator(root=root, subagent_manager=manager)
            result = orchestrator.run_team('build app', 'dev', parent_run_id='parent-1')

            assert result['status'] == 'ok'
            assert result['team'] == 'dev'
            assert result['specialist_count'] == 2
            assert manager.run_subagent.call_count == 2

    def test_merge_results_concatenate(self) -> None:
        results = [
            {'results': 'output from A'},
            {'results': 'output from B'},
        ]
        merged = TeamOrchestrator._merge_results(results, 'concatenate')
        assert 'output from A' in merged
        assert 'output from B' in merged

    def test_merge_results_lead_summary(self) -> None:
        results = [
            {'results': 'result A'},
            {'results': 'result B'},
        ]
        merged = TeamOrchestrator._merge_results(results, 'lead_summary')
        assert 'result A' in merged
        assert 'result B' in merged
