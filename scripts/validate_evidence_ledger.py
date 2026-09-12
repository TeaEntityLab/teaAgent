#!/usr/bin/env python3
"""Validate delivery evidence-ledger shape and freshness honesty.

A delivery evidence ledger (``.teaagent/delivery/*/evidence-ledger.yaml``)
records which claims were re-observed and which are pinned history. The 2026-09-12
agentflow-structures panel found the ledger had zero code consumers and already
held a self-contradictory entry (``freshness_kind: recheck_date`` with
``date_checked: unknown``) that nothing flagged. This gate makes that class of
contradiction fail deterministically.

Rules per entry:
- Required keys: ``claim``, ``source``, ``attester``, ``freshness_kind``,
  ``date_checked``.
- ``attester`` must be present, non-empty, and not ``unknown``.
- ``freshness_kind`` must be ``recheck_date`` or ``immutable_pin``.
- ``date_checked`` must be a parseable ``YYYY-MM-DD`` calendar date, never
  ``unknown`` — for both kinds (a pin still records when it was taken).
- ``immutable_pin`` additionally requires ``pinned_commit`` (non-empty,
  non-``unknown``): a pin with no anchor is a recheck claim wearing a pin's
  name. Retag anchorless history as ``recheck_date`` instead.

Exits 0 when no ledgers exist (fresh clones carry no ``.teaagent/`` delivery
state) or every entry validates; exits 1 with one actionable line per bad
entry otherwise. Enforcing by default, never advisory-only.
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_GLOB = '.teaagent/delivery/*/evidence-ledger.yaml'

REQUIRED_KEYS = frozenset(
    {'claim', 'source', 'attester', 'freshness_kind', 'date_checked'}
)
FRESHNESS_KINDS = frozenset({'recheck_date', 'immutable_pin'})


def _is_unknown(value: object) -> bool:
    """Return True for missing, empty, or explicitly unknown values."""
    return value is None or (
        isinstance(value, str)
        and value.strip().lower() in ('', 'unknown', 'n/a', 'none')
    )


def _is_calendar_date(value: object) -> bool:
    """Return True when value parses as a YYYY-MM-DD calendar date."""
    if not isinstance(value, str):
        return False
    try:
        datetime.date.fromisoformat(value.strip())
    except ValueError:
        return False
    return True


def validate_entry(entry: object, *, origin: str, index: int) -> list[str]:
    """Validate one ledger entry mapping; return a list of error strings."""
    where = f'{origin}:entry#{index}'
    if not isinstance(entry, dict):
        return [f'{where}: entry must be a mapping, got {type(entry).__name__}']
    errors = []
    missing = REQUIRED_KEYS - set(entry)
    if missing:
        errors.append(f'{where}: missing required keys: {sorted(missing)}')
    if _is_unknown(entry.get('attester')):
        errors.append(
            f'{where}: attester must name how the claim was checked, not unknown'
        )
    kind = entry.get('freshness_kind')
    if kind not in FRESHNESS_KINDS:
        errors.append(
            f'{where}: freshness_kind must be one of {sorted(FRESHNESS_KINDS)}, '
            f'got {kind!r}'
        )
    if not _is_calendar_date(entry.get('date_checked')):
        errors.append(
            f'{where}: date_checked must be a YYYY-MM-DD calendar date, '
            f'got {entry.get("date_checked")!r}'
        )
    if kind == 'immutable_pin' and _is_unknown(entry.get('pinned_commit')):
        errors.append(
            f'{where}: immutable_pin requires pinned_commit (the anchored revision); '
            'retag anchorless history as recheck_date instead'
        )
    claim = entry.get('claim')
    if not isinstance(claim, str) or not claim.strip():
        errors.append(f'{where}: claim must be a non-empty string')
    return errors


def validate_ledger(path: Path) -> list[str]:
    """Validate one ledger file; return a list of error strings."""
    try:
        import yaml
    except ImportError as exc:
        return [f'{path}: requires pyyaml ({exc})']
    try:
        payload = yaml.safe_load(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        return [f'{path}: unreadable ledger ({exc})']
    if not isinstance(payload, dict) or not isinstance(payload.get('entries'), list):
        return [f'{path}: ledger must be a mapping with an entries list']
    errors: list[str] = []
    for index, entry in enumerate(payload['entries']):
        errors.extend(validate_entry(entry, origin=str(path), index=index))
    return errors


def find_ledgers(repo_root: Path = _REPO_ROOT) -> list[Path]:
    """Return every delivery evidence-ledger under the repo root, sorted."""
    return sorted(repo_root.glob(_DEFAULT_GLOB))


def main(argv: list[str] | None = None) -> int:
    """Validate evidence ledgers; exit 0 on pass, 1 on any schema violation."""
    parser = argparse.ArgumentParser(
        description='Validate delivery evidence-ledger shape and freshness honesty.',
    )
    parser.add_argument(
        '--ledger',
        default=None,
        help='Validate one ledger file instead of scanning .teaagent/delivery/*.',
    )
    args = parser.parse_args(argv)

    paths = [Path(args.ledger)] if args.ledger else find_ledgers()
    if not paths:
        print('no evidence ledgers found; nothing to validate')
        return 0
    errors: list[str] = []
    for path in paths:
        errors.extend(validate_ledger(path))
    if errors:
        for error in errors:
            print(f'ERROR: {error}', file=sys.stderr)
        print(
            'stale or dishonest evidence ledger: fix the entries above, '
            'do not weaken this gate',
            file=sys.stderr,
        )
        return 1
    print(f'evidence ledger check passed ({len(paths)} file(s)).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
