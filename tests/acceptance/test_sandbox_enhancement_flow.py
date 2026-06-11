"""Test module for skill sandbox routing and isolation integration.

This module tests the skill sandbox system, which provides isolation for skill
execution based on risk level. Skills can be executed in different sandbox types
(directory-snapshot, docker, or none) depending on their assessed risk, providing
a defense-in-depth approach to skill security.

Key concepts tested:
- Auto Isolation Mode: The 'auto' isolation mode is supported for skill execution
- Risk-Based Isolation: Low risk uses directory-snapshot, medium risk uses docker
- Sandbox Type Mapping: SandboxType enum maps to isolation configuration strings
- Docker Configuration: CPU quota and memory limits can be configured for docker
- Skill Execution: Skills can be executed with appropriate isolation based on risk
- Skill Router: SkillRouter manages isolation planning and execution

Acceptance Criteria:
- AC1: Auto isolation mode is supported and normalized correctly
- AC2: Low risk skills use directory-snapshot isolation
- AC3: Medium risk skills use docker isolation
- AC4: SandboxType enum maps correctly to isolation strings
- AC5: Docker configuration (cpu_quota, memory_limit) is applied to isolation plan
- AC6: Skills can be executed with risk-based isolation and return results

Technical Details:
- normalize_subagent_isolation normalizes isolation mode strings
- plan_skill_isolation determines isolation based on RiskLevel
- SandboxType enum defines isolation types (DOCKER, DIRECTORY_SNAPSHOT, NONE)
- isolation_for_sandbox_type maps SandboxType to isolation configuration
- SkillRouter applies docker configuration (cpu_quota, memory_limit)
- execute_skill runs skills with appropriate isolation based on risk_level

References:
- Sandbox design: /docs/architecture/sandbox_system.md
- Skill isolation: /docs/architecture/skill_isolation.md
- Risk assessment: /docs/security/risk_assessment.md
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from teaagent.consensus import RiskLevel
from teaagent.skill_executor import execute_skill
from teaagent.skill_router import (
    SandboxType,
    SkillRouter,
    isolation_for_sandbox_type,
    plan_skill_isolation,
)
from teaagent.subagents._isolation import normalize_subagent_isolation


def test_auto_isolation_mode_is_supported() -> None:
    # Verify 'auto' isolation mode is supported and normalized
    assert normalize_subagent_isolation('auto') == 'auto', (
        'Expected "auto" isolation mode to be supported'
    )


def test_plan_skill_isolation_low_risk_uses_directory_snapshot() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_path = Path(tmp)
        (skill_path / 'SKILL.md').write_text('# helper\n', encoding='utf-8')
        plan = plan_skill_isolation(skill_path, RiskLevel.LOW)
        # Verify low risk skills use directory-snapshot isolation
        assert plan.isolation == 'directory-snapshot', (
            f'Expected isolation "directory-snapshot" for low risk, got {plan.isolation!r}'
        )
        assert plan.sandbox_type == SandboxType.DIRECTORY_SNAPSHOT, (
            f'Expected sandbox_type DIRECTORY_SNAPSHOT for low risk, got {plan.sandbox_type!r}'
        )


def test_plan_skill_isolation_medium_risk_uses_docker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_path = Path(tmp)
        (skill_path / 'SKILL.md').write_text('# helper\n', encoding='utf-8')
        plan = plan_skill_isolation(skill_path, RiskLevel.MEDIUM)
        # Verify medium risk skills use docker isolation
        assert plan.isolation == 'docker', (
            f'Expected isolation "docker" for medium risk, got {plan.isolation!r}'
        )
        assert plan.sandbox_type == SandboxType.DOCKER, (
            f'Expected sandbox_type DOCKER for medium risk, got {plan.sandbox_type!r}'
        )


def test_isolation_for_sandbox_type_mapping() -> None:
    # Verify SandboxType enum maps to correct isolation strings
    assert isolation_for_sandbox_type(SandboxType.DOCKER) == 'docker', (
        'Expected DOCKER to map to "docker"'
    )
    assert (
        isolation_for_sandbox_type(SandboxType.DIRECTORY_SNAPSHOT)
        == 'directory-snapshot'
    ), 'Expected DIRECTORY_SNAPSHOT to map to "directory-snapshot"'


def test_skill_router_docker_config_applied_to_plan() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_path = Path(tmp)
        (skill_path / 'SKILL.md').write_text('# helper\n', encoding='utf-8')
        router = SkillRouter(docker_cpu_quota=1.5, docker_memory_limit='512m')
        plan = plan_skill_isolation(skill_path, RiskLevel.MEDIUM, router=router)
        # Verify docker configuration is applied to isolation plan
        assert plan.cpu_quota == 1.5, (
            f'Expected cpu_quota 1.5 from router config, got {plan.cpu_quota}'
        )
        assert plan.memory_limit == '512m', (
            f'Expected memory_limit "512m" from router config, got {plan.memory_limit!r}'
        )


def test_execute_skill_routes_and_runs_low_risk_tool() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_path = Path(tmp)
        (skill_path / 'SKILL.md').write_text('# helper\n', encoding='utf-8')
        (skill_path / 'tool.py').write_text(
            'def run(payload):\n    return {"value": payload["n"]}\n',
            encoding='utf-8',
        )
        result = execute_skill(skill_path, {'n': 7}, risk_level=RiskLevel.LOW)
        # Verify skill execution succeeds with correct output
        assert result.success is True, (
            f'Expected skill execution to succeed, got success={result.success}'
        )
        assert result.output == {'value': 7}, (
            f'Expected output {{"value": 7}}, got {result.output}'
        )
