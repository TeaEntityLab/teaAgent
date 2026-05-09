from __future__ import annotations

from dataclasses import dataclass
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
