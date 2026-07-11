# test-type: contract
"""Executable specification for the H5 advisory eval-gate hold.

Companion to docs/specs/nonadvisory-eval-gate-promotion-spec-2026-07-11.md
(roadmap H5/M5 hold: non-advisory model/provider gate needs live provider
runs + owner decision).

Pins the exact split the hold rests on: corpus failures BLOCK even in
simulated mode, while execution quality is advisory-and-disclosed. Also pins
the release profile's strictness override, the fixture-counts-as-real design
point, disclosure-flag serialization, and the bundle key contract the future
evidence-bundle proof builds on. The final test is a feature-detection
activation hook for the non-advisory profile field.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from teaagent.eval_suite import (
    EvalCategory,
    EvalResult,
    EvalStatus,
    EvalStore,
)
from teaagent.governance.release_eval import (
    build_release_gate_config,
    run_release_eval_gate,
    should_block_release,
)
from teaagent.governance.release_gate import (
    ReleaseDecision,
    ReleaseGate,
    ReleaseGateConfig,
    ReleaseGateResult,
)


def test_release_profile_is_stricter_than_default(tmp_path: Path) -> None:
    """The CI release profile requires 100% success and 3 critical categories.

    build_release_gate_config overrides the 0.9 default with 1.0 and pins the
    critical set (release_eval.py:24-30). This is the actual config the
    release workflow runs; silently loosening it would weaken the release
    gate without any test noticing — this pin is that test.
    """
    gate = ReleaseGate(EvalStore(tmp_path))
    config = build_release_gate_config(gate)
    assert config.required_success_rate == 1.0
    assert config.block_on_critical_failure is True
    assert {
        'prompt_regression',
        'conversational',
        'repo_map_benchmark',
    } <= config.critical_test_categories


def test_simulated_run_still_blocks_on_seeded_corpus_failure(
    tmp_path: Path,
) -> None:
    """Corpus regressions BLOCK even when execution is simulated.

    The H5 hold is precise: 'advisory' covers only the execution-quality
    signal, not the corpus checks. A seeded corpus failure must block the
    release AND carry the simulated/advisory disclosure flags — this is the
    split the promotion spec formalizes.
    """
    result = run_release_eval_gate(tmp_path, seed_failure=True)
    assert result.decision is ReleaseDecision.BLOCK
    assert should_block_release(result)
    assert result.simulated is True
    assert result.advisory_only is True


def test_advisory_flag_tracks_simulated_flag(tmp_path: Path) -> None:
    """advisory_only and simulated are set together by execution disclosure.

    _apply_execution_disclosure assigns both flags from the same execution
    evidence (release_gate.py:307-316). Consumers (format_gate_summary, the
    evidence bundle) rely on the coupling; divergence would let a simulated
    result present as non-advisory.
    """
    result = run_release_eval_gate(tmp_path, seed_failure=False)
    assert result.simulated == result.advisory_only
    assert result.details.get('execution_mode') in ('simulated', 'real')


def test_fixture_execution_mode_counts_as_real(tmp_path: Path) -> None:
    """A suite whose critical results ran in fixture mode is NOT advisory.

    Design point (release_gate.py:303-305): deterministic fixture execution
    is a real regression signal (the M5 repo-map fixture corpus). Exercises
    _apply_execution_disclosure directly because run_and_evaluate re-runs
    the suite and would overwrite crafted execution metadata; the disclosure
    rule itself is the contract under test.
    """
    store = EvalStore(tmp_path)
    gate = ReleaseGate(store)
    suite = gate.runner.create_suite('fixture-disclosure')
    test, suite = gate.runner.add_test_to_suite(
        suite.suite_id,
        'repo-map-fixture-case',
        EvalCategory.REPO_MAP_BENCHMARK,
    )
    store.save_result(
        EvalResult(
            test_id=test.test_id,
            status=EvalStatus.PASSED,
            metrics={'execution_mode': 'fixture'},
        )
    )

    config = ReleaseGateConfig(
        gate_id='fixture-gate',
        name='Fixture Gate',
        critical_test_categories={'repo_map_benchmark'},
    )
    result = gate.evaluate_gate(config, suite.suite_id)
    gate._apply_execution_disclosure(result, suite)

    assert result.simulated is False
    assert result.advisory_only is False
    assert result.details['execution_mode'] == 'real'
    assert 'advisory_note' not in result.details


def test_gate_result_roundtrip_preserves_disclosure_flags() -> None:
    """simulated/advisory_only survive to_dict/from_dict round-trips.

    The exported gate report and the future evidence bundle both carry the
    serialized result; dropping the disclosure flags in transit would erase
    the advisory labeling the H5 hold depends on.
    """
    original = ReleaseGateResult(
        gate_id='rt-gate',
        decision=ReleaseDecision.APPROVE,
        simulated=True,
        advisory_only=True,
    )
    restored = ReleaseGateResult.from_dict(json.loads(json.dumps(original.to_dict())))
    assert restored.simulated is True
    assert restored.advisory_only is True
    assert restored.decision is ReleaseDecision.APPROVE


def test_release_bundle_key_contract(tmp_path: Path) -> None:
    """create_release_bundle emits the base keys the proof format extends.

    Spec section 3.3 defines the future bundle as additive over
    {suite, results, summary, generated_at} (file) and
    {bundle_path, suite_id, test_count, result_count} (metadata). Pinning
    the base keys keeps 'additive-only' checkable.
    """
    store = EvalStore(tmp_path)
    gate = ReleaseGate(store)
    suite = gate.runner.create_suite('bundle-contract')
    bundle_path = tmp_path / 'bundle.json'

    metadata = gate.create_release_bundle(suite.suite_id, bundle_path)

    assert set(metadata) == {
        'bundle_path',
        'suite_id',
        'test_count',
        'result_count',
    }
    payload = json.loads(bundle_path.read_text(encoding='utf-8'))
    assert set(payload) == {'suite', 'results', 'summary', 'generated_at'}


_HAS_NONADVISORY_FIELD = any(
    field.name == 'require_real_execution'
    for field in dataclasses.fields(ReleaseGateConfig)
)


@pytest.mark.skipif(
    not _HAS_NONADVISORY_FIELD,
    reason=(
        'non-advisory release profile not implemented; see '
        'docs/specs/nonadvisory-eval-gate-promotion-spec-2026-07-11.md '
        'section 3.2'
    ),
)
def test_nonadvisory_profile_field_activates() -> None:
    """Activation hook: the non-advisory profile defaults to off.

    Skipped until ReleaseGateConfig grows require_real_execution. Once
    implemented, this asserts the field defaults False (old reports parse)
    and round-trips; the promotion checklist then adds the adversarial
    simulated+require_real -> BLOCK test alongside.
    """
    config = ReleaseGateConfig(gate_id='na-gate', name='NA Gate')
    assert vars(config)['require_real_execution'] is False
    restored = ReleaseGateConfig.from_dict(config.to_dict())
    assert vars(restored)['require_real_execution'] is False
