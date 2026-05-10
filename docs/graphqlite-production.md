# GraphQLite Production Deployment

## Overview

`GraphQLitePersistentStore` extends `GraphQLiteGraphStore` with production-grade defaults, index strategy, and schema migration support for persistent (non-`:memory:`) deployments.

## Quick Start

```python
from teaagent import GraphQLitePersistentStore, GraphQLiteProductionConfig, KnowledgeGraph

store = GraphQLitePersistentStore(
    GraphQLiteProductionConfig(database='/data/graph.db')
)

graph = KnowledgeGraph()
graph.add_document(Document(doc_id='d1', text='Alice owns Acme Inc.', source='graph'))
graph.add_edge(GraphEdge(source='alice', relation='OWNS', target='acme', document_ids=('d1',)))
store.sync_from_knowledge_graph(graph)

results = store.graph_retrieve('alice', max_depth=2, limit=5)
```

## Index Strategy

`GraphQLitePersistentStore` applies these indexes automatically when `auto_index=True` (default):

| Index | Target | Use Case |
|-------|--------|----------|
| `idx_entity_name` | Entity(name) | Entity-lookup traversal (`MATCH (a:Entity {name: ...})`) |
| `idx_document_source` | Document(source) | Source-filtered retrieval |
| `idx_document_doc_id` | Document(doc_id) | Document lookups after graph traversal |
| `idx_edge_relation` | EDGE(relation) | Relationship-type traversal |

Indexes are created with `IF NOT EXISTS` and are idempotent across restarts. The `GraphQLiteGraphStore.upsert_node` / `upsert_edge` calls populate the `Entity` and `Document` labels which feed these indexes.

### Cypher Query Tuning

**Entity-lookup traversal** (used by `graph_retrieve`):

```cypher
MATCH (a:Entity {name: 'alice'})-[rel *1..2]-(b:Entity)
RETURN a.name as source, rel, b.name as target
```

- The `Entity(name)` index accelerates the `{name: '...'}` lookup at the start of the traversal.
- `*1..2` bounds the variable-length path to a reasonable depth.
- `EDGE(relation)` index accelerates filtering when the query narrows to specific relationship types.

**Document retrieval after traversal:**

```cypher
MATCH (d:Document {doc_id: 'd1'}) RETURN d
```

- The `Document(doc_id)` index turns this into a point lookup.

## PRAGMA Configuration

The following pragmas are set on the backing SQLite connection for production workloads:

```text
PRAGMA journal_mode=WAL       — allows concurrent readers
PRAGMA synchronous=NORMAL     — balances durability and write throughput
PRAGMA busy_timeout=5000      — 5s wait before BUSY errors
PRAGMA cache_size=-2000       — 2 MB page cache
PRAGMA foreign_keys=ON        — referential integrity for graph edges
```

To customize, pass a `pragmas` tuple to `GraphQLiteProductionConfig`:

```python
config = GraphQLiteProductionConfig(
    database='/data/graph.db',
    pragmas=(
        'PRAGMA journal_mode=WAL',
        'PRAGMA synchronous=FULL',
        'PRAGMA busy_timeout=10000',
        'PRAGMA cache_size=-8000',
    ),
)
```

## Schema Migrations

`GraphQLitePersistentStore` uses `SQLiteMigrationStore` / `MigrationRunner` to track and apply schema changes. Migrations run automatically when `auto_migrate=True` (default).

### Migration Versions

| Version | Description |
|---------|-------------|
| 1 | Base graph schema: Document nodes, Entity nodes, typed relationships |
| 2 | Index on Entity(name) |
| 3 | Index on Document(source) |
| 4 | Index on Document(doc_id) |
| 5 | Index on EDGE(relation) |

### Checking Migration Status

```python
status = store.migration_status()
print(status)  # {'applied': [1,2,3,4,5], 'pending': [], 'total': 5}
```

CLI:
```bash
teaagent doctor graphqlite migrate --database /data/graph.db
```

### Manual Migration

To add a custom migration, define a `SchemaMigration` and run it through the `MigrationRunner`:

```python
from teaagent.schema_migration import SchemaMigration, SQLiteMigrationStore, MigrationRunner

store = SQLiteMigrationStore('/data/graph.db')
runner = MigrationRunner(store, [
    SchemaMigration(version=6, description='Custom full-text index', sql='...'),
])
result = runner.apply_pending()
```

## Hardware Sizing

- **<1M entities/edges**: SQLite handles this comfortably with the default 2MB cache. A single-node deployment suffices.
- **1M–10M entities/edges**: Increase `cache_size` to `-8000` (8MB) or higher. Consider running on SSD-backed storage.
- **>10M entities/edges**: Consider sharding across multiple GraphQLite instances keyed by entity domain, or explore external graph databases.

## Monitoring

Check the health of a GraphQLite database before every agent invocation:

```python
from teaagent import check_graphqlite_runtime

ok, message = check_graphqlite_runtime(database='/data/graph.db')
if not ok:
    raise RuntimeError(f'GraphQLite unavailable: {message}')
```

The smoke check creates and queries a test node in the persistent store. It is lightweight (one node, one query) and suitable for readiness probes.

## Backup and Recovery

SQLite WAL databases are backed up via standard file-level tools while the database is in use:

```bash
sqlite3 /data/graph.db ".backup /backup/graph-$(date +%Y%m%d).db"
```

For point-in-time recovery, use WAL archival alongside incremental file backups.
