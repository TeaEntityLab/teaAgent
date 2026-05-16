from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


@dataclass(frozen=True)
class LSPServerConfig:
    language: str
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    initialization_options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CodeReference:
    symbol: str
    file_path: str
    line: int
    column: int
    kind: str
    detail: str = ''


class LSPClient(Protocol):
    def initialize(self, root_uri: str) -> None: ...
    def shutdown(self) -> None: ...
    def goto_definition(
        self, path: str, line: int, col: int
    ) -> list[CodeReference]: ...
    def find_references(
        self, path: str, line: int, col: int
    ) -> list[CodeReference]: ...
    def hover(self, path: str, line: int, col: int) -> Optional[str]: ...
    def document_diagnostics(self, path: str) -> list[dict[str, Any]]: ...
    def document_symbols(self, path: str) -> list[CodeReference]: ...
