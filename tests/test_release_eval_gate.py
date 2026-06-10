"""Tests for release eval gate wiring (WDA-004 / WDD-001)."""

from __future__ import annotations

import tempfile
import unittest

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
from teaagent.release_gate import ReleaseDecision


class ReleaseEvalGateTests(unittest.TestCase):
    def test_conversational_corpus_covers_four_axes(self) -> None:
        tests = create_conversational_quality_tests()
        axes = {test.metadata['axis'] for test in tests}
        self.assertEqual(
            axes,
            {'clarification', 'interruption', 'correction', 'long_context_recall'},
        )

    def test_register_release_eval_suite_includes_conversational_category(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = EvalStore(tmp)
            register_release_eval_suite(store)
            suite = store.load_suite(RELEASE_EVAL_SUITE_ID)
            assert suite is not None
            conversational = suite.get_tests_by_category(EvalCategory.CONVERSATIONAL)
            self.assertEqual(len(conversational), 4)

    def test_release_gate_passes_on_green_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_release_eval_gate(tmp, seed_failure=False)
        self.assertEqual(result.decision, ReleaseDecision.APPROVE)
        self.assertFalse(should_block_release(result))

    def test_seeded_regression_fixture_blocks_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_release_eval_gate(tmp, seed_failure=True)
        self.assertEqual(result.decision, ReleaseDecision.BLOCK)
        self.assertTrue(should_block_release(result))
        self.assertGreater(result.failed_tests, 0)
