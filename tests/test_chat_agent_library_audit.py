"""S-P0-3 (ADR-0035): library audit durability tests.

When ``run_chat_agent`` is called without an explicit ``audit`` logger it
must default to a *durable* JSONL audit log on disk (via ``RunStore``)
rather than an in-memory logger.  The ``no_audit=True`` opt-out must emit
a single ``audit_disabled`` warning to stderr and keep events in memory
only, writing no file.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from conftest import FakeAdapter

from teaagent import ChatAgentConfig, run_chat_agent
from teaagent.run_store import RunStore
from teaagent.types import AuditLogger, verify_audit_chain


def _final_adapter() -> FakeAdapter:
    return FakeAdapter(['{"type":"final","content":"done"}'])


def test_durable_jsonl_created_when_audit_is_none(
    tmp_path: Path,
) -> None:
    """(a) When audit is None a durable JSONL file is created on disk."""
    run_id = 'durable-run-001'
    config = ChatAgentConfig.from_root(tmp_path, max_iterations=1, max_tool_calls=0)

    # Patch home so the per-run HMAC key is stored inside tmp_path and
    # cleaned up with the test.
    with patch.object(Path, 'home', return_value=tmp_path):
        result = run_chat_agent(
            config,
            'say done',
            adapter=_final_adapter(),
            run_id=run_id,
        )

    assert result.status == 'completed'

    audit_path = RunStore(tmp_path).run_path(run_id)
    assert audit_path.is_file(), f'durable audit JSONL not created at {audit_path}'

    lines = [
        line
        for line in audit_path.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]
    assert len(lines) >= 1
    for line in lines:
        entry = json.loads(line)
        assert entry['run_id'] == run_id
        assert 'prev_hash' in entry
        assert 'hash' in entry
        assert 'chain_hmac' in entry


def test_durable_audit_chain_validates(tmp_path: Path) -> None:
    """(c) The durable audit log written by run_chat_agent validates."""
    run_id = 'durable-chain-001'
    config = ChatAgentConfig.from_root(tmp_path, max_iterations=1, max_tool_calls=0)

    with patch.object(Path, 'home', return_value=tmp_path):
        run_chat_agent(
            config,
            'say done',
            adapter=_final_adapter(),
            run_id=run_id,
        )
        audit_path = RunStore(tmp_path).run_path(run_id)
        result = verify_audit_chain(audit_path)

    assert result.valid, f'chain invalid: {result.error}; failures={result.failures}'
    assert result.event_count >= 1


def test_no_audit_emits_warning_and_writes_no_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """(b) no_audit=True emits an audit_disabled warning and writes no file."""
    run_id = 'no-audit-run-001'
    config = ChatAgentConfig.from_root(tmp_path, max_iterations=1, max_tool_calls=0)

    with patch.object(Path, 'home', return_value=tmp_path):
        result = run_chat_agent(
            config,
            'say done',
            adapter=_final_adapter(),
            run_id=run_id,
            no_audit=True,
        )

    assert result.status == 'completed'

    captured = capsys.readouterr()
    assert 'audit_disabled' in captured.err

    # No durable audit file should exist for this run.
    audit_path = RunStore(tmp_path).run_path(run_id)
    assert not audit_path.is_file(), (
        f'no_audit=True should not write a file, but {audit_path} exists'
    )


def test_explicit_audit_logger_is_respected(tmp_path: Path) -> None:
    """An explicit audit logger is used as-is (no durable default created)."""
    run_id = 'explicit-audit-001'
    config = ChatAgentConfig.from_root(tmp_path, max_iterations=1, max_tool_calls=0)
    explicit_path = tmp_path / 'custom-audit.jsonl'

    with patch.object(Path, 'home', return_value=tmp_path):
        explicit_audit = AuditLogger(path=explicit_path)
        run_chat_agent(
            config,
            'say done',
            adapter=_final_adapter(),
            run_id=run_id,
            audit=explicit_audit,
        )

    assert explicit_path.is_file()
    # The RunStore default path should NOT be created when an explicit
    # logger is supplied.
    assert not RunStore(tmp_path).run_path(run_id).is_file()
