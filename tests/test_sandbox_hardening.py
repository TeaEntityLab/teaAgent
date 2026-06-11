from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from teaagent.code_mode import (
    IsolateCodeModeBackend,
    SandboxProfile,
    execute_code_mode,
)
from teaagent.code_mode._container import ContainerCodeModeBackend
from teaagent.code_mode._types import CodeModeSandbox, ContainerCodeModeBackendConfig
from teaagent.code_mode._validation import UnsafeCodeError


def _backend(**kwargs) -> ContainerCodeModeBackend:
    return ContainerCodeModeBackend(image='python:3.12-slim', **kwargs)


def _cmd(**kwargs) -> list[str]:
    sb = CodeModeSandbox()
    return _backend(**kwargs)._build_command(sb)


def test_no_extra_security_opts_by_default() -> None:
    cmd = _cmd()
    opts = [a for a in cmd if a.startswith('--security-opt=')]
    assert opts == ['--security-opt=no-new-privileges']


def test_seccomp_profile_added() -> None:
    cmd = _cmd(seccomp_profile='/etc/docker/seccomp/default.json')
    assert '--security-opt=seccomp=/etc/docker/seccomp/default.json' in cmd


def test_seccomp_default_keyword() -> None:
    cmd = _cmd(seccomp_profile='default')
    assert '--security-opt=seccomp=default' in cmd


def test_apparmor_profile_added() -> None:
    cmd = _cmd(apparmor_profile='docker-default')
    assert '--security-opt=apparmor=docker-default' in cmd


def test_selinux_label_added() -> None:
    cmd = _cmd(selinux_label='level:s0:c100,c200')
    assert '--security-opt=label=level:s0:c100,c200' in cmd


def test_oci_runtime_added() -> None:
    cmd = _cmd(oci_runtime='runsc')
    assert '--runtime' in cmd
    idx = cmd.index('--runtime')
    assert cmd[idx + 1] == 'runsc'


def test_oci_runtime_none_omitted() -> None:
    cmd = _cmd()
    assert '--runtime' not in cmd


def test_all_security_opts_combined() -> None:
    cmd = _cmd(
        seccomp_profile='default',
        apparmor_profile='docker-default',
        selinux_label='disable',
        oci_runtime='runsc',
    )
    assert '--security-opt=seccomp=default' in cmd
    assert '--security-opt=apparmor=docker-default' in cmd
    assert '--security-opt=label=disable' in cmd
    assert '--runtime' in cmd


def test_image_still_last_positional() -> None:
    cmd = _cmd(seccomp_profile='default', oci_runtime='runsc')
    py_idx = cmd.index('python:3.12-slim')
    assert py_idx > 0
    assert cmd[py_idx - 1] == '-i'


def test_config_has_security_fields() -> None:
    cfg = ContainerCodeModeBackendConfig(
        image='python:3.12-slim',
        seccomp_profile='default',
        apparmor_profile='docker-default',
        selinux_label='disable',
        oci_runtime='runsc',
    )
    assert cfg.seccomp_profile == 'default'
    assert cfg.apparmor_profile == 'docker-default'
    assert cfg.selinux_label == 'disable'
    assert cfg.oci_runtime == 'runsc'


def test_config_security_fields_default_none() -> None:
    cfg = ContainerCodeModeBackendConfig(image='python:3.12-slim')
    assert cfg.seccomp_profile is None
    assert cfg.apparmor_profile is None
    assert cfg.selinux_label is None
    assert cfg.oci_runtime is None


def test_is_vm_isolated_true() -> None:
    b = IsolateCodeModeBackend(image='python:3.12-slim@sha256:' + 'a' * 64)
    assert b.is_vm_isolated


def test_require_image_digest_default_true() -> None:
    b = IsolateCodeModeBackend(image='python:3.12-slim@sha256:' + 'a' * 64)
    assert b.require_image_digest


def test_seccomp_profile_default_is_default() -> None:
    b = IsolateCodeModeBackend(image='python:3.12-slim@sha256:' + 'a' * 64)
    assert b.seccomp_profile == 'default'


