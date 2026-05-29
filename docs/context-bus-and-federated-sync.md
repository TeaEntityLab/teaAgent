# Context Bus and Federated Graph Sync

## Context Bus (`teaagent.context_bus`)

Cross-sandbox **Delta cards** for parallel agents share state through a workflow-scoped SQLite database.

| Topic | Behavior |
|-------|----------|
| Storage | `{db_path}` from `ContextBusConfig` (typically under `.teaagent/`) |
| Concurrency | One SQLite connection per thread (`threading.local`); WAL mode when `enable_wal_mode=True` |
| Connect | `timeout=5.0` seconds; `check_same_thread=False` |
| Reconnect | Generation counter invalidates stale handles; `close()` shuts down all registered connections |
| API | `publish_delta`, `subscribe_deltas`, `get_delta_count`, `cleanup_old_deltas`, `archive_to_rag`, `close` |

Parallel agents should call `close()` on the main owner thread when the workflow ends.

Tests: `tests/test_phase5_context_bus.py` (including multi-thread publish).

## Federated Graph Sync (`teaagent.federated_sync`)

P2P-style export/import of graph change batches for multi-agent knowledge graphs.

| Topic | Behavior |
|-------|----------|
| State file | `.teaagent/federated_sync_state.json` in the workspace |
| Transport | JSON files via `export_sync_message` / `import_sync_message` |
| Errors | Invalid JSON, missing keys, or I/O failures return `None` and log a warning |

CLI: `teaagent sync export|import|status` (see parser help).

Tests: `tests/test_federated_sync.py`, `tests/test_sync_cli.py`.
