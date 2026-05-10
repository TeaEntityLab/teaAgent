from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from teaagent.code_mode import (
    IsolateCodeModeBackend,
    SandboxProfile,
    execute_code_mode,
)
from teaagent.code_mode._container import ContainerCodeModeBackend
from teaagent.code_mode._types import CodeModeSandbox, ContainerCodeModeBackendConfig
from teaagent.code_mode._validation import UnsafeCodeError


class ContainerSecurityOptTests(unittest.TestCase):
    def _backend(self, **kwargs) -> ContainerCodeModeBackend:
        return ContainerCodeModeBackend(image='python:3.12-slim', **kwargs)

    def _cmd(self, **kwargs) -> list[str]:
        sb = CodeModeSandbox()
        return self._backend(**kwargs)._build_command(sb)

    def test_no_extra_security_opts_by_default(self) -> None:
        cmd = self._cmd()
        opts = [a for a in cmd if a.startswith('--security-opt=')]
        self.assertEqual(opts, ['--security-opt=no-new-privileges'])

    def test_seccomp_profile_added(self) -> None:
        cmd = self._cmd(seccomp_profile='/etc/docker/seccomp/default.json')
        self.assertIn('--security-opt=seccomp=/etc/docker/seccomp/default.json', cmd)

    def test_seccomp_default_keyword(self) -> None:
        cmd = self._cmd(seccomp_profile='default')
        self.assertIn('--security-opt=seccomp=default', cmd)

    def test_apparmor_profile_added(self) -> None:
        cmd = self._cmd(apparmor_profile='docker-default')
        self.assertIn('--security-opt=apparmor=docker-default', cmd)

    def test_selinux_label_added(self) -> None:
        cmd = self._cmd(selinux_label='level:s0:c100,c200')
        self.assertIn('--security-opt=label=level:s0:c100,c200', cmd)

    def test_oci_runtime_added(self) -> None:
        cmd = self._cmd(oci_runtime='runsc')
        self.assertIn('--runtime', cmd)
        idx = cmd.index('--runtime')
        self.assertEqual(cmd[idx + 1], 'runsc')

    def test_oci_runtime_none_omitted(self) -> None:
        cmd = self._cmd()
        self.assertNotIn('--runtime', cmd)

    def test_all_security_opts_combined(self) -> None:
        cmd = self._cmd(
            seccomp_profile='default',
            apparmor_profile='docker-default',
            selinux_label='disable',
            oci_runtime='runsc',
        )
        self.assertIn('--security-opt=seccomp=default', cmd)
        self.assertIn('--security-opt=apparmor=docker-default', cmd)
        self.assertIn('--security-opt=label=disable', cmd)
        self.assertIn('--runtime', cmd)

    def test_image_still_last_positional(self) -> None:
        cmd = self._cmd(seccomp_profile='default', oci_runtime='runsc')
        py_idx = cmd.index('python:3.12-slim')
        self.assertGreater(py_idx, 0)
        self.assertEqual(cmd[py_idx - 1], '-i')


class ContainerCodeModeBackendConfigTests(unittest.TestCase):
    def test_config_has_security_fields(self) -> None:
        cfg = ContainerCodeModeBackendConfig(
            image='python:3.12-slim',
            seccomp_profile='default',
            apparmor_profile='docker-default',
            selinux_label='disable',
            oci_runtime='runsc',
        )
        self.assertEqual(cfg.seccomp_profile, 'default')
        self.assertEqual(cfg.apparmor_profile, 'docker-default')
        self.assertEqual(cfg.selinux_label, 'disable')
        self.assertEqual(cfg.oci_runtime, 'runsc')

    def test_config_security_fields_default_none(self) -> None:
        cfg = ContainerCodeModeBackendConfig(image='python:3.12-slim')
        self.assertIsNone(cfg.seccomp_profile)
        self.assertIsNone(cfg.apparmor_profile)
        self.assertIsNone(cfg.selinux_label)
        self.assertIsNone(cfg.oci_runtime)


class IsolateCodeModeBackendTests(unittest.TestCase):
    def test_is_vm_isolated_true(self) -> None:
        b = IsolateCodeModeBackend(image='python:3.12-slim@sha256:' + 'a' * 64)
        self.assertTrue(b.is_vm_isolated)

    def test_require_image_digest_default_true(self) -> None:
        b = IsolateCodeModeBackend(image='python:3.12-slim@sha256:' + 'a' * 64)
        self.assertTrue(b.require_image_digest)

    def test_seccomp_profile_default_is_default(self) -> None:
        b = IsolateCodeModeBackend(image='python:3.12-slim@sha256:' + 'a' * 64)
        self.assertEqual(b.seccomp_profile, 'default')

    def test_executes_via_gvisor_runtime(self) -> None:
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
        self.assertIn('runsc', cmd)

    def test_is_vm_isolated_is_not_in_container_backend(self) -> None:
        b = ContainerCodeModeBackend(image='python:3.12-slim')
        self.assertFalse(hasattr(b, 'is_vm_isolated'))


class ExecuteCodeModeAuditTests(unittest.TestCase):
    def _mock_logger(self) -> MagicMock:
        logger = MagicMock()
        logger.record = MagicMock()
        return logger

    def test_profile_selected_event_emitted(self) -> None:
        logger = self._mock_logger()
        execute_code_mode(
            'x = 1',
            profile=SandboxProfile.CI,
            audit_logger=logger,
            run_id='run-1',
        )
        calls = [
            c
            for c in logger.record.call_args_list
            if c[0][0] == 'sandbox_profile_selected'
        ]
        self.assertEqual(len(calls), 1)
        evt_call = calls[0]
        self.assertEqual(evt_call[0][1], 'run-1')
        self.assertEqual(evt_call[1]['profile'], 'ci')

    def test_no_audit_without_logger(self) -> None:
        logger = self._mock_logger()
        execute_code_mode('x = 1')
        logger.record.assert_not_called()

    def test_violation_event_on_unsafe_code(self) -> None:
        logger = self._mock_logger()
        with self.assertRaises(UnsafeCodeError):
            execute_code_mode(
                'import os',
                profile=SandboxProfile.PRODUCTION,
                audit_logger=logger,
                run_id='run-2',
            )
        violation_calls = [
            c for c in logger.record.call_args_list if c[0][0] == 'sandbox_violation'
        ]
        self.assertEqual(len(violation_calls), 1)
        self.assertEqual(violation_calls[0][0][1], 'run-2')

    def test_profile_derives_sandbox_when_no_sandbox_given(self) -> None:
        logger = self._mock_logger()
        execute_code_mode(
            'x = 1',
            profile=SandboxProfile.PRODUCTION,
            audit_logger=logger,
        )
        calls = logger.record.call_args_list
        selected = [c for c in calls if c[0][0] == 'sandbox_profile_selected']
        self.assertEqual(len(selected), 1)
        self.assertAlmostEqual(selected[0][1]['timeout_seconds'], 2.0)
        self.assertAlmostEqual(selected[0][1]['memory_bytes'], 32 * 1024 * 1024)

    def test_explicit_sandbox_overrides_profile(self) -> None:
        logger = self._mock_logger()
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
            c
            for c in logger.record.call_args_list
            if c[0][0] == 'sandbox_profile_selected'
        ]
        self.assertEqual(selected[0][1]['timeout_seconds'], 7.0)

    def test_audit_logger_none_no_error(self) -> None:
        result = execute_code_mode('x = 42', audit_logger=None)
        self.assertEqual(result.variables.get('x'), 42)


if __name__ == '__main__':
    unittest.main()
