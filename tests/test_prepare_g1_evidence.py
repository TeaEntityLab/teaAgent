# test-type: contract
"""G1 evidence denominator tests (B-01).

Falsifier: a `frictionless` verdict while the runs index shows zero organic
runs means the denominator gate is broken. Organic requires positive proof —
origin == 'owner' — never the absence of a known fixture string.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from prepare_g1_evidence import (  # noqa: E402
    build_g1_evidence_report,
    load_friction_entries,
    load_runs_index,
)


def _run(
    task: str,
    created_at: str = '2026-09-10T12:00:00+00:00',
    origin: str | None = None,
) -> dict:
    row = {'run_id': 'r1', 'task': task, 'created_at': created_at}
    if origin is not None:
        row['origin'] = origin
    return row


def _friction_log(tmp_path: Path, body: str) -> Path:
    path = tmp_path / 'friction.md'
    path.write_text(body, encoding='utf-8')
    return path


def test_zero_organic_runs_is_unexercised_not_frictionless():
    """All-synthetic runs must never report frictionless — that is the
    null-signal bug this instrument exists to kill."""
    runs = [
        _run('Reply with exactly: Hello from CLI test'),
        _run('Update docs/cli.md to document clarify command'),
    ]
    report = build_g1_evidence_report(runs, [])
    assert report.verdict == 'unexercised'
    assert report.organic_runs == 0
    assert report.synthetic_runs == 2


def test_unknown_origin_never_counts_as_organic():
    """A run with no origin field (or origin='unknown') is NOT organic —
    positive proof only, so a new synthetic string can't false-positive."""
    runs = [
        _run('Refactor the auth module for readability'),  # no origin
        _run('Another plausible task', origin='unknown'),
        _run('Agent task', origin='agent'),
    ]
    report = build_g1_evidence_report(runs, [])
    assert report.organic_runs == 0
    assert report.unknown_runs == 3
    assert report.verdict == 'unexercised'


def test_owner_origin_counts_as_organic(tmp_path):
    log = _friction_log(
        tmp_path,
        '### 2026-09-10 - Something broke\n- **Status:** open\n',
    )
    entries = load_friction_entries(log)
    report = build_g1_evidence_report(
        [_run('Refactor the auth module', origin='owner')], entries
    )
    assert report.verdict == 'friction_observed'
    assert report.organic_runs == 1


def test_organic_run_without_open_friction_is_frictionless(tmp_path):
    log = _friction_log(
        tmp_path,
        '### 2026-09-10 - Old issue\n- **Status:** closed\n',
    )
    entries = load_friction_entries(log)
    report = build_g1_evidence_report(
        [_run('Refactor the auth module', origin='owner')], entries
    )
    assert report.verdict == 'frictionless'
    assert report.doc_lookup_instrumented is False


def test_window_bounds_exclude_out_of_range_runs():
    runs = [
        _run('Organic task A', created_at='2026-09-01T00:00:00+00:00', origin='owner'),
        _run('Organic task B', created_at='2026-09-20T00:00:00+00:00', origin='owner'),
    ]
    report = build_g1_evidence_report(runs, [], since='2026-09-05', until='2026-09-15')
    assert report.organic_runs == 0
    assert report.verdict == 'unexercised'


def test_window_bounds_are_inclusive():
    runs = [
        _run('In window', created_at='2026-09-05T00:00:00+00:00', origin='owner'),
        _run('Also in', created_at='2026-09-15T23:59:00+00:00', origin='owner'),
    ]
    report = build_g1_evidence_report(runs, [], since='2026-09-05', until='2026-09-15')
    assert report.organic_runs == 2


def test_invalid_window_raises():
    import pytest

    with pytest.raises(ValueError, match='since must be <= until'):
        build_g1_evidence_report([], [], since='2026-09-15', until='2026-09-05')


def test_load_runs_index_skips_malformed(tmp_path):
    index = tmp_path / 'runs-index.jsonl'
    index.write_text(
        '{"run_id": "a", "task": "real work", "origin": "owner", "created_at": "2026-09-10T00:00:00+00:00"}\n'
        'not json\n'
        '{"run_id": "b", "task": "Reply with exactly: x", "created_at": "2026-09-10T00:00:00+00:00"}\n',
        encoding='utf-8',
    )
    rows = load_runs_index(index)
    assert len(rows) == 2
    report = build_g1_evidence_report(rows, [])
    assert report.organic_runs == 1
    assert report.synthetic_runs == 1
