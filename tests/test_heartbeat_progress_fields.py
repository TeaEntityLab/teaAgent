# test-type: behavior
from __future__ import annotations

import time
from typing import Any, Optional

from conftest import FakeAdapter

from teaagent import AuditLogger, ChatAgentConfig, Heartbeat, RunStore, run_chat_agent


def _heartbeat_payloads(audit: AuditLogger) -> list[dict[str, Any]]:
    return [e.payload for e in audit.events if e.event_type == 'heartbeat']


def test_tick_payload_carries_tool_elapsed_cost_and_checkpoint() -> None:
    audit = AuditLogger()
    checkpoint = {'call_id': 'read-1', 'at': '2026-10-27T00:00:00+00:00'}

    def provider() -> Optional[dict[str, Any]]:
        return {
            'tool': 'workspace_read_file',
            'elapsed_seconds': 12.5,
            'cost_cents': 3.2,
            'checkpoint': checkpoint,
        }

    beat = Heartbeat(
        audit,
        'run-progress',
        interval_seconds=30.0,
        progress=provider,
    )
    beat.tick()

    (payload,) = _heartbeat_payloads(audit)
    assert payload['tick'] == 1
    assert payload['interval_seconds'] == 30.0
    assert payload['tool'] == 'workspace_read_file'
    assert payload['elapsed_seconds'] == 12.5
    assert payload['cost_cents'] == 3.2
    assert payload['checkpoint'] == checkpoint


def test_tick_without_provider_keeps_legacy_payload() -> None:
    audit = AuditLogger()
    beat = Heartbeat(audit, 'run-legacy', interval_seconds=5.0)
    beat.tick()

    (payload,) = _heartbeat_payloads(audit)
    assert payload == {'tick': 1, 'interval_seconds': 5.0}


def test_tick_omits_fields_the_provider_does_not_return() -> None:
    audit = AuditLogger()
    beat = Heartbeat(
        audit,
        'run-partial',
        interval_seconds=5.0,
        progress=lambda: {'elapsed_seconds': 1.0},
    )
    beat.tick()

    (payload,) = _heartbeat_payloads(audit)
    assert payload == {'tick': 1, 'interval_seconds': 5.0, 'elapsed_seconds': 1.0}


def test_provider_cannot_overwrite_tick_or_inject_unknown_keys() -> None:
    audit = AuditLogger()
    beat = Heartbeat(
        audit,
        'run-guard',
        interval_seconds=5.0,
        progress=lambda: {'tick': 999, 'run_id': 'other', 'cost_cents': 1.5},
    )
    beat.tick()

    (payload,) = _heartbeat_payloads(audit)
    assert payload['tick'] == 1
    assert 'run_id' not in payload
    assert payload['cost_cents'] == 1.5


def test_failing_provider_does_not_stop_the_tick() -> None:
    audit = AuditLogger()

    def broken() -> Optional[dict[str, Any]]:
        raise RuntimeError('state unavailable')

    beat = Heartbeat(
        audit,
        'run-broken',
        interval_seconds=5.0,
        progress=broken,
    )
    beat.tick()

    (payload,) = _heartbeat_payloads(audit)
    assert payload['tick'] == 1
    assert payload['progress_unavailable'] is True


def test_real_run_emits_heartbeat_with_current_tool_and_elapsed(
    chat_agent_config: ChatAgentConfig,
    tmp_run_store: RunStore,
) -> None:
    (chat_agent_config.root / 'note.txt').write_text('hello', encoding='utf-8')
    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"note.txt"},"call_id":"read-hb"}',
            '{"type":"final","content":"done"}',
        ],
        before_each=lambda: time.sleep(0.05),
    )
    audit = tmp_run_store.audit_logger()

    result = run_chat_agent(
        ChatAgentConfig.from_root(chat_agent_config.root, heartbeat_seconds=0.02),
        'read the note',
        adapter=adapter,
        audit=audit,
    )
    tmp_run_store.logger_for_result(result, audit)

    assert result.status == 'completed'
    beats = [e.payload for e in audit.events if e.event_type == 'heartbeat']
    with_tool = [b for b in beats if b.get('tool') == 'workspace_read_file']
    assert with_tool, 'expected at least one heartbeat to name the running tool'
    assert all(b['elapsed_seconds'] >= 0 for b in with_tool)
    assert all(b['cost_cents'] >= 0 for b in with_tool)
