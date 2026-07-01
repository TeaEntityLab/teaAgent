"""Tests for release eval gate wiring (WDA-004 / WDD-001)."""

from __future__ import annotations

import tempfile

from teaagent.release_gate import ReleaseDecision

from teaagent.eval_corpus import (
    RELEASE_EVAL_SUITE_ID,
    create_conversational_quality_tests,
    register_release_eval_suite,
)
from teaagent.eval_suite import EvalCategory, EvalStore, EvalSuite, EvalTest
from teaagent.governance.release_eval import (
    format_gate_summary,
    run_release_eval_gate,
    should_block_release,
)
from teaagent.governance.release_gate import EVAL_EXECUTION_ADVISORY_NOTE


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
        repo_map = suite.get_tests_by_category(EvalCategory.REPO_MAP_BENCHMARK)
        assert [test.test_id for test in repo_map] == ['repo-map-release-eval-corpus']
    # Verify cleanup
    assert not os.path.exists(tmp_path), (
        f'Temporary directory {tmp_path} was not cleaned up'
    )


def test_register_reconciles_stale_suite_missing_repo_map() -> None:
    """A suite persisted before the repo-map corpus gains it on re-register.

    Regression guard: registration must not return a stale persisted suite that
    omits a newer critical category. The stale-suite early-return made the gate
    vacuously block on 'missing-category:repo_map_benchmark' even though the
    corpus defines a repo-map test.
    """
    with tempfile.TemporaryDirectory() as tmp:
        store = EvalStore(tmp)
        stale = EvalSuite(
            suite_id=RELEASE_EVAL_SUITE_ID, name='stale', description='pre-M5'
        )
        stale.add_test(
            EvalTest(
                test_id='old-1', name='old', category=EvalCategory.PROMPT_REGRESSION
            )
        )
        store.save_suite(stale)
        assert not store.load_suite(RELEASE_EVAL_SUITE_ID).get_tests_by_category(
            EvalCategory.REPO_MAP_BENCHMARK
        )

        register_release_eval_suite(store)

        refreshed = store.load_suite(RELEASE_EVAL_SUITE_ID)
        repo_map = refreshed.get_tests_by_category(EvalCategory.REPO_MAP_BENCHMARK)
        assert [test.test_id for test in repo_map] == ['repo-map-release-eval-corpus']


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


def test_seeded_repo_map_fixture_blocks_release(monkeypatch) -> None:
    import os

    tmp_path = None
    monkeypatch.setenv('TEAAGENT_EVAL_SEED_REPO_MAP_FAILURE', '1')
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = tmp
        result = run_release_eval_gate(tmp, seed_failure=False)
    assert result.decision == ReleaseDecision.BLOCK
    assert should_block_release(result)
    assert 'repo-map-release-eval-corpus' in result.critical_failures
    assert not os.path.exists(tmp_path), (
        f'Temporary directory {tmp_path} was not cleaned up'
    )


def test_release_gate_summary_discloses_simulated_execution() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = run_release_eval_gate(tmp, seed_failure=False)
    summary = format_gate_summary(result)
    assert EVAL_EXECUTION_ADVISORY_NOTE in summary
    assert result.simulated is True
    assert result.advisory_only is True
    assert '"simulated": true' in summary
    assert '"advisory_only": true' in summary
