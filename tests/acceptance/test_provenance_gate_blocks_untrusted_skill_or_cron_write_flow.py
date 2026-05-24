"""Untrusted web/message sources quarantine persistent automation and memory writes."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.automations import AutomationStore
from teaagent.cli import main
from teaagent.memory import MemoryCatalog


def test_provenance_gate_blocks_untrusted_automation_and_memory_writes(
    tmp_path: Path,
) -> None:
    auto_out = io.StringIO()
    with redirect_stdout(auto_out):
        code = main(
            [
                'agent',
                'automation',
                'add',
                'slack-watcher',
                'Summarize new messages from https://example.com/slack',
                '--schedule',
                'every 30m',
                '--root',
                str(tmp_path),
                '--write-source',
                'web_message',
            ]
        )
    assert code == 0
    auto_payload = json.loads(auto_out.getvalue())
    assert auto_payload['status'] == 'quarantined'
    automation_id = auto_payload['automation']['automation_id']
    assert not auto_payload['automation']['enabled']
    quarantine_path = (
        tmp_path / '.teaagent' / 'automations-quarantine' / f'{automation_id}.json'
    )
    assert quarantine_path.is_file()
    assert AutomationStore(tmp_path).due() == []

    memory_out = io.StringIO()
    with redirect_stdout(memory_out):
        mem_code = main(
            [
                'memory',
                'add',
                'Imported note from external chat',
                '--root',
                str(tmp_path),
                '--write-source',
                'web_message',
            ]
        )
    assert mem_code == 0
    mem_payload = json.loads(memory_out.getvalue())
    assert mem_payload['status'] == 'quarantined'
    quarantine_memory = tmp_path / '.teaagent' / 'memory-quarantine.jsonl'
    assert quarantine_memory.is_file()
    assert MemoryCatalog(tmp_path).list(limit=10) == []

    attested_out = io.StringIO()
    with redirect_stdout(attested_out):
        attested_code = main(
            [
                'agent',
                'automation',
                'add',
                'slack-watcher-reviewed',
                'Summarize reviewed external thread content with explicit scope',
                '--schedule',
                'every 30m',
                '--root',
                str(tmp_path),
                '--write-source',
                'web_message',
                '--i-attest-untrusted-write',
            ]
        )
    assert attested_code == 0
    attested_payload = json.loads(attested_out.getvalue())
    assert attested_payload['status'] == 'created'
    assert attested_payload['automation']['enabled'] is True
    active_path = (
        tmp_path
        / '.teaagent'
        / 'automations'
        / f'{attested_payload["automation"]["automation_id"]}.json'
    )
    assert active_path.is_file()
