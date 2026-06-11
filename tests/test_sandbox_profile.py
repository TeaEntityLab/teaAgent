from __future__ import annotations

from teaagent.code_mode import SandboxProfile
from teaagent.code_mode._types import CodeModeSandbox


def test_local_has_relaxed_limits() -> None:
    sb = SandboxProfile.LOCAL.default_sandbox()
    assert isinstance(sb, CodeModeSandbox)
    assert sb.timeout_seconds > 5.0
    assert sb.memory_bytes > 64 * 1024 * 1024


def test_ci_is_between_local_and_production() -> None:
    local = SandboxProfile.LOCAL.default_sandbox()
    ci = SandboxProfile.CI.default_sandbox()
    prod = SandboxProfile.PRODUCTION.default_sandbox()
    assert prod.timeout_seconds < ci.timeout_seconds
    assert ci.timeout_seconds <= local.timeout_seconds
    assert prod.memory_bytes < ci.memory_bytes
    assert ci.memory_bytes <= local.memory_bytes


def test_production_has_tightest_limits() -> None:
    sb = SandboxProfile.PRODUCTION.default_sandbox()
    assert sb.timeout_seconds <= 2.0
    assert sb.memory_bytes <= 32 * 1024 * 1024
    assert sb.max_output_bytes <= 1 * 1024 * 1024


def test_each_profile_returns_code_mode_sandbox() -> None:
    for profile in SandboxProfile:
        sb = profile.default_sandbox()
        assert isinstance(sb, CodeModeSandbox), f'{profile} returned wrong type'


def test_local_and_ci_always_no_warnings() -> None:
    for profile in (SandboxProfile.LOCAL, SandboxProfile.CI):
        warnings = profile.validate_runtime_support()
        assert warnings == [], f'{profile} should have no warnings'


def test_production_returns_list() -> None:
    warnings = SandboxProfile.PRODUCTION.validate_runtime_support()
    assert isinstance(warnings, list)


def test_production_warnings_are_strings() -> None:
    warnings = SandboxProfile.PRODUCTION.validate_runtime_support()
    for w in warnings:
        assert isinstance(w, str)


def test_all_three_profiles_exist() -> None:
    values = {p.value for p in SandboxProfile}
    assert 'local' in values
    assert 'ci' in values
    assert 'production' in values


def test_profiles_are_strings() -> None:
    for profile in SandboxProfile:
        assert isinstance(profile.value, str)


def test_sandbox_profile_imported_from_code_mode() -> None:
    from teaagent.code_mode import SandboxProfile as SP

    assert SP is SandboxProfile
