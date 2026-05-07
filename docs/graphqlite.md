# GraphQLite Integration

TeaAgent uses `graphqlite` as the Graph RAG persistence option. GraphQLite is an SQLite graph extension with Cypher support, not a GraphQL API server.

## Requirement

Install through either project metadata or requirements:

```bash
pip install -r requirements.txt
```

GraphQLite requires a Python SQLite runtime that supports extension loading. On macOS, the Apple Command Line Tools Python may not expose `sqlite3.Connection.enable_load_extension`. TeaAgent includes `pysqlite3` in requirements and automatically shims `sqlite3` to `pysqlite3` when the platform runtime lacks extension loading.

## Adapter

Use `GraphQLiteGraphStore` to sync the in-memory `KnowledgeGraph` into GraphQLite:

```python
from teaagent import GraphQLiteGraphStore

store = GraphQLiteGraphStore()
store.sync_from_knowledge_graph(graph)
rows = store.query("MATCH (a:Entity)-[r]->(b:Entity) RETURN a.name, r.relation, b.name")
```

The adapter lazy-loads `graphqlite`, so tests and non-graph workflows can still run before the runtime dependency is installed.

## Runtime Check

```python
from teaagent import check_graphqlite_runtime

ok, message = check_graphqlite_runtime()
print(ok, message)
```
