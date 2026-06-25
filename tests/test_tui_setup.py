from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, patch

from teaagent.tui._setup import (
    apply_setup_result_to_tui,
    run_tui_setup,
    workspace_configured,
)
from teaagent.types import PermissionMode
from teaagent.wizard import WizardResult


@dataclass
class _SetupTuiStub:
    root: Path
    provider: str = 'gpt'
    permission_mode: PermissionMode = PermissionMode.READ_ONLY
    heartbeat_seconds: int = 30
    model: str = 'gpt-4'
    input_fn: Callable[[str], str] | None = None
    output_fn: Callable[[str], None] | None = None
    saved_state_count: int = 0
    printed_json: list[dict] = field(default_factory=list)
    output_lines: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.output_fn is None:
            self.output_fn = self.output_lines.append

    def _save_tui_state(self) -> None:
        self.saved_state_count += 1

    def _print_json(self, payload: dict) -> None:
        self.printed_json.append(payload)


def _wizard_result(
    *,
    ok: bool,
    configured: dict | None = None,
    safe_command: str = '',
    next_steps: list[str] | None = None,
) -> WizardResult:
    return WizardResult(
        ok=ok,
        mode='tui',
        root='/tmp',
        configured=configured or {},
        safe_command=safe_command,
        next_steps=next_steps or [],
    )


def test_workspace_configured_finds_json(tmp_path: Path) -> None:
    (tmp_path / '.teaagent').mkdir()
    (tmp_path / '.teaagent' / 'config.json').write_text('{}')
    assert workspace_configured(tmp_path) is True


def test_workspace_configured_finds_toml(tmp_path: Path) -> None:
    (tmp_path / '.teaagent').mkdir()
    (tmp_path / '.teaagent' / 'config.toml').write_text('')
    assert workspace_configured(tmp_path) is True


def test_workspace_configured_returns_false_when_missing(tmp_path: Path) -> None:
    assert workspace_configured(tmp_path) is False


def test_workspace_configured_returns_false_when_no_teaagent_dir(
    tmp_path: Path,
) -> None:
    assert workspace_configured(tmp_path) is False


def test_apply_setup_result_sets_provider() -> None:
    tui = _SetupTuiStub(root=Path('/tmp'))
    result = _wizard_result(
        ok=True,
        configured={'provider': 'gpt', 'permission_mode': 'read-only'},
    )
    apply_setup_result_to_tui(tui, result)
    assert tui.provider == 'gpt'
    assert tui.permission_mode == PermissionMode.READ_ONLY


def test_apply_setup_result_skips_empty_provider() -> None:
    tui = _SetupTuiStub(root=Path('/tmp'), provider='existing')
    result = _wizard_result(
        ok=True,
        configured={'provider': '', 'permission_mode': 'workspace-write'},
    )
    apply_setup_result_to_tui(tui, result)
    assert tui.provider == 'existing'
    assert tui.permission_mode == PermissionMode.WORKSPACE_WRITE


@patch('teaagent.tui._setup.run_first_session_setup')
@patch('teaagent.tui._setup.check_llm_configuration')
def test_run_tui_setup_success(
    mock_check_llm: MagicMock,
    mock_run_setup: MagicMock,
) -> None:
    tui = _SetupTuiStub(root=Path('/tmp'), input_fn=lambda p: 'y')
    result = _wizard_result(
        ok=True,
        configured={'provider': 'gpt', 'permission_mode': 'read-only'},
        safe_command='teaagent run ...',
        next_steps=['step 1', 'step 2', 'step 3'],
    )
    mock_run_setup.return_value = result

    ok = run_tui_setup(tui)
    assert ok is True
    mock_run_setup.assert_called_once()
    assert mock_run_setup.call_args[0][0].provider == 'gpt'
    assert mock_run_setup.call_args[0][0].permission_mode == 'read-only'
    assert tui.saved_state_count == 1
    assert tui.printed_json == [result.to_dict()]


@patch('teaagent.tui._setup.run_first_session_setup')
@patch('teaagent.tui._setup.check_llm_configuration')
def test_run_tui_setup_failure(
    mock_check_llm: MagicMock,
    mock_run_setup: MagicMock,
) -> None:
    tui = _SetupTuiStub(root=Path('/tmp'))
    result = _wizard_result(ok=False)
    mock_run_setup.return_value = result

    ok = run_tui_setup(tui)
    assert ok is False
    assert tui.printed_json == [result.to_dict()]


@patch('teaagent.tui._setup.run_first_session_setup')
@patch('teaagent.tui._setup.check_llm_configuration')
def test_run_tui_setup_passes_input_fn(
    mock_check_llm: MagicMock,
    mock_run_setup: MagicMock,
) -> None:
    tui = _SetupTuiStub(root=Path('/tmp'), input_fn=lambda p: 'y')
    result = _wizard_result(ok=True)
    mock_run_setup.return_value = result

    run_tui_setup(tui)

    _, kwargs = mock_run_setup.call_args
    assert callable(kwargs['input_fn'])
