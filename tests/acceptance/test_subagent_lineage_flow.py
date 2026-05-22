"""AC-NEW-23: Subagent lineage and isolation flow.

As a user, I want child subagent runs to record parent lineage so delegated work
is auditable and batch delegation returns ordered metadata.

Acceptance criteria:
- Child subagent results include parent_run_id, def_name, depth, and isolation.
- subagent_batch returns ordered lineage entries with batch_index.
- Default isolation is shared workspace; worktree isolation is optional on git repos.
"""

from __future__ import annotations

import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main
from teaagent.subagents import DEFAULT_SUBAGENT_ISOLATION


def test_cli_subagent_run_includes_lineage_in_tool_observation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'README.md').write_text('hello', encoding='utf-8')
        adapter = FakeAdapter(
            [
                '{"type":"tool","tool_name":"subagent","arguments":{"task":"inspect README"},"call_id":"sub-1"}',
                '{"type":"final","content":"child done"}',
                '{"type":"final","content":"parent done"}',
            ]
        )
        output = StringIO()
        with (
            patch('teaagent.cli.create_llm_adapter', return_value=adapter),
            redirect_stdout(output),
        ):
            exit_code = main(
                [
                    'agent',
                    'run',
                    'gpt',
                    'delegate inspection',
                    '--subagent',
                    '--root',
                    tmp,
                    '--permission-mode',
                    'read-only',
                ]
            )

        payload = json.loads(output.getvalue())
        assert exit_code == 0
        assert payload['status'] == 'completed'

        run_path = root / '.teaagent' / 'runs' / f'{payload["run_id"]}.jsonl'
        assert run_path.exists()
        events = [
            json.loads(line)
            for line in run_path.read_text(encoding='utf-8').splitlines()
            if line.strip()
        ]
        completed = next(
            e
            for e in events
            if e.get('event_type') == 'tool_call_completed'
            and e.get('payload', {}).get('tool_name') == 'subagent'
        )
        lineage = completed['payload']['result']['lineage']
        assert lineage['parent_run_id'] == payload['run_id']
        assert lineage['def_name'] == 'generic'
        assert lineage['depth'] == 1
        assert lineage['isolation'] == DEFAULT_SUBAGENT_ISOLATION
        assert 'batch_index' not in lineage

        child_run_id = completed['payload']['result']['run_id']
        child_lines = [
            json.loads(line)
            for line in (root / '.teaagent' / 'runs' / f'{child_run_id}.jsonl')
            .read_text(encoding='utf-8')
            .splitlines()
            if line.strip()
        ]
        lineage_event = next(
            e for e in child_lines if e.get('event_type') == 'subagent_lineage'
        )
        assert lineage_event['payload']['parent_run_id'] == payload['run_id']
