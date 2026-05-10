from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Protocol


@dataclass(frozen=True)
class CodeModeResult:
    variables: dict[str, Any]


@dataclass(frozen=True)
class CodeModeSandbox:
    timeout_seconds: float = 2.0
    cpu_seconds: int = 2
    memory_bytes: int = 64 * 1024 * 1024
    max_output_bytes: int = 1 * 1024 * 1024


class CodeModeBackend(Protocol):
    def execute(
        self,
        code: str,
        inputs: dict[str, Any],
        sandbox: CodeModeSandbox,
    ) -> CodeModeResult: ...


@dataclass(frozen=True)
class ContainerCodeModeBackendConfig:
    image: str
    runtime: str = 'docker'
    python_executable: str = 'python3'
    network: str = 'none'
    cpus: float = 1.0
    user: str = '65534:65534'
    tmpfs_size_mb: int = 16
    require_image_digest: bool = False
    allowed_images: Optional[frozenset[str]] = None


class SandboxProfile(str, Enum):
    LOCAL = 'local'
    CI = 'ci'
    PRODUCTION = 'production'

    def default_sandbox(self) -> 'CodeModeSandbox':
        if self == SandboxProfile.LOCAL:
            return CodeModeSandbox(
                timeout_seconds=10.0,
                cpu_seconds=10,
                memory_bytes=128 * 1024 * 1024,
                max_output_bytes=4 * 1024 * 1024,
            )
        if self == SandboxProfile.CI:
            return CodeModeSandbox(
                timeout_seconds=5.0,
                cpu_seconds=5,
                memory_bytes=64 * 1024 * 1024,
                max_output_bytes=2 * 1024 * 1024,
            )
        # PRODUCTION — tightest defaults
        return CodeModeSandbox(
            timeout_seconds=2.0,
            cpu_seconds=2,
            memory_bytes=32 * 1024 * 1024,
            max_output_bytes=1 * 1024 * 1024,
        )

    def validate_runtime_support(self) -> list[str]:
        warnings: list[str] = []
        if self != SandboxProfile.PRODUCTION:
            return warnings
        try:
            import resource as _resource

            _resource.getrlimit(_resource.RLIMIT_AS)
        except (ImportError, AttributeError, ValueError):
            warnings.append(
                'RLIMIT_AS unavailable — memory limits will not be enforced in PRODUCTION profile'
            )
        try:
            import resource as _resource

            _resource.getrlimit(_resource.RLIMIT_CPU)
        except (ImportError, AttributeError, ValueError):
            warnings.append(
                'RLIMIT_CPU unavailable — CPU limits will not be enforced in PRODUCTION profile'
            )
        return warnings
