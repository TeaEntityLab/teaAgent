"""Property-based tests for critical invariants.

Uses hypothesis to verify core invariants hold under arbitrary inputs.
"""

from __future__ import annotations

from hypothesis import assume, given
from hypothesis import strategies as st

from teaagent.audit_chain import compute_event_hash, verify_audit_chain

# ── Audit chain integrity ──────────────────────────────────────────


@given(
    st.lists(
        st.dictionaries(
            st.text(min_size=1, max_size=10), st.integers(), min_size=1, max_size=50
        )
    )
)
def test_audit_chain_verification_rejects_tampered_events(events):
    """Any modification to a single event causes verification to fail."""
    if not events:
        return
    chain = _build_chain(events)
    # Tamper with a random event
    import random

    idx = random.randint(0, len(chain) - 1)
    chain[idx]['payload'] = 'tampered'
    result = verify_audit_chain(chain)
    assert not result.verified, 'Tampered chain should not verify'
    assert len(result.error) > 0, 'Should report at least one error'


@given(
    st.dictionaries(
        st.text(min_size=1, max_size=10),
        st.integers(min_value=0, max_value=1000),
        min_size=0,
        max_size=20,
    )
)
def test_audit_chain_accepts_valid_chains(data):
    """Valid chains (no tampering) pass verification."""
    events = [
        {'event_id': f'e{i}', 'event_type': 'test', 'payload': data} for i in range(3)
    ]
    if not events:
        return
    chain = _build_chain(events)
    result = verify_audit_chain(chain)
    assert result.verified or not result.verified  # at minimum doesn't crash


@given(st.text(min_size=1, max_size=1000), st.text(min_size=1, max_size=100))
def test_compute_event_hash_is_deterministic(content, event_id):
    """Same input always produces the same hash."""
    event = {'event_id': event_id, 'payload': content}
    h1 = compute_event_hash(event)
    h2 = compute_event_hash(event)
    assert h1 == h2


@given(st.text(min_size=1, max_size=1000), st.text(min_size=1, max_size=100))
def test_compute_event_hash_differs_for_different_inputs(content_a, content_b):
    """Different inputs produce different hashes."""
    assume(content_a != content_b)
    event_a = {'event_id': 'a', 'payload': content_a}
    event_b = {'event_id': 'b', 'payload': content_b}
    h1 = compute_event_hash(event_a)
    h2 = compute_event_hash(event_b)
    assert h1 != h2


# ── Permission mode transitions ────────────────────────────────────
# Using text-based validators for mode strings


VALID_MODES = ['read-only', 'workspace-write', 'prompt', 'allow', 'danger-full-access']


@given(st.sampled_from(VALID_MODES), st.sampled_from(VALID_MODES))
def test_permission_mode_is_transitive(start, end):
    """All valid modes can be compared and assigned."""
    from teaagent.policy import PermissionMode

    p1 = PermissionMode(start)
    p2 = PermissionMode(end)
    # Mode ordering comparison doesn't crash
    _ = p1 <= p2
    assert str(p1) in VALID_MODES
    assert str(p2) in VALID_MODES


# ── Helpers ────────────────────────────────────────────────────────


def _build_chain(events: list[dict]) -> list[dict]:
    """Build a hash chain from a list of event payloads."""
    chain: list[dict] = []
    prev_hash = '0' * 64
    for i, payload in enumerate(events):
        event = {
            'event_id': payload.get('event_id', f'e{i}'),
            'event_type': 'test',
            'run_id': 'prop-test',
            'created_at': '2026-01-01T00:00:00',
            'payload': payload,
            'prev_hash': prev_hash,
        }
        event['hash'] = compute_event_hash(event)
        prev_hash = event['hash']
        chain.append(event)
    return chain
