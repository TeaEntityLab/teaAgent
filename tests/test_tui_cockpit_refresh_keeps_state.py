# test-type: behavior
"""U-P1-18: a failed cockpit refresh keeps the previous state.

Spec: docs/specs/operator-cockpit-acceptance-spec-2026-07-11.md section 3.4,
"a failed refresh keeps the previous state and logs at debug". Before the fix,
a single failing refresh reset ``_control_cockpit`` / ``_cockpit_state`` to
None and wiped the [Control Cockpit] panel.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from teaagent.tui import TeaAgentTUI


def _tui(root: Path) -> TeaAgentTUI:
    return TeaAgentTUI(
        root=root,
        input_fn=lambda _prompt: 'exit',
        output_fn=lambda _text: None,
    )


def test_failed_control_cockpit_refresh_keeps_previous_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tui = _tui(tmp_path)
    tui._refresh_control_cockpit()
    previous = tui._control_cockpit
    assert previous is not None

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError('simulated control cockpit failure')

    monkeypatch.setattr('teaagent.tui.core.build_control_cockpit', _raise)
    tui._refresh_control_cockpit()

    assert tui._control_cockpit is previous


def test_failed_cockpit_state_refresh_keeps_previous_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tui = _tui(tmp_path)
    tui._refresh_control_cockpit()
    previous = tui._cockpit_state
    assert previous is not None

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError('simulated context health failure')

    monkeypatch.setattr('teaagent.tui.core.compute_context_health', _raise)
    tui._refresh_control_cockpit()

    assert tui._cockpit_state is previous


def test_first_failed_refresh_leaves_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tui = _tui(tmp_path)

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError('simulated first-refresh failure')

    monkeypatch.setattr('teaagent.tui.core.build_control_cockpit', _raise)
    monkeypatch.setattr('teaagent.tui.core.compute_context_health', _raise)
    tui._refresh_control_cockpit()

    assert tui._control_cockpit is None
    assert tui._cockpit_state is None
