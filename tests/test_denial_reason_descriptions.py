# test-type: contract
"""Every recorded denial reason has a human-readable `why-denied` description."""

from __future__ import annotations

from teaagent.cli._handlers._ergonomics.approval import _DENIAL_REASON_DESCRIPTIONS
from teaagent.errors import DenialReasonCode

# Reason codes recorded on tool_call_denied that are not DenialReasonCode
# members: the pending-approval TTL auto-deny (teaagent/run_store.py).
_EXTRA_RECORDED_CODES = ('expired',)


def test_every_denial_reason_code_has_a_description() -> None:
    missing = [
        code.value
        for code in DenialReasonCode
        if code.value not in _DENIAL_REASON_DESCRIPTIONS
    ]
    assert missing == []


def test_recorded_non_enum_codes_have_descriptions() -> None:
    for code in _EXTRA_RECORDED_CODES:
        assert _DENIAL_REASON_DESCRIPTIONS.get(code), code


def test_descriptions_are_not_placeholders() -> None:
    for code, text in _DENIAL_REASON_DESCRIPTIONS.items():
        assert text.strip(), code
        assert 'Unknown' not in text, code
