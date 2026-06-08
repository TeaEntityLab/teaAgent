from __future__ import annotations

from pathlib import Path

from teaagent.code_analysis._config import CodeAnalysisConfig
from teaagent.code_analysis._tools import (
    _GRAPH_BY_ROOT,
    _MAX_GRAPH_CACHE,
    clear_graph_cache,
    register_code_analysis_tools,
)
from teaagent.types import ToolRegistry


def test_graph_cache_evicts_oldest_when_over_capacity(tmp_path: Path) -> None:
    clear_graph_cache()
    try:
        roots = [tmp_path / f'proj_{i}' for i in range(_MAX_GRAPH_CACHE + 1)]
        for root in roots:
            root.mkdir()
            registry = ToolRegistry()
            cfg = CodeAnalysisConfig.from_root(root, enabled=True)
            register_code_analysis_tools(registry, cfg)
            registry.execute('code_relations_to_graph', {'path': 'README.md'})

        assert len(_GRAPH_BY_ROOT) == _MAX_GRAPH_CACHE
        assert str(roots[0]) not in _GRAPH_BY_ROOT
        assert str(roots[-1]) in _GRAPH_BY_ROOT
    finally:
        clear_graph_cache()
