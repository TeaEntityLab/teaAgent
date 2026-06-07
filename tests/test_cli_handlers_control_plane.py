from __future__ import annotations

import argparse
from contextlib import ExitStack
from unittest.mock import patch


def _make_args(**overrides: object) -> argparse.Namespace:
    defaults = dict(
        host='127.0.0.1',
        port=8080,
        jit_timeout_seconds=180,
        api_token=None,
        api_token_file=None,
        sse_interval_seconds=1.0,
        default_tenant='default',
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_control_plane_serve_starts() -> None:
    with ExitStack() as stack:
        mock_server = stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.ControlPlaneServer')
        )
        stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.JITApprovalServer')
        )
        stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.ToolPermissionManager')
        )
        stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.ControlPlaneRegistry')
        )
        # load_surface_auth_policy is imported inside the function body,
        # so patch at its definition site
        stack.enter_context(patch('teaagent.surface_auth.load_surface_auth_policy'))

        from teaagent.cli._handlers._control_plane import control_plane_serve_command

        result = control_plane_serve_command(_make_args())

    assert result == 0
    mock_server.return_value.serve_blocking.assert_called_once()


def test_control_plane_serve_creates_jit() -> None:
    with ExitStack() as stack:
        mock_permission = stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.ToolPermissionManager')
        )
        mock_jit = stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.JITApprovalServer')
        )
        stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.ControlPlaneServer')
        )
        stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.ControlPlaneRegistry')
        )
        stack.enter_context(patch('teaagent.surface_auth.load_surface_auth_policy'))

        from teaagent.cli._handlers._control_plane import control_plane_serve_command

        control_plane_serve_command(_make_args(jit_timeout_seconds=60))

    mock_permission.assert_called_once()
    mock_jit.assert_called_once()
    call_args = mock_jit.call_args
    assert call_args[0][0] is mock_permission.return_value
    assert call_args[1]['timeout_seconds'] == 60


def test_control_plane_serve_passes_args_to_server() -> None:
    with ExitStack() as stack:
        mock_server = stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.ControlPlaneServer')
        )
        mock_registry = stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.ControlPlaneRegistry')
        )
        mock_jit = stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.JITApprovalServer')
        )
        mock_auth = stack.enter_context(
            patch('teaagent.surface_auth.load_surface_auth_policy')
        )
        stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.ToolPermissionManager')
        )

        from teaagent.cli._handlers._control_plane import control_plane_serve_command

        control_plane_serve_command(
            _make_args(host='0.0.0.0', port=7331, sse_interval_seconds=2.0)
        )

    mock_server.assert_called_once_with(
        host='0.0.0.0',
        port=7331,
        tenant_registry=mock_registry.return_value,
        jit_server=mock_jit.return_value,
        sse_interval_seconds=2.0,
        max_sse_events=None,
        auth_policy=mock_auth.return_value,
    )


def test_control_plane_serve_value_error() -> None:
    with ExitStack() as stack:
        mock_server = stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.ControlPlaneServer')
        )
        stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.JITApprovalServer')
        )
        stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.ToolPermissionManager')
        )
        stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.ControlPlaneRegistry')
        )
        stack.enter_context(patch('teaagent.surface_auth.load_surface_auth_policy'))

        from teaagent.cli._handlers._control_plane import control_plane_serve_command

        mock_server.side_effect = ValueError('bad config')
        result = control_plane_serve_command(_make_args())

    assert result == 1


def test_control_plane_auth_policy_no_token_file() -> None:
    with ExitStack() as stack:
        mock_auth = stack.enter_context(
            patch('teaagent.surface_auth.load_surface_auth_policy')
        )
        stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.ControlPlaneServer')
        )
        stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.JITApprovalServer')
        )
        stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.ToolPermissionManager')
        )
        stack.enter_context(
            patch('teaagent.cli._handlers._control_plane.ControlPlaneRegistry')
        )

        from teaagent.cli._handlers._control_plane import control_plane_serve_command

        control_plane_serve_command(_make_args(api_token='tok_abc'))

    mock_auth.assert_called_once()
    _, kwargs = mock_auth.call_args
    assert kwargs['api_token'] == 'tok_abc'
    assert kwargs['api_token_file'] is None
    assert kwargs['relay_mode'] is False
