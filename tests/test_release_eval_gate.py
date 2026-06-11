"""Tests for release eval gate wiring (WDA-004 / WDD-001)."""

from __future__ import annotations

import tempfile

from teaagent.release_gate import ReleaseDecision

from teaagent.eval_corpus import (
    RELEASE_EVAL_SUITE_ID,
    create_conversational_quality_tests,
    register_release_eval_suite,
)
from teaagent.eval_suite import EvalCategory, EvalStore
from teaagent.governance.release_eval import (
    run_release_eval_gate,
    should_block_release,
)


def test_conversational_corpus_covers_four_axes() -> None:
    tests = create_conversational_quality_tests()
    axes = {test.metadata['axis'] for test in tests}
    assert axes == {
        'clarification',
        'interruption',
        'correction',
        'long_context_recall',
    }


def test_register_release_eval_suite_includes_conversational_category() -> None:
    import os

    tmp_path = None
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = tmp
        store = EvalStore(tmp)
        register_release_eval_suite(store)
        suite = store.load_suite(RELEASE_EVAL_SUITE_ID)
        assert suite is not None
        conversational = suite.get_tests_by_category(EvalCategory.CONVERSATIONAL)
        assert len(conversational) == 4
    # Verify cleanup
    assert not os.path.exists(tmp_path), (
        f'Temporary directory {tmp_path} was not cleaned up'
    )


def test_release_gate_passes_on_green_corpus() -> None:
    import os

    tmp_path = None
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = tmp
        result = run_release_eval_gate(tmp, seed_failure=False)
    assert result.decision == ReleaseDecision.APPROVE
    assert not should_block_release(result)
    # Verify cleanup
    assert not os.path.exists(tmp_path), (
        f'Temporary directory {tmp_path} was not cleaned up'
    )


def test_seeded_regression_fixture_blocks_release() -> None:
    import os

    tmp_path = None
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = tmp
        result = run_release_eval_gate(tmp, seed_failure=True)
    assert result.decision == ReleaseDecision.BLOCK
    assert should_block_release(result)
    assert result.failed_tests > 0
    # Verify cleanup
    assert not os.path.exists(tmp_path), (
        f'Temporary directory {tmp_path} was not cleaned up'
    )
