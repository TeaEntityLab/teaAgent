"""AC: Skill sandbox routing and isolation integration."""

from __future__ import annotations

import tempfile
from pathlib import Path

from teaagent.consensus import RiskLevel
from teaagent.skill_router import (
    SandboxType,
    SkillRouter,
    isolation_for_sandbox_type,
    plan_skill_isolation,
)
from teaagent.subagents._isolation import normalize_subagent_isolation


def test_auto_isolation_mode_is_supported() -> None:
    assert normalize_subagent_isolation('auto') == 'auto'


def test_plan_skill_isolation_low_risk_uses_directory_snapshot() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_path = Path(tmp)
        (skill_path / 'SKILL.md').write_text('# helper\n', encoding='utf-8')
        plan = plan_skill_isolation(skill_path, RiskLevel.LOW)
        assert plan.isolation == 'directory-snapshot'
        assert plan.sandbox_type == SandboxType.DIRECTORY_SNAPSHOT


def test_plan_skill_isolation_medium_risk_uses_docker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_path = Path(tmp)
        (skill_path / 'SKILL.md').write_text('# helper\n', encoding='utf-8')
        plan = plan_skill_isolation(skill_path, RiskLevel.MEDIUM)
        assert plan.isolation == 'docker'
        assert plan.sandbox_type == SandboxType.DOCKER


def test_isolation_for_sandbox_type_mapping() -> None:
    assert isolation_for_sandbox_type(SandboxType.DOCKER) == 'docker'
    assert (
        isolation_for_sandbox_type(SandboxType.DIRECTORY_SNAPSHOT)
        == 'directory-snapshot'
    )


def test_skill_router_docker_config_applied_to_plan() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_path = Path(tmp)
        (skill_path / 'SKILL.md').write_text('# helper\n', encoding='utf-8')
        router = SkillRouter(docker_cpu_quota=1.5, docker_memory_limit='512m')
        plan = plan_skill_isolation(skill_path, RiskLevel.MEDIUM, router=router)
        assert plan.cpu_quota == 1.5
        assert plan.memory_limit == '512m'
