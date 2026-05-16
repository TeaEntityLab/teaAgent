from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from teaagent.code_analysis._types import LSPServerConfig


@dataclass(frozen=True)
class CodeAnalysisConfig:
    root: Path
    enabled: bool = False
    max_files_for_context: int = 5
    server_timeout_seconds: float = 10.0
    diagnostic_severity_limit: int = 2
    servers: tuple[LSPServerConfig, ...] = (
        LSPServerConfig('python', ['pyright-langserver', '--stdio']),
        LSPServerConfig('typescript', ['typescript-language-server', '--stdio']),
    )

    @classmethod
    def from_root(cls, root: str | Path, **kwargs: Any) -> 'CodeAnalysisConfig':
        return cls(root=Path(root).resolve(), **kwargs)
