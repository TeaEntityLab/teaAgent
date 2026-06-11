"""SURF-010: attach snapshot and attach --resume share resume preparation."""

from __future__ import annotations

import io
import json
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from teaagent.cli import main
from teaagent.integration.run_state import (
    RUN_STATE_SCHEMA_VERSION,
    build_attach_snapshot,
)
from teaagent.run_store import RunStore


def _seed_run(root: str, run_id: str = 'attach-parity') -> None:
    store = RunStore(root)
    audit = store.audit_logger(run_id)
    audit.record('run_started', run_id, task='attach smoke', permission_mode='prompt')
    audit.record('heartbeat', run_id, tick=1, interval_seconds=0.1)
    audit.record('run_completed', run_id, answer='done', cost_cents=3.5)


def test_build_attach_snapshot_matches_cli_attach_payload() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _seed_run(tmp)
        store = RunStore(tmp)
        snapshot = build_attach_snapshot(store, 'attach-parity')

        out = io.StringIO()
        with redirect_stdout(out):
            code = main(['agent', 'attach', 'attach-parity', '--root', tmp])
        # Verify CLI attach command succeeds
        assert code == 0, f'Expected CLI attach to succeed, got exit code {code}'
        cli_payload = json.loads(out.getvalue())

        # Verify CLI payload matches programmatic snapshot
        assert cli_payload == snapshot, (
            'CLI attach payload should match build_attach_snapshot output'
        )
        # Verify schema version is current
        assert cli_payload['run_state']['schema_version'] == RUN_STATE_SCHEMA_VERSION, (
            f'Expected schema version {RUN_STATE_SCHEMA_VERSION}, '
            f'got {cli_payload["run_state"]["schema_version"]}'
        )
        # Verify run status is completed
        assert cli_payload['run_state']['status'] == 'completed', (
            f'Expected status "completed", got {cli_payload["run_state"]["status"]!r}'
        )
        # Verify cost is preserved from seed data
        assert cli_payload['run_state']['cost_cents'] == 3.5, (
            f'Expected cost_cents 3.5, got {cli_payload["run_state"]["cost_cents"]}'
        )


def test_agent_attach_resume_delegates_to_resume_command() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _seed_run(tmp)
        tea = Path(tmp) / '.teaagent'
        tea.mkdir(parents=True, exist_ok=True)
        (tea / 'config.toml').write_text('provider = "gpt"\n', encoding='utf-8')

        with patch(
            'teaagent.cli._handlers._agent.runs.agent_resume_command',
            return_value=0,
        ) as resume:
            code = main(['agent', 'attach', 'attach-parity', '--resume', '--root', tmp])
        # Verify attach --resume command succeeds
        assert code == 0, f'Expected attach --resume to succeed, got exit code {code}'
        # Verify resume command was called exactly once
        resume.assert_called_once()
        resume_args = resume.call_args[0][0]
        # Verify run_id is passed correctly to resume command
        assert resume_args.run_id == 'attach-parity', (
            f'Expected run_id "attach-parity", got {resume_args.run_id!r}'
        )
        # Verify provider from config is passed to resume command
        assert resume_args.provider == 'gpt', (
            f'Expected provider "gpt", got {resume_args.provider!r}'
        )
