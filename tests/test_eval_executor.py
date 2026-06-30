"""Tests for real model-output execution seam in EvalRunner."""

from __future__ import annotations

import tempfile

from teaagent.release_gate import ReleaseDecision

from teaagent.eval_corpus import register_release_eval_suite
from teaagent.eval_suite import (
    EvalCategory,
    EvalRunner,
    EvalStatus,
    EvalStore,
    EvalSuite,
    ModelRunner,
)
from teaagent.governance.release_eval import run_release_eval_gate
from teaagent.governance.release_gate import EVAL_EXECUTION_ADVISORY_NOTE


def _prompt_to_expected(store: EvalStore, suite: EvalSuite) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for test in suite.get_enabled_tests():
        if test.category not in (
            EvalCategory.PROMPT_REGRESSION,
            EvalCategory.CONVERSATIONAL,
        ):
            continue
        prompt = str(test.metadata.get('prompt', ''))
        mapping[prompt] = str(test.metadata.get('expected_output', ''))
    return mapping


def _good_model_runner(store: EvalStore, suite: EvalSuite) -> ModelRunner:
    expected_by_prompt = _prompt_to_expected(store, suite)

    def runner(prompt: str) -> str:
        return expected_by_prompt.get(prompt, '')

    return runner


def _bad_model_runner(_prompt: str) -> str:
    return 'definitely wrong model output'


def test_model_runner_passes_with_real_execution_mode() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = EvalStore(tmp)
        runner = EvalRunner(store)
        suite = runner.create_suite('Prompt Suite')
        runner.add_test_to_suite(
            suite.suite_id,
            'Regression 1',
            EvalCategory.PROMPT_REGRESSION,
            metadata={
                'prompt': 'Say hello',
                'expected_output': 'Hello there',
                'expected_behavior': {'keywords': ['hello']},
            },
        )
        suite = store.load_suite(suite.suite_id)
        assert suite is not None

        good_runner = _good_model_runner(store, suite)
        real_runner = EvalRunner(store, model_runner=good_runner)
        results = real_runner.run_suite(suite)

        assert len(results) == 1
        assert results[0].status == EvalStatus.PASSED
        assert results[0].metrics['execution_mode'] == 'real'
        assert results[0].metrics['executor'] == 'model'
        assert results[0].metrics['advisory_only'] is False


def test_model_runner_fails_on_wrong_output() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = EvalStore(tmp)
        runner = EvalRunner(store)
        suite = runner.create_suite('Prompt Suite')
        runner.add_test_to_suite(
            suite.suite_id,
            'Regression 1',
            EvalCategory.PROMPT_REGRESSION,
            metadata={
                'prompt': 'Say hello',
                'expected_output': 'Hello there',
                'expected_behavior': {'keywords': ['hello']},
            },
        )
        suite = store.load_suite(suite.suite_id)
        assert suite is not None

        real_runner = EvalRunner(store, model_runner=_bad_model_runner)
        results = real_runner.run_suite(suite)

        assert len(results) == 1
        assert results[0].status == EvalStatus.FAILED
        assert results[0].metrics['execution_mode'] == 'real'


def test_no_model_runner_preserves_replay_baseline_metadata() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = EvalStore(tmp)
        runner = EvalRunner(store)
        suite = runner.create_suite('Prompt Suite')
        runner.add_test_to_suite(
            suite.suite_id,
            'Regression 1',
            EvalCategory.PROMPT_REGRESSION,
            metadata={
                'prompt': 'Say hello',
                'expected_output': 'Hello there',
                'expected_behavior': {'keywords': ['hello']},
            },
        )
        suite = store.load_suite(suite.suite_id)
        assert suite is not None

        results = runner.run_suite(suite)

        assert len(results) == 1
        assert results[0].status == EvalStatus.PASSED
        assert results[0].metrics['execution_mode'] == 'replay_baseline'
        assert results[0].metrics['executor'] == 'placeholder'
        assert results[0].metrics['advisory_only'] is True


def test_run_release_eval_gate_with_model_runner_approves_real_execution() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = EvalStore(tmp)
        register_release_eval_suite(store)
        suite = store.load_suite('release-eval-corpus')
        assert suite is not None
        good_runner = _good_model_runner(store, suite)

        result = run_release_eval_gate(tmp, model_runner=good_runner)

    assert result.decision == ReleaseDecision.APPROVE
    assert result.simulated is False
    assert result.advisory_only is False
    assert result.details.get('execution_mode') == 'real'
    assert 'advisory_note' not in result.details


def test_run_release_eval_gate_without_model_runner_unchanged() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = run_release_eval_gate(tmp)

    assert result.decision == ReleaseDecision.APPROVE
    assert result.simulated is True
    assert result.advisory_only is True
    assert result.details.get('execution_mode') == 'simulated'
    assert result.details.get('advisory_note') == EVAL_EXECUTION_ADVISORY_NOTE
