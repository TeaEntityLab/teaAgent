from __future__ import annotations

from pathlib import Path
from typing import Optional

from teaagent.code_analysis._client import StdioLSPClient
from teaagent.code_analysis._config import CodeAnalysisConfig
from teaagent.code_analysis._types import CodeReference, LSPClient

_EXT_LANGUAGE = {
    '.py': 'python',
    '.pyi': 'python',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.js': 'typescript',
    '.jsx': 'typescript',
}


class LSPServerManager:
    def __init__(self, config: CodeAnalysisConfig) -> None:
        self._config = config
        self._servers: dict[str, LSPClient] = {}

    def get_client(self, file_path: str) -> Optional[LSPClient]:
        lang = _detect_language(file_path)
        if lang is None:
            return None
        existing = self._servers.get(lang)
        if existing is not None:
            return existing
        server_cfg = next(
            (cfg for cfg in self._config.servers if cfg.language == lang), None
        )
        if server_cfg is None:
            return None
        client = StdioLSPClient(
            server_cfg,
            timeout_seconds=self._config.server_timeout_seconds,
        )
        try:
            client.initialize(self.root.as_uri())
        except Exception:
            return None
        self._servers[lang] = client
        return client

    def goto_definition(self, path: str, line: int, column: int) -> list[CodeReference]:
        client = self.get_client(path)
        return client.goto_definition(path, line, column) if client else []

    def find_references(self, path: str, line: int, column: int) -> list[CodeReference]:
        client = self.get_client(path)
        return client.find_references(path, line, column) if client else []

    def document_diagnostics(self, path: str) -> list[dict]:
        client = self.get_client(path)
        return client.document_diagnostics(path) if client else []

    def document_symbols(self, path: str) -> list[CodeReference]:
        client = self.get_client(path)
        return client.document_symbols(path) if client else []

    def shutdown_all(self) -> None:
        for client in self._servers.values():
            client.shutdown()
        self._servers.clear()

    @property
    def root(self) -> Path:
        return self._config.root


def _detect_language(path: str) -> Optional[str]:
    suffix = Path(path).suffix.lower()
    return _EXT_LANGUAGE.get(suffix)
