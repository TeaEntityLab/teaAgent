"""ADR-0043 quarantine markers must stay on non-goal surfaces.

The 2026-09-09 review found pre-2026-06-13 code implementing the harness-first
section 2 non-goals still imported, CLI-exposed, and CI-gated with no visible
record at the code surface. ADR-0043 quarantines these surfaces as
legacy-competitive with a 2026-12-09 disposition. These markers are the code
surface of that record: removing one re-hides the contradiction, so removal
must fail here rather than silently.
"""

from __future__ import annotations

import importlib

import pytest

_QUARANTINED_MODULES = (
    'teaagent.federated_sync',
    'teaagent.signature_relay',
    'teaagent.domain.workflow_engine',
    'teaagent.consensus',
    'teaagent.consensus.engine',
    'teaagent.consensus.voting',
    'teaagent.consensus.peer_registry',
    'teaagent.consensus.types',
    'teaagent.cli._handlers._consensus',
    'teaagent.jit_approval_server',
)


@pytest.mark.parametrize('module_name', _QUARANTINED_MODULES)
def test_quarantined_surface_names_adr0043(module_name: str) -> None:
    module = importlib.import_module(module_name)
    doc = module.__doc__ or ''
    assert 'ADR-0043' in doc, (
        f'{module_name} lost its ADR-0043 quarantine notice; '
        're-add it or record the 2026-12-09 disposition first'
    )
    assert '2026-12-09' in doc, (
        f'{module_name} quarantine notice lost its expiry date; '
        'the quarantine is dated, not permanent'
    )
    assert 'owner-override' in doc, (
        f'{module_name} quarantine notice lost its scheduling rule; '
        'DR-006 requires a dated owner-override for new work'
    )
