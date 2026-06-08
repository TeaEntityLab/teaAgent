"""Performance benchmarks for audit chain operations (TST-009)."""

from __future__ import annotations

import time

import pytest

from teaagent.types import compute_event_hash, verify_audit_chain


def _chain(n: int) -> list[dict]:
    events = []
    prev = 'genesis'
    for i in range(n):
        event = {
            'event_id': f'e{i}',
            'event_type': 'test',
            'run_id': 'bench',
            'created_at': f'2024-01-01T00:{i % 60:02d}:00Z',
            'payload': {'i': i},
            'prev_hash': prev,
        }
        event['event_hash'] = compute_event_hash(event)
        prev = event['event_hash']
        events.append(event)
    return events


@pytest.mark.slow
def test_audit_chain_verify_scales_linearly_enough():
    small = _chain(100)
    large = _chain(1000)
    t0 = time.perf_counter()
    assert verify_audit_chain(small).valid
    small_ms = (time.perf_counter() - t0) * 1000
    t1 = time.perf_counter()
    assert verify_audit_chain(large).valid
    large_ms = (time.perf_counter() - t1) * 1000
    # 10x events should not exceed 50x time (sanity guard, not strict perf SLA)
    assert large_ms < max(small_ms * 50, 5000)
