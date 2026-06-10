"""WDC-002/003 conversation UX snapshots."""

from __future__ import annotations

from teaagent.evidence_summary import RunEvidenceSummary
from teaagent.governance.conversation_ux import (
    format_approval_prompt_human,
    plain_run_receipt_summary,
    progressive_disclosure_sections,
    stranger_concept_count,
)
from teaagent.run_receipt import RunReceiptContext, format_run_receipt


def test_happy_path_concept_count_is_three() -> None:
    assert stranger_concept_count(include_advanced=False) == 3


def test_progressive_disclosure_hides_advanced_by_default() -> None:
    sections = progressive_disclosure_sections(include_advanced=False)
    assert all('Advanced' not in line for line in sections)


def test_plain_approval_prompt_snapshot() -> None:
    text = format_approval_prompt_human('workspace_write_file', 'call-1')
    assert 'TeaAgent wants to run' in text
    assert 'workspace_write_file' in text


def test_json_approval_prompt_snapshot() -> None:
    text = format_approval_prompt_human(
        'workspace_write_file',
        'call-1',
        {'path': 'a.py'},
        json_mode=True,
    )
    assert '"tool_name": "workspace_write_file"' in text


def test_plain_run_receipt_first_line() -> None:
    summary = RunEvidenceSummary(
        run_id='run-1',
        status='success',
        total_cost_cents=0,
        cost_state='unlimited',
    )
    context = RunReceiptContext(goal='fix tests')
    receipt = format_run_receipt(summary, context)
    assert receipt.splitlines()[0] == plain_run_receipt_summary(
        status='success',
        goal='fix tests',
    )
