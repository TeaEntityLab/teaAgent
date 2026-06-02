# config — Public API Reference

## Data Models

### `ConfigLayer`
| Field | Type | Description |
|---|---|---|
| `DEFAULT` | `str` | Hard-coded fallback source. |
| `USER` | `str` | `~/.teaagent/config.json` source. |
| `WORKSPACE` | `str` | `<root>/.teaagent/config.json` source. |
| `ENV` | `str` | `TEAAGENT_*` environment source. |

### `ResolvedConfig`
| Field | Type | Description |
|---|---|---|
| `values` | `dict[str, Any]` | Resolved values after precedence merge. |
| `sources` | `dict[str, ConfigLayer]` | Winning source layer per key. |

### `ConfigResolver`
| Field | Type | Description |
|---|---|---|
| `workspace_root` | `str | Path` | Root for workspace config lookup. |
| `user_home` | `Optional[str | Path]` | Optional home-dir override. |

## Functions

### `load_workspace_config(root: str | Path) -> dict[str, Any]`
**Location**: `teaagent/config_loader.py:142`
**Pre-condition**: `root` is a readable path.
**Post-condition**: Returns workspace config dict or `{}` if missing/unreadable.

### `ConfigResolver.resolve() -> ResolvedConfig`
**Location**: `teaagent/config_loader.py:171`
**Pre-condition**: None.
**Post-condition**: Returns merged config with source attribution (`default < user < workspace < env`).

### `ResolvedConfig.get(key: str, *, default: Any = None) -> Any`
**Location**: `teaagent/config_loader.py:90`
**Pre-condition**: None.
**Post-condition**: Returns resolved value or provided default.

### `ResolvedConfig.source(key: str) -> Optional[ConfigLayer]`
**Location**: `teaagent/config_loader.py:93`
**Pre-condition**: None.
**Post-condition**: Returns source layer for key, else `None`.

### `ResolvedConfig.show() -> list[str]`
**Location**: `teaagent/config_loader.py:96`
**Pre-condition**: None.
**Post-condition**: Returns human-readable `key = value [layer]` lines.
