from __future__ import annotations

import unittest

from teaagent.code_mode import SandboxProfile
from teaagent.code_mode._types import CodeModeSandbox


class SandboxProfileDefaultSandboxTests(unittest.TestCase):
    def test_local_has_relaxed_limits(self) -> None:
        sb = SandboxProfile.LOCAL.default_sandbox()
        self.assertIsInstance(sb, CodeModeSandbox)
        self.assertGreater(sb.timeout_seconds, 5.0)
        self.assertGreater(sb.memory_bytes, 64 * 1024 * 1024)

    def test_ci_is_between_local_and_production(self) -> None:
        local = SandboxProfile.LOCAL.default_sandbox()
        ci = SandboxProfile.CI.default_sandbox()
        prod = SandboxProfile.PRODUCTION.default_sandbox()
        self.assertLess(prod.timeout_seconds, ci.timeout_seconds)
        self.assertLessEqual(ci.timeout_seconds, local.timeout_seconds)
        self.assertLess(prod.memory_bytes, ci.memory_bytes)
        self.assertLessEqual(ci.memory_bytes, local.memory_bytes)

    def test_production_has_tightest_limits(self) -> None:
        sb = SandboxProfile.PRODUCTION.default_sandbox()
        self.assertLessEqual(sb.timeout_seconds, 2.0)
        self.assertLessEqual(sb.memory_bytes, 32 * 1024 * 1024)
        self.assertLessEqual(sb.max_output_bytes, 1 * 1024 * 1024)

    def test_each_profile_returns_code_mode_sandbox(self) -> None:
        for profile in SandboxProfile:
            sb = profile.default_sandbox()
            self.assertIsInstance(sb, CodeModeSandbox, f'{profile} returned wrong type')


class SandboxProfileValidateRuntimeTests(unittest.TestCase):
    def test_local_and_ci_always_no_warnings(self) -> None:
        for profile in (SandboxProfile.LOCAL, SandboxProfile.CI):
            warnings = profile.validate_runtime_support()
            self.assertEqual(warnings, [], f'{profile} should have no warnings')

    def test_production_returns_list(self) -> None:
        warnings = SandboxProfile.PRODUCTION.validate_runtime_support()
        self.assertIsInstance(warnings, list)

    def test_production_warnings_are_strings(self) -> None:
        warnings = SandboxProfile.PRODUCTION.validate_runtime_support()
        for w in warnings:
            self.assertIsInstance(w, str)


class SandboxProfileEnumTests(unittest.TestCase):
    def test_all_three_profiles_exist(self) -> None:
        values = {p.value for p in SandboxProfile}
        self.assertIn('local', values)
        self.assertIn('ci', values)
        self.assertIn('production', values)

    def test_profiles_are_strings(self) -> None:
        for profile in SandboxProfile:
            self.assertIsInstance(profile.value, str)

    def test_sandbox_profile_imported_from_code_mode(self) -> None:
        from teaagent.code_mode import SandboxProfile as SP

        self.assertIs(SP, SandboxProfile)


if __name__ == '__main__':
    unittest.main()
