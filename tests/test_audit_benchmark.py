"""Performance benchmarks for audit chain operations (TST-009)."""

from __future__ import annotations

import time

import pytest

from teaagent.types import compute_event_hash, verify_audit_chain


def _chain(n: int) -> list[dict]:
    events = []
    prev = 'genesis'
    for i in range(n):
        # Generate monotonic timestamps using i to avoid regression failures
        event = {
            'event_id': f'e{i}',
            'event_type': 'test',
            'run_id': 'bench',
            'created_at': f'2024-01-01T00:{i // 60:02d}:{i % 60:02d}Z',
            'payload': {'i': i},
            'prev_hash': prev,
        }
        event['event_hash'] = compute_event_hash(event)
        prev = event['event_hash']
        events.append(event)
    return events


@pytest.mark.slow
def test_audit_chain_verify_scales_linearly_enough():
    import json
    import tempfile
    from pathlib import Path

    small = _chain(100)
    large = _chain(1000)

    def verify_list(events: list[dict]) -> bool:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.jsonl', delete=False, encoding='utf-8'
        ) as tmp:
            for event in events:
                event_to_write = dict(event)
                if 'event_hash' in event_to_write:
                    event_to_write['hash'] = event_to_write.pop('event_hash')
                tmp.write(json.dumps(event_to_write) + '\n')
            tmp_path = Path(tmp.name)
        try:
            return verify_audit_chain(tmp_path).valid
        finally:
            tmp_path.unlink()

    t0 = time.perf_counter()
    assert verify_list(small)
    small_ms = (time.perf_counter() - t0) * 1000
    t1 = time.perf_counter()
    assert verify_list(large)
    large_ms = (time.perf_counter() - t1) * 1000
    # 10x events should not exceed 50x time (sanity guard, not strict perf SLA)
    assert large_ms < max(small_ms * 50, 5000)
