"""WDF-001 root module freeze."""

from __future__ import annotations

from scripts.check_root_module_count import ROOT_BASELINE, count_root_modules


def test_root_module_count_within_baseline() -> None:
    assert count_root_modules() <= ROOT_BASELINE
