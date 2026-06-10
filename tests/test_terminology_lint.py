"""WDC-004 terminology freeze."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TERMINOLOGY = REPO / 'docs' / 'terminology.md'

CANONICAL_NOUNS = (
    'tenant',
    'workspace',
    'session',
    'run',
    'goal',
    'background',
)


def test_terminology_declares_canonical_nouns() -> None:
    text = TERMINOLOGY.read_text(encoding='utf-8').lower()
    for noun in CANONICAL_NOUNS:
        assert noun in text, f'missing canonical noun: {noun}'