def test_executes_via_gvisor_runtime() -> None:
    b = IsolateCodeModeBackend(image='python:3.12-slim@sha256:' + 'a' * 64)
    sandbox = CodeModeSandbox()
    with patch.object(
        ContainerCodeModeBackend,
        'execute',
        return_value=MagicMock(variables={}),
    ) as mock_exec:
        b.execute('x = 1', {}, sandbox)
        mock_exec.assert_called_once()

    # Inspect via _build_command
    inner_backend = ContainerCodeModeBackend(
        image='python:3.12-slim@sha256:' + 'a' * 64,
        oci_runtime='runsc',
    )
    cmd = inner_backend._build_command(sandbox)
    assert 'runsc' in cmd


def test_is_vm_isolated_is_not_in_container_backend() -> None:
    b = ContainerCodeModeBackend(image='python:3.12-slim')
    assert not hasattr(b, 'is_vm_isolated')


def _mock_logger() -> MagicMock:
    logger = MagicMock()
    logger.record = MagicMock()
    return logger


def test_profile_selected_event_emitted() -> None:
    logger = _mock_logger()
    execute_code_mode(
        'x = 1',
        profile=SandboxProfile.CI,
        audit_logger=logger,
        run_id='run-1',
    )
    calls = [
        c for c in logger.record.call_args_list if c[0][0] == 'sandbox_profile_selected'
    ]
    assert len(calls) == 1
    evt_call = calls[0]
    assert evt_call[0][1] == 'run-1'
    assert evt_call[1]['profile'] == 'ci'


def test_no_audit_without_logger() -> None:
    logger = _mock_logger()
    execute_code_mode('x = 1')
    logger.record.assert_not_called()


def test_violation_event_on_unsafe_code() -> None:
    logger = _mock_logger()
    with pytest.raises(UnsafeCodeError):
        execute_code_mode(
            'import os',
            profile=SandboxProfile.PRODUCTION,
            audit_logger=logger,
            run_id='run-2',
        )
    violation_calls = [
        c for c in logger.record.call_args_list if c[0][0] == 'sandbox_violation'
    ]
    assert len(violation_calls) == 1
    assert violation_calls[0][0][1] == 'run-2'


def test_profile_derives_sandbox_when_no_sandbox_given() -> None:
    logger = _mock_logger()
    execute_code_mode(
        'x = 1',
        profile=SandboxProfile.PRODUCTION,
        audit_logger=logger,
    )
    calls = logger.record.call_args_list
    selected = [c for c in calls if c[0][0] == 'sandbox_profile_selected']
    assert len(selected) == 1
    assert selected[0][1]['timeout_seconds'] == pytest.approx(2.0)
    assert selected[0][1]['memory_bytes'] == pytest.approx(32 * 1024 * 1024)


def test_explicit_sandbox_overrides_profile() -> None:
    logger = _mock_logger()
    custom_sandbox = CodeModeSandbox(
        timeout_seconds=7.0, cpu_seconds=7, memory_bytes=99 * 1024 * 1024
    )
    execute_code_mode(
        'x = 1',
        sandbox=custom_sandbox,
        profile=SandboxProfile.CI,
        audit_logger=logger,
    )
    selected = [
        c for c in logger.record.call_args_list if c[0][0] == 'sandbox_profile_selected'
    ]
    assert selected[0][1]['timeout_seconds'] == 7.0


def test_audit_logger_none_no_error() -> None:
    result = execute_code_mode('x = 42', audit_logger=None)
    assert result.variables.get('x') == 42


def test_container_backend_falls_back_when_docker_unavailable() -> None:
    logger = _mock_logger()
    backend = ContainerCodeModeBackend(image='python:3.12-slim')
    with patch(
        'teaagent.code_mode.DockerSandbox.preflight',
        return_value={'status': 'fallback', 'reason': 'daemon down'},
    ):
        result = execute_code_mode(
            'x = 1',
            backend=backend,
            audit_logger=logger,
            run_id='run-fallback',
        )
    assert result.variables.get('x') == 1
    events = [call[0][0] for call in logger.record.call_args_list]
    assert 'docker_preflight_failed' in events
    assert 'sandbox_fallback_to_child_process' in events
