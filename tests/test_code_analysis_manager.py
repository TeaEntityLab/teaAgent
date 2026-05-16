from __future__ import annotations

from teaagent.code_analysis._config import CodeAnalysisConfig
from teaagent.code_analysis._manager import LSPServerManager


def test_unknown_extension_has_no_client(tmp_path):
    manager = LSPServerManager(CodeAnalysisConfig.from_root(tmp_path, enabled=True))
    assert manager.get_client('README.md') is None


def test_missing_lsp_binary_gracefully_returns_none(tmp_path, monkeypatch):
    from teaagent.code_analysis import _manager as manager_mod

    class _BoomClient:
        def __init__(self, *args, **kwargs):
            pass

        def initialize(self, root_uri: str) -> None:
            raise FileNotFoundError('missing')

    monkeypatch.setattr(manager_mod, 'StdioLSPClient', _BoomClient)
    manager = LSPServerManager(CodeAnalysisConfig.from_root(tmp_path, enabled=True))
    assert manager.get_client('a.py') is None
