"""Tests for skill router."""

import tempfile
from pathlib import Path

from teaagent.consensus import RiskLevel
from teaagent.skill_router import SandboxType, SkillRouter


def test_skill_router_init():
    """Test skill router initialization."""
    router = SkillRouter()
    assert router.default_sandbox == SandboxType.AUTO
    assert router.wasm_memory_limit_mb == 256


def test_skill_router_with_custom_config():
    """Test skill router with custom configuration."""
    router = SkillRouter(
        default_sandbox=SandboxType.DOCKER,
        wasm_memory_limit_mb=512,
        docker_cpu_quota=2.0,
        docker_memory_limit='1g',
    )

    assert router.default_sandbox == SandboxType.DOCKER
    assert router.wasm_memory_limit_mb == 512
    assert router.docker_cpu_quota == 2.0
    assert router.docker_memory_limit == '1g'


def test_route_skill_low_risk():
    """Test routing low-risk skill."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_path = Path(tmpdir)
        (skill_path / 'skill.py').write_text(
            'def run(): return "hello"', encoding='utf-8'
        )

        router = SkillRouter()
        decision = router.route_skill(skill_path, RiskLevel.LOW)

        assert decision.sandbox_type == SandboxType.DOCKER
        assert 'Low risk' in decision.reason
        assert 'directory-snapshot' in decision.reason


def test_route_skill_medium_risk():
    """Test routing medium-risk skill."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_path = Path(tmpdir)
        (skill_path / 'skill.py').write_text(
            'def run(): return "hello"', encoding='utf-8'
        )

        router = SkillRouter()
        decision = router.route_skill(skill_path, RiskLevel.MEDIUM)

        assert decision.sandbox_type == SandboxType.DOCKER
        assert 'Medium risk' in decision.reason


def test_route_skill_high_risk_with_wasm():
    """Test routing high-risk skill with WASM available."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_path = Path(tmpdir)
        (skill_path / 'skill.py').write_text(
            'def run(): return "hello"', encoding='utf-8'
        )

        router = SkillRouter()
        decision = router.route_skill(skill_path, RiskLevel.HIGH)

        # If WASM is available and compatible, should use WASM
        # Otherwise falls back to Docker
        assert decision.sandbox_type in (SandboxType.WASM, SandboxType.DOCKER)
        assert 'High risk' in decision.reason


def test_route_skill_with_preferred_sandbox():
    """Test routing with user-preferred sandbox."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_path = Path(tmpdir)
        (skill_path / 'skill.py').write_text(
            'def run(): return "hello"', encoding='utf-8'
        )

        router = SkillRouter()
        decision = router.route_skill(
            skill_path, RiskLevel.LOW, preferred_sandbox=SandboxType.DOCKER
        )

        assert decision.sandbox_type == SandboxType.DOCKER
        assert 'user-preferred' in decision.reason


def test_route_skill_wasm_incompatible():
    """Test routing when skill is WASM incompatible."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_path = Path(tmpdir)
        # Create skill with async/await (incompatible with WASM)
        (skill_path / 'skill.py').write_text(
            'async def run(): return "hello"', encoding='utf-8'
        )

        router = SkillRouter()
        decision = router.route_skill(
            skill_path, RiskLevel.HIGH, preferred_sandbox=SandboxType.WASM
        )

        # SEC-08: WASM fallback must not silently choose directory-snapshot.
        assert decision.sandbox_type == SandboxType.DOCKER
        assert len(decision.warnings) > 0 or 'incompatible' in decision.reason.lower()


def test_get_sandbox_config_wasm():
    """Test getting WASM sandbox configuration."""
    router = SkillRouter(wasm_memory_limit_mb=512)
    config = router.get_sandbox_config(SandboxType.WASM)

    assert config['type'] == 'wasm'
    assert config['memory_limit_mb'] == 512


def test_get_sandbox_config_docker():
    """Test getting Docker sandbox configuration."""
    router = SkillRouter(docker_cpu_quota=2.0, docker_memory_limit='1g')
    config = router.get_sandbox_config(SandboxType.DOCKER)

    assert config['type'] == 'docker'
    assert config['cpu_quota'] == 2.0
    assert config['memory_limit'] == '1g'


def test_get_sandbox_config_directory_snapshot():
    """Test getting directory-snapshot sandbox configuration."""
    router = SkillRouter()
    config = router.get_sandbox_config(SandboxType.DIRECTORY_SNAPSHOT)

    assert config['type'] == 'directory-snapshot'
    assert 'cpu_quota' not in config
    assert 'memory_limit' not in config
