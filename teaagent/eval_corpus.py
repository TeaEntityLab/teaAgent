"""Eval corpora for release gating (WDD-001)."""

from __future__ import annotations

from teaagent.eval_suite import EvalCategory, EvalStore, EvalSuite, EvalTest
from teaagent.prompt_regression import PromptRegressionEvaluator, PromptRegressionTest

RELEASE_EVAL_SUITE_ID = 'release-eval-corpus'
RELEASE_EVAL_SUITE_NAME = 'Release Eval Corpus'


def create_conversational_quality_tests() -> list[PromptRegressionTest]:
    """Conversational regression corpus: clarify, interrupt, correct, recall."""
    return [
        PromptRegressionTest(
            test_id='conv-clarify-001',
            name='Clarification before action',
            prompt='Fix the auth bug.',
            expected_output=(
                'Before I change code, could you clarify which auth flow failed '
                'and whether this is login, token refresh, or permission checks?'
            ),
            expected_behavior={'keywords': ['clarif', 'auth']},
            tolerance_threshold=0.65,
            metadata={'axis': 'clarification'},
        ),
        PromptRegressionTest(
            test_id='conv-interrupt-001',
            name='Graceful interruption handling',
            prompt='Stop — switch to writing tests only, no more refactors.',
            expected_output=(
                'Understood. I will stop refactoring and focus only on adding tests '
                'from this point forward.'
            ),
            expected_behavior={'keywords': ['stop', 'tests']},
            tolerance_threshold=0.65,
            metadata={'axis': 'interruption'},
        ),
        PromptRegressionTest(
            test_id='conv-correct-001',
            name='User correction acknowledgment',
            prompt='No, the failing module is billing, not auth.',
            expected_output=(
                'Thanks for the correction — I will target the billing module instead '
                'of auth and re-check the failing tests there.'
            ),
            expected_behavior={'keywords': ['billing', 'correction']},
            tolerance_threshold=0.65,
            metadata={'axis': 'correction'},
        ),
        PromptRegressionTest(
            test_id='conv-recall-001',
            name='Long-context recall',
            prompt='What was the budget cap and rollback rule we agreed on earlier?',
            expected_output=(
                'Earlier you set a budget cap of 2000 cents with rollback required '
                'before any destructive shell command.'
            ),
            expected_behavior={
                'keywords': ['budget', 'rollback'],
                'min_length': 40,
            },
            tolerance_threshold=0.6,
            metadata={'axis': 'long_context_recall'},
        ),
    ]


def _to_eval_test(
    regression_test: PromptRegressionTest,
    *,
    category: EvalCategory,
) -> EvalTest:
    return EvalTest(
        test_id=regression_test.test_id,
        name=regression_test.name,
        category=category,
        description=f'Eval corpus test: {regression_test.name}',
        metadata={
            'prompt': regression_test.prompt,
            'expected_output': regression_test.expected_output,
            'expected_behavior': regression_test.expected_behavior,
            'tolerance_threshold': regression_test.tolerance_threshold,
            **regression_test.metadata,
        },
    )


def register_release_eval_suite(store: EvalStore) -> str:
    """Register prompt + conversational tests in the release eval suite."""
    evaluator = PromptRegressionEvaluator()
    existing = store.load_suite(RELEASE_EVAL_SUITE_ID)
    if existing is not None:
        return RELEASE_EVAL_SUITE_ID

    suite = EvalSuite(
        suite_id=RELEASE_EVAL_SUITE_ID,
        name=RELEASE_EVAL_SUITE_NAME,
        description='Prompt regression + conversational quality corpus (WDD-001).',
    )
    for regression_test in (
        *evaluator.create_default_regression_tests(),
        *create_conversational_quality_tests(),
    ):
        category = (
            EvalCategory.CONVERSATIONAL
            if regression_test.test_id.startswith('conv-')
            else EvalCategory.PROMPT_REGRESSION
        )
        suite.add_test(_to_eval_test(regression_test, category=category))
    store.save_suite(suite)
    return suite.suite_id
