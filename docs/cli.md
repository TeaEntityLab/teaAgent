# TeaAgent CLI

## Install

For local development, install the package in editable mode:

```bash
python3 -m pip install -e .
```

Then run:

```bash
teaagent --help
```

You can also run without installing the console script:

```bash
python3 -m teaagent.cli --help
```

## GraphQLite

Check the GraphQLite runtime:

```bash
teaagent doctor graphqlite
```

Run a smoke query:

```bash
teaagent graphqlite smoke
```

Run a Cypher query:

```bash
teaagent graphqlite query "MATCH (n:SmokeTest) RETURN n.name"
```

Use a persistent SQLite file:

```bash
teaagent graphqlite smoke --database ./graph.db
teaagent graphqlite query "MATCH (n) RETURN n" --database ./graph.db
```

## Interactive TUI

Start the interactive terminal UI:

```bash
teaagent tui
```

Or without installing the console script:

```bash
python3 -m teaagent.cli tui
```

Inside the TUI:

```text
help
doctor
smoke
query MATCH (n:SmokeTest) RETURN n.name
use ./graph.db
exit
```

Start with a persistent database:

```bash
teaagent tui --database ./graph.db
```
