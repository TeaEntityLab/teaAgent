"""Skill execution routing to appropriate sandboxes.

This module provides routing logic for executing skills in the appropriate
sandbox based on risk level, WASM compatibility, and user preferences.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from teaagent.consensus import RiskLevel
from teaagent.wasm_runtime import WASMRuntime, is_wasm_available

logger = logging.getLogger(__name__)


class SandboxType(Enum):
    """Available sandbox types."""

    AUTO = 'auto'
    DIRECTORY_SNAPSHOT = 'directory-snapshot'
    DOCKER = 'docker'
    WASM = 'wasm'


@dataclass
class RoutingDecision:
    """Decision on which sandbox to use for a skill."""

    sandbox_type: SandboxType
    reason: str
    fallback_available: bool = True
    warnings: Optional[list[str]] = None

    def __post_init__(self) -> None:
        if self.warnings is None:
            self.warnings = []


@dataclass(frozen=True)
class SkillIsolationPlan:
    """Resolved subagent isolation from skill routing."""

    isolation: str
    sandbox_type: SandboxType
    reason: str
    cpu_quota: Optional[float] = None
    memory_limit: Optional[str] = None


def isolation_for_sandbox_type(sandbox_type: SandboxType) -> str:
    """Map sandbox router output to ``prepare_subagent_isolation`` mode."""
    if sandbox_type == SandboxType.DOCKER:
        return 'docker'
    if sandbox_type in {SandboxType.DIRECTORY_SNAPSHOT, SandboxType.WASM}:
        return 'directory-snapshot'
    return 'directory-snapshot'


def plan_skill_isolation(
    skill_path: Path,
    risk_level: RiskLevel,
    *,
    router: Optional[SkillRouter] = None,
) -> SkillIsolationPlan:
    """Route a skill to an isolation mode and docker resource limits."""
    skill_router = router or SkillRouter()
    decision = skill_router.route_skill(skill_path, risk_level)
    return SkillIsolationPlan(
        isolation=isolation_for_sandbox_type(decision.sandbox_type),
        sandbox_type=decision.sandbox_type,
        reason=decision.reason,
        cpu_quota=skill_router.docker_cpu_quota,
        memory_limit=skill_router.docker_memory_limit,
    )


class SkillRouter:
    """Routes skills to appropriate sandboxes."""

    def __init__(
        self,
        default_sandbox: SandboxType = SandboxType.AUTO,
        wasm_memory_limit_mb: int = 256,
        docker_cpu_quota: Optional[float] = None,
        docker_memory_limit: Optional[str] = None,
    ) -> None:
        """Initialize skill router.

        Args:
            default_sandbox: Default sandbox type
            wasm_memory_limit_mb: Memory limit for WASM runtime
            docker_cpu_quota: CPU quota for Docker containers
            docker_memory_limit: Memory limit for Docker containers
        """
        self.default_sandbox = default_sandbox
        self.wasm_memory_limit_mb = wasm_memory_limit_mb
        self.docker_cpu_quota = docker_cpu_quota
        self.docker_memory_limit = docker_memory_limit

    def route_skill(
        self,
        skill_path: Path,
        risk_level: RiskLevel,
        preferred_sandbox: Optional[SandboxType] = None,
    ) -> RoutingDecision:
        """Determine which sandbox to use for a skill.

        Args:
            skill_path: Path to the skill directory
            risk_level: Risk level of the skill
            preferred_sandbox: User's preferred sandbox (overrides auto-selection)

        Returns:
            Routing decision with sandbox type and reasoning
        """
        # If user specified a sandbox, use it
        if preferred_sandbox and preferred_sandbox != SandboxType.AUTO:
            return self._validate_preferred_sandbox(
                skill_path, preferred_sandbox, risk_level
            )

        # Auto-select based on risk level
        return self._auto_select_sandbox(skill_path, risk_level)

    def _validate_preferred_sandbox(
        self,
        skill_path: Path,
        preferred_sandbox: SandboxType,
        risk_level: RiskLevel,
    ) -> RoutingDecision:
        """Validate and use preferred sandbox.

        Args:
            skill_path: Path to the skill directory
            preferred_sandbox: User's preferred sandbox
            risk_level: Risk level of the skill

        Returns:
            Routing decision
        """
        warnings = []

        if preferred_sandbox == SandboxType.WASM:
            if not is_wasm_available():
                return RoutingDecision(
                    sandbox_type=SandboxType.DIRECTORY_SNAPSHOT,
                    reason='WASM not available, falling back to directory-snapshot',
                    fallback_available=True,
                    warnings=['WASM runtime not installed'],
                )

            # Check WASM compatibility
            if is_wasm_available():
                runtime = WASMRuntime(memory_limit_mb=self.wasm_memory_limit_mb)
                compat_result = runtime.check_compatibility(skill_path)

                if not compat_result['compatible']:
                    return RoutingDecision(
                        sandbox_type=SandboxType.DIRECTORY_SNAPSHOT,
                        reason='Skill not compatible with WASM, falling back to directory-snapshot',
                        fallback_available=True,
                        warnings=compat_result['issues'],
                    )

                warnings.extend(compat_result['warnings'])

            return RoutingDecision(
                sandbox_type=SandboxType.WASM,
                reason='Using user-preferred WASM sandbox',
                fallback_available=True,
                warnings=warnings,
            )

        elif preferred_sandbox == SandboxType.DOCKER:
            # Docker is always available if installed
            return RoutingDecision(
                sandbox_type=SandboxType.DOCKER,
                reason='Using user-preferred Docker sandbox',
                fallback_available=True,
                warnings=warnings,
            )

        else:
            return RoutingDecision(
                sandbox_type=preferred_sandbox,
                reason='Using user-preferred sandbox',
                fallback_available=True,
                warnings=warnings,
            )

    def _auto_select_sandbox(
        self,
        skill_path: Path,
        risk_level: RiskLevel,
    ) -> RoutingDecision:
        """Auto-select sandbox based on risk level.

        Args:
            skill_path: Path to the skill directory
            risk_level: Risk level of the skill

        Returns:
            Routing decision
        """
        # Low risk: directory-snapshot (fastest)
        if risk_level == RiskLevel.LOW:
            return RoutingDecision(
                sandbox_type=SandboxType.DIRECTORY_SNAPSHOT,
                reason='Low risk: using directory-snapshot for speed',
                fallback_available=True,
            )

        # Medium risk: Docker (balanced)
        if risk_level == RiskLevel.MEDIUM:
            return RoutingDecision(
                sandbox_type=SandboxType.DOCKER,
                reason='Medium risk: using Docker for balanced isolation',
                fallback_available=True,
            )

        # High or critical risk: Try WASM first, fallback to Docker
        if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            if is_wasm_available():
                runtime = WASMRuntime(memory_limit_mb=self.wasm_memory_limit_mb)
                compat_result = runtime.check_compatibility(skill_path)

                if compat_result['compatible']:
                    return RoutingDecision(
                        sandbox_type=SandboxType.WASM,
                        reason='High risk: using WASM for maximum isolation',
                        fallback_available=True,
                        warnings=compat_result['warnings'],
                    )
                else:
                    return RoutingDecision(
                        sandbox_type=SandboxType.DOCKER,
                        reason=f'High risk: WASM incompatible ({compat_result["issues"][0]}), using Docker',
                        fallback_available=True,
                        warnings=compat_result['issues'],
                    )
            else:
                return RoutingDecision(
                    sandbox_type=SandboxType.DOCKER,
                    reason='High risk: WASM not available, using Docker',
                    fallback_available=True,
                    warnings=['WASM runtime not installed'],
                )

        # Default fallback
        return RoutingDecision(
            sandbox_type=SandboxType.DIRECTORY_SNAPSHOT,
            reason='Default: using directory-snapshot',
            fallback_available=True,
        )

    def get_sandbox_config(
        self,
        sandbox_type: SandboxType,
    ) -> dict[str, Any]:
        """Get configuration for a sandbox type.

        Args:
            sandbox_type: The sandbox type

        Returns:
            Configuration dictionary
        """
        config: dict[str, Any] = {'type': sandbox_type.value}

        if sandbox_type == SandboxType.WASM:
            config['memory_limit_mb'] = self.wasm_memory_limit_mb
        elif sandbox_type == SandboxType.DOCKER:
            if self.docker_cpu_quota:
                config['cpu_quota'] = self.docker_cpu_quota
            if self.docker_memory_limit:
                config['memory_limit'] = self.docker_memory_limit

        return config
