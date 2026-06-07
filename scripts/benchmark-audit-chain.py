#!/usr/bin/env python3
"""Benchmark audit chain hashing and verification performance.

Measures hash computation and chain verification time for event counts
of 10, 100, 1000, and 10000.

Usage:
    python3 scripts/benchmark-audit-chain.py
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
from pathlib import Path
from uuid import uuid4

HERE = Path(__file__).resolve().parent.parent


import teaagent.audit_chain as ac  # noqa: E402


def make_event(
    event_id: str, run_id: str, prev_hash: str, payload_size: int = 256
) -> dict:
    payload = {'key': 'x' * (payload_size - 4)}
    return {
        'event_id': event_id,
        'event_type': 'benchmark_event',
        'run_id': run_id,
        'created_at': '2026-01-01T00:00:00Z',
        'payload': payload,
        'prev_hash': prev_hash,
    }


def generate_chain(count: int, hash_fn=None) -> list[dict]:
    events: list[dict] = []
    prev_hash = ac.GENESIS_HASH
    run_id = uuid4().hex
    for _ in range(count):
        evt = make_event(event_id=uuid4().hex, run_id=run_id, prev_hash=prev_hash)
        h = ac.compute_event_hash(evt)
        evt['hash'] = h
        evt['chain_hmac'] = ''  # skip HMAC for benchmark
        events.append(evt)
        prev_hash = h
    return events


def write_chain(events: list[dict], path: Path) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        for evt in events:
            f.write(json.dumps(evt, sort_keys=True) + '\n')


BENCH_SIZES = [10, 100, 1000, 10000]


def main() -> None:
    print('=' * 70)
    print('Audit Chain Hashing Benchmark')
    print('=' * 70)
    print()

    # --- Hash computation benchmark ---
    print('--- Hash Computation (compute_event_hash) ---')
    print(
        f'{"Events":>8}  {"Total (s)":>10}  {"Per-event (us)":>15}  {"Rate (evt/s)":>12}'
    )
    print('-' * 50)

    for size in BENCH_SIZES:
        run_id = uuid4().hex
        samples: list[dict] = []
        prev_hash = ac.GENESIS_HASH
        for _ in range(size):
            evt = make_event(event_id=uuid4().hex, run_id=run_id, prev_hash=prev_hash)
            samples.append(evt)
            prev_hash = 'dummy'

        start = time.perf_counter()
        for evt in samples:
            h = ac.compute_event_hash(evt)
            evt['hash'] = h
        elapsed = time.perf_counter() - start
        per_event_us = (elapsed / size) * 1_000_000
        rate = size / elapsed if elapsed > 0 else 0
        print(f'{size:>8}  {elapsed:>10.4f}  {per_event_us:>15.1f}  {rate:>12.0f}')

    print()

    # --- Chain verification benchmark ---
    print('--- Chain Verification (verify_audit_chain) ---')
    print(
        f'{"Events":>8}  {"Total (s)":>10}  {"Per-event (us)":>15}  {"Rate (evt/s)":>12}  {"Result":>10}'
    )
    print('-' * 60)

    for size in BENCH_SIZES:
        with tempfile.NamedTemporaryFile(
            suffix='.jsonl', mode='w', encoding='utf-8', delete=False
        ) as tmp:
            tmp_path = Path(tmp.name)
            events = generate_chain(size)
            write_chain(events, tmp_path)

        try:
            start = time.perf_counter()
            result = ac.verify_audit_chain(tmp_path)
            elapsed = time.perf_counter() - start
            per_event = (elapsed / max(result.event_count, 1)) * 1_000_000
            rate = result.event_count / elapsed if elapsed > 0 else 0
            valid_str = 'OK' if result.valid else f'FAIL {len(result.failures)}'
            print(
                f'{size:>8}  {elapsed:>10.4f}  {per_event:>15.1f}  {rate:>12.0f}  {valid_str:>10}'
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    print()

    # --- Hash algorithm comparison ---
    print('--- Hash Algorithm Comparison ---')
    print(f'{"Algo":>10}  {"Total 1k (s)":>13}  {"Per-event (us)":>15}')
    print('-' * 45)

    for alg_name in ('sha256', 'sha1', 'md5'):
        samples = []
        prev_hash = ac.GENESIS_HASH
        run_id = uuid4().hex
        for _ in range(1000):
            evt = make_event(event_id=uuid4().hex, run_id=run_id, prev_hash=prev_hash)
            canonical = json.dumps(
                {
                    'event_id': evt['event_id'],
                    'event_type': evt['event_type'],
                    'run_id': evt['run_id'],
                    'created_at': evt['created_at'],
                    'payload': evt['payload'],
                    'prev_hash': evt['prev_hash'],
                },
                sort_keys=True,
                separators=(',', ':'),
            ).encode('utf-8')
            samples.append(canonical)
            prev_hash = 'dummy'

        start = time.perf_counter()
        if alg_name == 'sha256':
            for s in samples:
                hashlib.sha256(s).hexdigest()
        elif alg_name == 'sha1':
            for s in samples:
                hashlib.sha1(s).hexdigest()
        elif alg_name == 'md5':
            for s in samples:
                hashlib.md5(s).hexdigest()
        elapsed = time.perf_counter() - start
        per_event = (elapsed / len(samples)) * 1_000_000
        print(f'{alg_name:>10}  {elapsed:>13.4f}  {per_event:>15.1f}')

    # Blake3 check
    try:
        import blake3 as blake3_mod

        prev_hash = ac.GENESIS_HASH
        run_id = uuid4().hex
        b3_samples = []
        for _ in range(1000):
            evt = make_event(event_id=uuid4().hex, run_id=run_id, prev_hash=prev_hash)
            canonical = json.dumps(
                {
                    'event_id': evt['event_id'],
                    'event_type': evt['event_type'],
                    'run_id': evt['run_id'],
                    'created_at': evt['created_at'],
                    'payload': evt['payload'],
                    'prev_hash': evt['prev_hash'],
                },
                sort_keys=True,
                separators=(',', ':'),
            ).encode('utf-8')
            b3_samples.append(canonical)
            prev_hash = 'dummy'

        start = time.perf_counter()
        for s in b3_samples:
            blake3_mod.blake3(s).hexdigest()
        elapsed = time.perf_counter() - start
        per_event = (elapsed / len(b3_samples)) * 1_000_000
        print(f'{"blake3":>10}  {elapsed:>13.4f}  {per_event:>15.1f}')
    except ImportError:
        print(f'{"blake3":>10}  {"not installed":>13}  {"N/A":>15}')

    print()
    print('Done.')


if __name__ == '__main__':
    main()
