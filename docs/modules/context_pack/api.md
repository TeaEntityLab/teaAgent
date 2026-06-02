# context_pack — Public API Reference

## Data Models

### `ContextPack`
| Field | Type | Description |
|---|---|---|
| `task` | `str` | Original task text. |
| `candidate_files` | `list[dict[str, Any]]` | Candidate file entries with path/existence metadata. |
| `memories` | `list[dict[str, Any]]` | Memory hits relevant to task. |
| `symbols` | `list[dict[str, Any]]` | Symbol hints from LSP or file stats. |
| `graph_rag` | `dict[str, Any]` | Indexed search evidence payload. |
| `read_only` | `bool` | Read-only flag propagated by builder. |

## Functions

### `build_context_pack(task: str, *, root: str | Path = '.', memory_limit: int = 5, file_limit: int = 12, symbol_limit: int = 8, graph_hit_limit: int = 5, include_agents_md: bool = True, hydrate_lsp: bool = False, search_graph: bool = True, code_analysis_config: Optional[CodeAnalysisConfig] = None, readonly: bool = False) -> ContextPack`
**Location**: `teaagent/context_pack.py:474`
**Pre-condition**: `root` is readable and `task` is meaningful text.
**Post-condition**: Returns a populated `ContextPack`; missing index/config inputs degrade gracefully.

### `ContextPack.to_dict() -> dict[str, Any]`
**Location**: `teaagent/context_pack.py:39`
**Pre-condition**: `ContextPack` instance exists.
**Post-condition**: Returns JSON-serializable dictionary form.
