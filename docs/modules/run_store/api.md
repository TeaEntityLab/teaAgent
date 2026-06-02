# run_store — Public API Reference

## Data Models

### `RunSummary`
| Field | Type | Description |
|---|---|---|
| `run_id` | `str` | Stable run identifier. |
| `task` | `str` | Task text from `run_started`. |
| `status` | `str` | Derived run status. |
| `created_at` | `str` | First event timestamp. |
| `updated_at` | `str` | Last event timestamp. |
| `path` | `Path` | JSONL run log path. |
| `final_answer` | `Optional[str]` | Final answer for completed runs. |

### `RunStore`
| Field | Type | Description |
|---|---|---|
| `root` | `Path` | Workspace root. |
| `readonly` | `bool` | Blocks mutating persistence operations when true. |
| `store_dir` | `Path` | Run storage directory `.teaagent/runs`. |

## Functions

### `RunStore.list_runs(*, limit: int = 20) -> list[RunSummary]`
**Location**: `teaagent/run_store.py:125`
**Pre-condition**: None.
**Post-condition**: Returns newest-first run summaries; corrupt files are skipped and counted.

### `RunStore.show_run(run_id: str) -> list[dict[str, Any]]`
**Location**: `teaagent/run_store.py:138`
**Pre-condition**: Run file exists.
**Post-condition**: Returns parsed event list; malformed lines increment corruption count.

### `RunStore.task_for_run(run_id: str) -> str`
**Location**: `teaagent/run_store.py:152`
**Pre-condition**: Run contains `run_started` with a string task.
**Post-condition**: Returns task string or raises `ValueError`.

### `RunStore.observations_for_run(run_id: str) -> list[dict[str, Any]]`
**Location**: `teaagent/run_store.py:160`
**Pre-condition**: None.
**Post-condition**: Returns normalized `tool_call_completed` observation records.

### `RunStore.pending_approval_for_run(run_id: str) -> Optional[dict[str, Any]]`
**Location**: `teaagent/run_store.py:179`
**Pre-condition**: None.
**Post-condition**: Returns unresolved approval payload if one is pending, else `None`.

### `RunStore.health_report() -> dict[str, Any]`
**Location**: `teaagent/run_store.py:296`
**Pre-condition**: None.
**Post-condition**: Returns corruption-aware health snapshot.
