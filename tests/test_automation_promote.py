from __future__ import annotations

from pathlib import Path

import pytest

from teaagent.automation_ticket import compute_automation_provenance_digest
from teaagent.automations import AutomationStore
from teaagent.provenance_gate import ProvenanceSourceKind


def test_promote_quarantined_moves_to_active_dir(tmp_path: Path) -> None:
    store = AutomationStore(tmp_path)
    spec = store.draft(
        name='web-cron',
        task='Summarize external feed items with explicit scope and output path',
        schedule='every 30m',
        provider=None,
        model=None,
        permission_mode='read-only',
        context_profile='lean',
        max_iterations=3,
        max_tool_calls=3,
        enabled=False,
    )
    store.create_quarantined(
        spec,
        provenance={
            'source_kind': ProvenanceSourceKind.LOCAL.value,
            'action': 'quarantine',
        },
    )
    promoted = store.promote_quarantined(spec.automation_id)
    assert promoted.enabled is True
    assert store.show(spec.automation_id).name == 'web-cron'
    assert not (
        tmp_path / '.teaagent' / 'automations-quarantine' / f'{spec.automation_id}.json'
    ).exists()


def test_promote_web_message_requires_attestation(tmp_path: Path) -> None:
    store = AutomationStore(tmp_path)
    spec = store.draft(
        name='web-cron',
        task='Summarize external feed items with explicit scope and output path',
        schedule='every 30m',
        provider=None,
        model=None,
        permission_mode='read-only',
        context_profile='lean',
        max_iterations=3,
        max_tool_calls=3,
        enabled=False,
    )
    store.create_quarantined(
        spec,
        provenance={'source_kind': 'web_message', 'action': 'quarantine'},
    )
    with pytest.raises(ValueError, match='web_message'):
        store.promote_quarantined(spec.automation_id)
    promoted = store.promote_quarantined(spec.automation_id, attested=True)
    assert promoted.enabled is True


def test_promote_quarantined_rejects_payload_digest_tamper(tmp_path: Path) -> None:
    store = AutomationStore(tmp_path)
    spec = store.draft(
        name='web-cron',
        task='Summarize external feed items with explicit scope and output path',
        schedule='every 30m',
        provider=None,
        model=None,
        permission_mode='read-only',
        context_profile='lean',
        max_iterations=3,
        max_tool_calls=3,
        collector_command='python3 collector.py',
        provenance_digest='',
        enabled=False,
    )
    spec = type(spec)(
        **{
            **spec.to_dict(),
            'provenance_digest': compute_automation_provenance_digest(spec),
        }
    )
    store.create_quarantined(
        spec,
        provenance={
            'source_kind': ProvenanceSourceKind.LOCAL.value,
            'content_digest': spec.provenance_digest,
        },
    )
    path = (
        tmp_path / '.teaagent' / 'automations-quarantine' / f'{spec.automation_id}.json'
    )
    payload = path.read_text(encoding='utf-8')
    path.write_text(
        payload.replace('python3 collector.py', 'python3 changed.py'), encoding='utf-8'
    )

    with pytest.raises(ValueError, match='provenance_digest'):
        store.promote_quarantined(spec.automation_id)
