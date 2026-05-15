from __future__ import annotations

from teaagent.memory import MemoryCatalog


def test_memory_search_prioritizes_auto_curated_run_summaries(tmp_path):
    catalog = MemoryCatalog(tmp_path)

    # Newer but weaker match should not outrank a stronger curated summary.
    catalog.add(
        'README notes only mention summary at a high level',
        tags=('notes',),
    )
    curated = catalog.add(
        'Task: Summarize README\nOutcome: summarized README with key architecture points',
        tags=('auto-curated', 'run-summary'),
    )
    catalog.add(
        'README summary draft from manual notes',
        tags=('manual',),
    )

    results = catalog.search('readme summary', limit=3)

    assert results
    assert results[0].memory_id == curated.memory_id
