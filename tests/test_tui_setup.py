from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from teaagent.tui._setup import (
    apply_setup_result_to_tui,
    run_tui_setup,
    workspace_configured,
)
from teaagent.types import PermissionMode
from teaagent.wizard import WizardResult


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
    tui = MagicMock()
    result = MagicMock(spec=WizardResult)
    result.configured = {'provider': 'gpt', 'permission_mode': 'read-only'}
    apply_setup_result_to_tui(tui, result)
    assert tui.provider == 'gpt'
    assert tui.permission_mode == PermissionMode.READ_ONLY


def test_apply_setup_result_skips_empty_provider() -> None:
    tui = MagicMock()
    result = MagicMock(spec=WizardResult)
    result.configured = {'provider': '', 'permission_mode': 'workspace-write'}
    apply_setup_result_to_tui(tui, result)
    assert not tui.provider.called


@patch('teaagent.tui._setup.run_first_session_setup')
@patch('teaagent.tui._setup.check_llm_configuration')
def test_run_tui_setup_success(
    mock_check_llm: MagicMock,
    mock_run_setup: MagicMock,
) -> None:
    tui = MagicMock()
    tui.root = Path('/tmp')
    tui.provider = 'gpt'
    tui.permission_mode = PermissionMode.READ_ONLY
    tui.heartbeat_seconds = 30
    tui.model = 'gpt-4'
    tui.input_fn = lambda p: 'y'
    tui.output_fn = lambda s: None

    result = MagicMock(spec=WizardResult)
    result.ok = True
    result.configured = {'provider': 'gpt', 'permission_mode': 'read-only'}
    result.to_dict.return_value = {'ok': True}
    result.safe_command = 'teaagent run ...'
    result.next_steps = ['step 1', 'step 2', 'step 3']
    mock_run_setup.return_value = result

    ok = run_tui_setup(tui)
    assert ok is True
    mock_run_setup.assert_called_once()
    assert mock_run_setup.call_args[0][0].provider == 'gpt'
    assert mock_run_setup.call_args[0][0].permission_mode == 'read-only'
    tui._save_tui_state.assert_called_once()
    tui._print_json.assert_called_once_with({'ok': True})


@patch('teaagent.tui._setup.run_first_session_setup')
@patch('teaagent.tui._setup.check_llm_configuration')
def test_run_tui_setup_failure(
    mock_check_llm: MagicMock,
    mock_run_setup: MagicMock,
) -> None:
    tui = MagicMock()
    tui.root = Path('/tmp')
    tui.provider = 'gpt'
    tui.permission_mode = PermissionMode.READ_ONLY
    tui.heartbeat_seconds = 30
    tui.model = 'gpt-4'
    tui.output_fn = lambda s: None

    result = MagicMock(spec=WizardResult)
    result.ok = False
    result.configured = {}
    result.to_dict.return_value = {'ok': False}
    mock_run_setup.return_value = result

    ok = run_tui_setup(tui)
    assert ok is False


@patch('teaagent.tui._setup.run_first_session_setup')
@patch('teaagent.tui._setup.check_llm_configuration')
def test_run_tui_setup_passes_input_fn(
    mock_check_llm: MagicMock,
    mock_run_setup: MagicMock,
) -> None:
    tui = MagicMock()
    tui.root = Path('/tmp')
    tui.provider = 'gpt'
    tui.permission_mode = PermissionMode.READ_ONLY
    tui.heartbeat_seconds = 30
    tui.model = 'gpt-4'
    tui.input_fn = lambda p: 'y'
    tui.output_fn = lambda s: None

    result = MagicMock(spec=WizardResult)
    result.ok = True
    result.configured = {}
    result.to_dict.return_value = {'ok': True}
    result.safe_command = ''
    result.next_steps = []
    mock_run_setup.return_value = result

    run_tui_setup(tui)

    _, kwargs = mock_run_setup.call_args
    assert callable(kwargs['input_fn'])
