"""Release eval gate orchestration (WDA-004 / WDD-001)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from teaagent.eval_corpus import register_release_eval_suite
from teaagent.eval_suite import EvalStore
from teaagent.release_gate import ReleaseDecision, ReleaseGate, ReleaseGateResult


def release_eval_store_path(workspace_root: str | Path) -> Path:
    return Path(workspace_root).resolve() / '.teaagent' / 'eval'


def build_release_gate_config(gate: ReleaseGate) -> Any:
    config = gate.create_default_gate_config()
    config.critical_test_categories.update(
        {'prompt_regression', 'conversational', 'repo_map_benchmark'}
    )
    config.required_success_rate = 1.0
    return config


def run_release_eval_gate(
    workspace_root: str | Path,
    *,
    seed_failure: bool = False,
    report_path: str | Path | None = None,
) -> ReleaseGateResult:
    """Run prompt + conversational corpora and evaluate the release gate."""
    root = Path(workspace_root).resolve()
    store_dir = release_eval_store_path(root)
    store_dir.mkdir(parents=True, exist_ok=True)

    previous = os.environ.get('TEAAGENT_EVAL_SEED_FAILURE')
    if seed_failure:
        os.environ['TEAAGENT_EVAL_SEED_FAILURE'] = '1'
    else:
        os.environ.pop('TEAAGENT_EVAL_SEED_FAILURE', None)

    try:
        store = EvalStore(store_dir)
        suite_id = register_release_eval_suite(store)
        gate = ReleaseGate(store)
        config = build_release_gate_config(gate)
        result = gate.run_and_evaluate(config, suite_id)
        if report_path is not None:
            gate.export_gate_report(result, report_path)
        return result
    finally:
        if previous is None:
            os.environ.pop('TEAAGENT_EVAL_SEED_FAILURE', None)
        else:
            os.environ['TEAAGENT_EVAL_SEED_FAILURE'] = previous


def gate_result_to_dict(result: ReleaseGateResult) -> dict[str, Any]:
    return result.to_dict()


def should_block_release(result: ReleaseGateResult) -> bool:
    return result.decision == ReleaseDecision.BLOCK


def format_gate_summary(result: ReleaseGateResult) -> str:
    payload = gate_result_to_dict(result)
    return json.dumps(payload, indent=2)
