"""AC-NEW-25: Read-only context pack for planning/preflight.

As a user, I want preflight to surface why candidate files and memories were
selected without mutating the workspace.

Acceptance criteria:
- `agent preflight` includes a read-only `context_pack` with candidate files.
- Context pack evidence is deterministic for known task path mentions.
- Hybrid, knowledge, and GraphQLite indexes contribute read-only graph hits.
- Read-only planning runs still block workspace writes (regression guard).
"""

from __future__ import annotations

import io
import json
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main
from teaagent.graphqlite_store import GraphQLiteConfig, GraphQLiteGraphStore
from teaagent.hybrid_search import LocalHybridSearchBackend
from teaagent.memory import MemoryCatalog
from tests.test_graphqlite_store import FakeGraphQLiteGraph


def test_preflight_includes_read_only_context_pack_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        module = root / 'teaagent' / 'runner.py'
        module.parent.mkdir(parents=True)
        module.write_text('def run():\n    pass\n', encoding='utf-8')
        task = 'review teaagent/runner.py audit chain regressions in tests'
        MemoryCatalog(root).add(task, tags=('runner',))

        output = io.StringIO()
        with redirect_stdout(output):
            code = main(
                [
                    'agent',
                    'preflight',
                    'gpt',
                    task,
                    '--root',
                    tmp,
                ]
            )
        payload = json.loads(output.getvalue())

        assert code == 0
        context_pack = payload['context_pack']
        assert context_pack['read_only'] is True
        paths = [entry['path'] for entry in context_pack['candidate_files']]
        assert 'teaagent/runner.py' in paths
        assert any(entry['exists'] for entry in context_pack['candidate_files'])
        assert len(context_pack['memories']) >= 1
        assert context_pack['graph_rag']['status'] in {'indexed', 'not_indexed'}


def test_preflight_graph_rag_includes_hybrid_hits_when_indexed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        doc = root / 'teaagent' / 'runner.py'
        doc.parent.mkdir(parents=True)
        doc.write_text('runner audit chain regressions in tests', encoding='utf-8')
        task = 'review teaagent/runner.py audit chain regressions in tests'
        LocalHybridSearchBackend().index(
            root=root, args={'include': 'teaagent/**', 'collection': 'default'}
        )

        output = io.StringIO()
        with redirect_stdout(output):
            code = main(['agent', 'preflight', 'gpt', task, '--root', tmp])
        payload = json.loads(output.getvalue())

        assert code == 0
        graph = payload['context_pack']['graph_rag']
        assert graph['status'] == 'indexed'
        assert graph['reason'] == 'hybrid_search_read'
        assert len(graph['hits']) >= 1
        assert 'hybrid' in graph['sources']


def test_preflight_graph_rag_includes_knowledge_hits_when_marker_exists() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        doc = root / 'docs' / 'runner.md'
        doc.parent.mkdir(parents=True)
        doc.write_text('runner audit chain regressions in tests', encoding='utf-8')
        task = 'review runner audit chain regressions in tests'
        LocalHybridSearchBackend().index(
            root=root, args={'include': 'docs/**', 'collection': 'knowledge'}
        )
        (root / '.teaagent').mkdir(exist_ok=True)
        (root / '.teaagent' / 'knowledge').write_text(
            json.dumps({'collection': 'knowledge'}), encoding='utf-8'
        )

        output = io.StringIO()
        with redirect_stdout(output):
            code = main(['agent', 'preflight', 'gpt', task, '--root', tmp])
        payload = json.loads(output.getvalue())

        assert code == 0
        graph = payload['context_pack']['graph_rag']
        assert graph['status'] == 'indexed'
        assert len(graph['sources']['knowledge']['hits']) >= 1


def test_preflight_graph_rag_includes_graphqlite_hits_when_db_exists() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        task = 'runner audit chain regressions in tests'
        (root / '.teaagent').mkdir()
        db_path = root / '.teaagent' / 'graphqlite.db'
        db_path.write_text('', encoding='utf-8')

        class RecordingGraph(FakeGraphQLiteGraph):
            def query(self, cypher: str):
                self.queries.append(cypher)
                return [
                    {
                        'doc_id': 'doc-runner',
                        'text': 'runner audit chain regressions in tests',
                        'source': 'graph',
                    }
                ]

        store = GraphQLiteGraphStore(
            GraphQLiteConfig(database=str(db_path)),
            graph_factory=RecordingGraph,
        )

        output = io.StringIO()
        with (
            patch('teaagent.graphqlite_store.GraphQLiteGraphStore', return_value=store),
            redirect_stdout(output),
        ):
            code = main(['agent', 'preflight', 'gpt', task, '--root', tmp])
        payload = json.loads(output.getvalue())

        assert code == 0
        graph = payload['context_pack']['graph_rag']
        assert graph['status'] == 'indexed'
        assert graph['reason'] == 'graphqlite_read'
        assert len(graph['sources']['graphqlite']['hits']) >= 1


def test_read_only_run_still_blocks_writes_with_context_pack_available() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'README.md').write_text('hello', encoding='utf-8')
        adapter = FakeAdapter(
            [
                '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"out.md","content":"x"},"call_id":"w1"}'
            ]
        )
        output = io.StringIO()
        with (
            patch('teaagent.cli.create_llm_adapter', return_value=adapter),
            redirect_stdout(output),
        ):
            code = main(
                [
                    'agent',
                    'run',
                    'gpt',
                    'Plan only',
                    '--root',
                    tmp,
                    '--permission-mode',
                    'read-only',
                ]
            )
        payload = json.loads(output.getvalue())
        assert code != 0 or payload['status'] != 'completed'
        assert not (root / 'out.md').exists()
