"""Agent Teams / Swarm Coordination — lead agent + specialist subagents.

Extends the subagent system with team-level orchestration:
- ``TeamDef`` defines a team of specialised subagents with a lead
- ``TeamOrchestrator`` distributes tasks, collects results, merges outputs
- ``register_team_tools()`` exposes team operations to the agent loop
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from teaagent.subagents._types import SubagentDef


def _load_team_yaml(path: Path) -> Any:
    """Load a team definition from YAML.

    Prefer PyYAML when installed, but fall back to a minimal parser for the
    restricted YAML subset used by `.teaagent/teams/*.yml`:
    - top-level `key: value` scalars
    - a `specialists:` list of dict items with scalar `key: value` fields

    This keeps YAML team defs usable without adding a hard dependency on PyYAML.
    """

    text = path.read_text(encoding='utf-8')
    try:
        import yaml

        return yaml.safe_load(text)
    except ImportError:
        return _parse_simple_team_yaml(text)


def _parse_simple_team_yaml(text: str) -> dict[str, Any]:
    """Parse a tiny YAML subset used for team definitions.

    This is intentionally not a general YAML parser.
    """

    out: dict[str, Any] = {}
    lines = [ln.rstrip('\n') for ln in text.splitlines()]
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith('#'):
            continue

        # top-level "key: value" or "key:" (block follows)
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        key = key.strip()
        value = value.strip()

        if key != 'specialists':
            if value == '':
                out[key] = ''
            else:
                out[key] = _coerce_scalar(value)
            continue

        # specialists block
        specialists: list[dict[str, Any]] = []
        while i < len(lines):
            raw = lines[i]
            if raw.strip() == '' or raw.lstrip().startswith('#'):
                i += 1
                continue
            if not raw.startswith(' '):
                break
            item_line = raw.strip()
            if not item_line.startswith('- '):
                i += 1
                continue
            item: dict[str, Any] = {}
            item_kv = item_line[2:]
            if ':' in item_kv:
                ik, iv = item_kv.split(':', 1)
                item[ik.strip()] = _coerce_scalar(iv.strip())
            i += 1
            while i < len(lines):
                sub_raw = lines[i]
                if sub_raw.strip() == '' or sub_raw.lstrip().startswith('#'):
                    i += 1
                    continue
                if not sub_raw.startswith(' ' * 4):
                    break
                sub = sub_raw.strip()
                if ':' in sub:
                    sk, sv = sub.split(':', 1)
                    item[sk.strip()] = _coerce_scalar(sv.strip())
                i += 1
            specialists.append(item)
        out['specialists'] = specialists

    return out


def _coerce_scalar(value: str) -> Any:
    if value.isdigit():
        return int(value)
    lowered = value.lower()
    if lowered in {'true', 'false'}:
        return lowered == 'true'
    return value


@dataclass(frozen=True)
class TeamDef:
    """Definition of an agent team with a lead and specialists."""

    name: str
    description: str = ''
    lead_prompt: str = ''
    specialists: tuple[SubagentDef, ...] = field(default_factory=tuple)
    max_concurrent: int = 3
    merge_strategy: str = 'concatenate'


def load_team_defs(root: Path) -> dict[str, TeamDef]:
    """Load team definitions from ``.teaagent/teams/`` directory."""
    teams: dict[str, TeamDef] = {}
    teams_dir = root.resolve() / '.teaagent' / 'teams'
    if not teams_dir.is_dir():
        return teams
    for path in sorted(teams_dir.glob('*')):
        if path.suffix in ('.yaml', '.yml'):
            data = _load_team_yaml(path)
        elif path.suffix == '.json':
            data = json.loads(path.read_text(encoding='utf-8'))
        else:
            continue
        if not isinstance(data, dict) or 'name' not in data:
            continue
        specialists = []
        for spec in data.get('specialists', []):
            specialists.append(
                SubagentDef(
                    name=spec.get('name', ''),
                    description=spec.get('description', ''),
                    system_prompt=spec.get('system_prompt', ''),
                    model=spec.get('model'),
                    max_iterations=spec.get('max_iterations', 5),
                    max_tool_calls=spec.get('max_tool_calls', 8),
                    isolation=spec.get('isolation', 'worktree'),
                    effort=spec.get('effort'),
                )
            )
        teams[data['name']] = TeamDef(
            name=data['name'],
            description=data.get('description', ''),
            lead_prompt=data.get('lead_prompt', ''),
            specialists=tuple(specialists),
            max_concurrent=data.get('max_concurrent', 3),
            merge_strategy=data.get('merge_strategy', 'concatenate'),
        )
    return teams


class TeamOrchestrator:
    """Orchestrates a team of subagents with a lead agent coordinating."""

    def __init__(
        self,
        *,
        root: Path,
        subagent_manager: Any,
    ) -> None:
        self._root = root
        self._manager = subagent_manager
        self._defs = load_team_defs(root)

    def list_teams(self) -> list[TeamDef]:
        return sorted(self._defs.values(), key=lambda t: t.name)

    def get_team(self, name: str) -> Optional[TeamDef]:
        return self._defs.get(name)

    def run_team(
        self,
        task: str,
        team_name: str,
        *,
        parent_run_id: str = '',
    ) -> dict[str, Any]:
        team = self.get_team(team_name)
        if team is None:
            return {'status': 'error', 'message': f'unknown team: {team_name}'}

        specialist_results: list[dict[str, Any]] = []
        for i, spec in enumerate(team.specialists):
            if i >= team.max_concurrent:
                break
            result = self._manager.run_subagent(
                task=task,
                parent_run_id=parent_run_id,
                depth=2,
                def_name=spec.name,
                batch_index=i,
                isolation=spec.isolation,
            )
            specialist_results.append(result)

        merged = self._merge_results(specialist_results, team.merge_strategy)
        return {
            'status': 'ok',
            'team': team_name,
            'specialist_count': len(specialist_results),
            'output': merged,
        }

    @staticmethod
    def _merge_results(results: list[dict[str, Any]], strategy: str) -> str:
        if strategy == 'lead_summary':
            outputs = [r.get('results', r.get('output', '')) for r in results]
            return '\n\n---\n\n'.join(str(o) for o in outputs if o)
        outputs = [r.get('results', r.get('output', str(r))) for r in results]
        return '\n\n---\n\n'.join(str(o) for o in outputs if o)
