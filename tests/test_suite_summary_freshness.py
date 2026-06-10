"""WDB-004 suite summary freshness validator."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.validate_docs_consistency import validate_suite_summary_freshness


def test_stale_summary_warns_on_test_count_claims() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        doc = root / 'roadmap.md'
        doc.write_text('H1 complete — 4758 tests pass at HEAD\n', encoding='utf-8')
        summary_path = root / 'suite-summary.json'
        stale = datetime.now(timezone.utc) - timedelta(hours=96)
        summary_path.write_text(
            json.dumps({'generated_at': stale.isoformat()}) + '\n',
            encoding='utf-8',
        )
        errors = validate_suite_summary_freshness(
            docs_to_scan=[doc],
            summary_path=summary_path,
            max_age_hours=72.0,
        )
        assert errors


def test_fresh_summary_passes() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        doc = root / 'roadmap.md'
        doc.write_text('628 tests pass on acceptance tier\n', encoding='utf-8')
        summary_path = root / 'suite-summary.json'
        fresh = datetime.now(timezone.utc) - timedelta(hours=1)
        summary_path.write_text(
            json.dumps({'generated_at': fresh.isoformat()}) + '\n',
            encoding='utf-8',
        )
        errors = validate_suite_summary_freshness(
            docs_to_scan=[doc],
            summary_path=summary_path,
        )
        assert not errors
