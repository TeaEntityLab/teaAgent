"""SURF-011: surfaces explain lists commands and gaps per surface."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

from teaagent.cli import main
from teaagent.integration.surface_parity import (
    IDE_COMMAND_CLI_PARITY,
    SURF002_REQUIRED_COMMANDS,
    SURFACE_EXPLAIN_SCHEMA_VERSION,
    build_surface_explain,
    format_surface_explain_human,
)


def test_build_surface_explain_includes_all_surfaces() -> None:
    payload = build_surface_explain()
    assert payload['schema_version'] == SURFACE_EXPLAIN_SCHEMA_VERSION
    surfaces = payload['surfaces']
    assert set(surfaces) == {'cli', 'tui', 'ide', 'dashboard'}
    assert 'agent daily' in surfaces['cli']['supported']
    assert 'resume <run_id>' in surfaces['tui']['supported']
    assert len(surfaces['ide']['supported']) == len(IDE_COMMAND_CLI_PARITY)
    assert set(surfaces['ide']['surf002_required']) == SURF002_REQUIRED_COMMANDS
    assert 'dashboard_cockpit' in surfaces['ide']['gaps']


def test_human_formatter_mentions_surfaces() -> None:
    text = format_surface_explain_human(build_surface_explain())
    assert '## cli' in text
    assert '## ide' in text
    assert 'teaagent.agentDaily' in text


def test_cli_surfaces_explain_emits_json_contract() -> None:
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(['surfaces', 'explain'])
    assert code == 0
    payload = json.loads(out.getvalue())
    assert payload['schema_version'] == SURFACE_EXPLAIN_SCHEMA_VERSION
    assert 'surfaces' in payload


def test_cli_surfaces_explain_human_flag() -> None:
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(['surfaces', 'explain', '--human'])
    assert code == 0
    assert 'TeaAgent surface capabilities' in out.getvalue()
