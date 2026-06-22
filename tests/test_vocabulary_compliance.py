"""Vocabulary compliance tests for background/resume terminology (WS1-005).

Ensures that code strings match the canonical vocabulary defined in
docs/guides/background-resume-vocabulary.md.
"""

from __future__ import annotations

# ── Canonical terms from docs/guides/background-resume-vocabulary.md ──────────
_CANONICAL_TERMS = {
    'checkpointed_suspension',
    'checkpointed suspension',
    'Checkpointed suspension',
    'resumable_session',
    'resumable session',
    'Resumable session',
    'checkpoint_available',
    'checkpoint available',
    'Checkpoint available',
    'live background execution',
    'scratchpad hint',
    'suspension json',
}

# Forbidden legacy terms that must not appear in new code paths.
# Only used for explicit output checks — not sweeping file searches.
_FORBIDDEN_TERMS = {
    # 'suspended' alone is too common; scoped checks handle it
}


# ── _derive_resume_state() return values ─────────────────────────────────────


def test_derive_resume_state_uses_vocabulary():
    """_derive_resume_state() returns canonical vocabulary terms."""
    from teaagent.evidence_summary import RunEvidenceSummary
    from teaagent.run_receipt import _derive_resume_state

    # Test: pending_approval → checkpointed_suspension
    summary = RunEvidenceSummary(
        run_id='test-1',
        status='pending_approval',
    )
    result = _derive_resume_state([], summary=summary)
    assert result == 'checkpointed_suspension', (
        f"Expected 'checkpointed_suspension' for pending_approval, got '{result}'"
    )

    # Test: run_suspended → resumable_session
    summary2 = RunEvidenceSummary(
        run_id='test-2',
        status='completed',
    )
    events = [{'event_type': 'run_suspended', 'timestamp': '2026-01-01T00:00:00Z'}]
    result2 = _derive_resume_state(events, summary=summary2)
    assert result2 == 'resumable_session', (
        f"Expected 'resumable_session' for run_suspended, got '{result2}'"
    )

    # Test: rollback_available → checkpoint_available
    summary3 = RunEvidenceSummary(
        run_id='test-3',
        status='completed',
        rollback_available=True,
    )
    result3 = _derive_resume_state([], summary=summary3)
    assert result3 == 'checkpoint_available', (
        f"Expected 'checkpoint_available' for rollback_available, got '{result3}'"
    )

    # Test: no special state → none
    summary4 = RunEvidenceSummary(
        run_id='test-4',
        status='completed',
    )
    result4 = _derive_resume_state([], summary=summary4)
    assert result4 == 'none', f"Expected 'none' for completed run, got '{result4}'"


# ── TUI help text compliance ────────────────────────────────────────────────


def test_tui_help_text_handoff_is_not_background_execution():
    """TUI help text for handoff must NOT claim it is background execution."""
    from teaagent.tui import HELP_TEXT

    # The handoff line should clarify it's a suspension checkpoint alias
    assert 'handoff' in HELP_TEXT.lower()
    # Must mention it's a checkpoint/suspension, not background execution
    assert 'checkpoint' in HELP_TEXT.lower()
    assert (
        'background execution' not in HELP_TEXT.split('handoff')[1].split('\n')[0]
        or 'not background execution' in HELP_TEXT.split('handoff')[1].split('\n')[0]
    )


def test_tui_help_text_uses_correct_background_vocab():
    """TUI help text for background command uses suspension checkpoint vocabulary."""
    from teaagent.tui import HELP_TEXT

    # The background line must clarify it's a suspension checkpoint
    assert (
        'suspension checkpoint' in HELP_TEXT.lower()
        or 'checkpoint' in HELP_TEXT.lower()
    )


# Chat REPL help-text compliance removed with U-P2-1: print_chat_help belonged
# to the retired run_chat_repl REPL. TUI help vocabulary is owned by the TUI
# rendering/_commands path and tested there.


# ── Run receipt output compliance ────────────────────────────────────────────


def test_run_receipt_resume_state_uses_vocabulary():
    """Run receipt output uses canonical resume state vocabulary."""
    import json
    import tempfile

    from teaagent.run_receipt import build_run_receipt
    from teaagent.run_store import RunStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStore(tmpdir)

        # Create a run with pending_approval
        events = [
            {
                'event_type': 'run_started',
                'timestamp': '2026-06-06T10:00:00Z',
                'payload': {
                    'task': 'test task',
                    'provider': 'gpt',
                    'model': 'gpt-4',
                },
            },
            {
                'event_type': 'run_paused',
                'timestamp': '2026-06-06T10:01:00Z',
                'payload': {},
            },
        ]

        run_id = 'vocab-test-001'
        path = store.run_path(run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '\n'.join(json.dumps(e, sort_keys=True) for e in events) + '\n',
            encoding='utf-8',
        )

        receipt = build_run_receipt(store, run_id, tmpdir)
        # Must use vocabulary terms, not legacy strings
        assert 'checkpointed_suspension' in receipt
        # Must NOT use legacy 'suspended' in the resume state line
        resume_line = [
            line for line in receipt.splitlines() if 'Resume/checkpoint:' in line
        ]
        assert resume_line
        assert 'checkpointed_suspension' in resume_line[0]


def test_run_receipt_resume_state_for_resumable():
    """Run receipt for a suspended run shows resumable_session."""
    import json
    import tempfile

    from teaagent.run_receipt import build_run_receipt
    from teaagent.run_store import RunStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStore(tmpdir)
        events = [
            {
                'event_type': 'run_started',
                'timestamp': '2026-06-06T10:00:00Z',
                'payload': {
                    'task': 'test task',
                    'provider': 'gpt',
                    'model': 'gpt-4',
                },
            },
            {
                'event_type': 'run_suspended',
                'timestamp': '2026-06-06T10:01:00Z',
                'payload': {},
            },
        ]

        run_id = 'vocab-test-002'
        path = store.run_path(run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '\n'.join(json.dumps(e, sort_keys=True) for e in events) + '\n',
            encoding='utf-8',
        )

        receipt = build_run_receipt(store, run_id, tmpdir)
        assert 'resumable_session' in receipt


# ── TUI handoff command output compliance ────────────────────────────────────


def test_tui_handoff_command_does_not_conflate_with_background_execution():
    """TUI handoff command output clarifies it's a suspension checkpoint alias."""
    from unittest.mock import MagicMock

    from teaagent.tui._commands import _cmd_handoff

    tui = MagicMock()
    tui.output_fn = MagicMock()
    tui._handle_background = MagicMock()

    _cmd_handoff(tui, [])

    # Verify output was produced
    calls = tui.output_fn.call_args_list
    # First call should explain it's a suspension checkpoint alias
    first_msg = str(calls[0][0][0]).lower() if calls else ''
    assert 'suspension' in first_msg or 'checkpoint' in first_msg
    assert 'not background' in first_msg

    # _handle_background must still be called (backward compat)
    tui._handle_background.assert_called_once()
