from __future__ import annotations

import json
import math
import sqlite3
import time
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Callable, Protocol

from teaagent.rag import tokenize


class HybridSearchBackend(Protocol):
    def index(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]: ...

    def search(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class SearchHit:
    path: str
    score: float
    lexical_score: float
    vector_score: float
    snippet: str


_BACKENDS: dict[str, HybridSearchBackend] = {}


def register_hybrid_backend(name: str, backend: HybridSearchBackend) -> None:
    if not name.strip():
        raise ValueError('backend name must be non-empty')
    _BACKENDS[name] = backend


def get_hybrid_backend(name: str) -> HybridSearchBackend:
    backend = _BACKENDS.get(name)
    if backend is None:
        raise ValueError(f"unknown hybrid backend '{name}'")
    return backend


def _embed_text(text: str, *, dimensions: int = 256) -> list[float]:
    vec = [0.0] * dimensions
    for token in tokenize(text):
        idx = hash(token) % dimensions
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 0.0:
        return vec
    return [v / norm for v in vec]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))


def _rrf(rank: int, *, k: int = 60) -> float:
    return 1.0 / (k + rank)


class LocalHybridSearchBackend:
    def __init__(self, *, db_name: str = 'hybrid_search.sqlite3') -> None:
        self.db_name = db_name

    def index(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        include = str(args.get('include', '**/*'))
        collection = str(args.get('collection', 'default'))
        clear = bool(args.get('clear', False))
        is_ignored = _read_ignore_matcher(root)

        db_path = _db_path(root, self.db_name)
        with sqlite3.connect(str(db_path)) as conn:
            _ensure_schema(conn)
            if clear:
                conn.execute(
                    'DELETE FROM documents WHERE collection = ?', (collection,)
                )
            indexed = 0
            skipped = 0
            for file_path in sorted(root.rglob('*')):
                if not file_path.is_file() or file_path.is_symlink():
                    continue
                rel = file_path.relative_to(root).as_posix()
                if (
                    rel.startswith('.git/')
                    or is_ignored(rel)
                    or not fnmatch(rel, include)
                ):
                    continue
                try:
                    text = file_path.read_text(encoding='utf-8')
                except UnicodeDecodeError:
                    skipped += 1
                    continue
                vec = _embed_text(text)
                now = int(time.time())
                conn.execute(
                    'DELETE FROM documents WHERE path = ? AND collection = ?',
                    (rel, collection),
                )
                conn.execute(
                    'INSERT INTO documents(path, collection, text, vec, updated_at) VALUES (?, ?, ?, ?, ?)',
                    (rel, collection, text, json.dumps(vec), now),
                )
                indexed += 1
            conn.commit()
        return {
            'backend': 'local',
            'collection': collection,
            'indexed': indexed,
            'skipped': skipped,
            'include': include,
            'database': str(db_path),
        }

    def search(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args['query'])
        limit = int(args.get('limit', 5))
        collection = str(args.get('collection', 'default'))
        db_path = _db_path(root, self.db_name)
        with sqlite3.connect(str(db_path)) as conn:
            _ensure_schema(conn)
            query_vec = _embed_text(query)

            lex_rows = conn.execute(
                'SELECT documents.path, '
                'snippet(documents_fts, 1, "[", "]", " ... ", 16), '
                'bm25(documents_fts) as bm '
                'FROM documents_fts JOIN documents ON documents_fts.rowid = documents.id '
                'WHERE documents_fts MATCH ? AND documents.collection = ? '
                'ORDER BY bm LIMIT ?',
                (query, collection, max(limit * 5, 20)),
            ).fetchall()
            vec_rows = conn.execute(
                'SELECT path, text, vec FROM documents WHERE collection = ?',
                (collection,),
            ).fetchall()

        lex_ranked: dict[str, tuple[int, float, str]] = {}
        for rank, row in enumerate(lex_rows, start=1):
            path = str(row[0])
            snippet = str(row[1] or '')
            bm25_score = float(row[2])
            lex_ranked[path] = (rank, -bm25_score, snippet)

        vec_scored: list[tuple[str, float, str]] = []
        for path, text, vec_json in vec_rows:
            try:
                vec = json.loads(str(vec_json))
            except json.JSONDecodeError:
                continue
            score = _dot(query_vec, [float(v) for v in vec])
            snippet = _snippet_from_text(str(text), query)
            vec_scored.append((str(path), score, snippet))
        vec_scored.sort(key=lambda x: x[1], reverse=True)

        vec_ranked: dict[str, tuple[int, float, str]] = {}
        for rank, (path, score, snippet) in enumerate(vec_scored, start=1):
            vec_ranked[path] = (rank, score, snippet)

        fused: list[SearchHit] = []
        all_paths = set(lex_ranked) | set(vec_ranked)
        for path in all_paths:
            lex_rank, lex_score, lex_snippet = lex_ranked.get(path, (10_000, 0.0, ''))
            vec_rank, vec_score, vec_snippet = vec_ranked.get(path, (10_000, 0.0, ''))
            score = _rrf(lex_rank) + _rrf(vec_rank)
            fused.append(
                SearchHit(
                    path=path,
                    score=score,
                    lexical_score=lex_score,
                    vector_score=vec_score,
                    snippet=lex_snippet or vec_snippet,
                )
            )

        fused.sort(key=lambda h: h.score, reverse=True)
        hits = fused[:limit]
        return {
            'backend': 'local',
            'collection': collection,
            'query': query,
            'hits': [
                {
                    'path': hit.path,
                    'score': hit.score,
                    'lexical_score': hit.lexical_score,
                    'vector_score': hit.vector_score,
                    'snippet': hit.snippet,
                }
                for hit in hits
            ],
        }


def _snippet_from_text(text: str, query: str, *, max_chars: int = 200) -> str:
    lower = text.lower()
    needle = query.lower().strip()
    if not needle:
        return text[:max_chars]
    idx = lower.find(needle)
    if idx < 0:
        return text[:max_chars]
    start = max(0, idx - 40)
    end = min(len(text), idx + len(needle) + 120)
    return text[start:end]


def _db_path(root: Path, name: str) -> Path:
    state_dir = root / '.teaagent'
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / name


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        'CREATE TABLE IF NOT EXISTS documents ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'path TEXT NOT NULL, '
        'collection TEXT NOT NULL, '
        'text TEXT NOT NULL, '
        'vec TEXT NOT NULL, '
        'updated_at INTEGER NOT NULL, '
        'UNIQUE(path, collection)'
        ')'
    )
    conn.execute(
        'CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(path, text, content="documents", content_rowid="id")'
    )
    conn.execute(
        'CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN '
        'INSERT INTO documents_fts(rowid, path, text) VALUES (new.id, new.path, new.text); END'
    )
    conn.execute(
        'CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN '
        'INSERT INTO documents_fts(documents_fts, rowid, path, text) VALUES ("delete", old.id, old.path, old.text); END'
    )
    conn.execute(
        'CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN '
        'INSERT INTO documents_fts(documents_fts, rowid, path, text) VALUES ("delete", old.id, old.path, old.text); '
        'INSERT INTO documents_fts(rowid, path, text) VALUES (new.id, new.path, new.text); END'
    )


def _read_ignore_matcher(root: Path) -> Callable[[str], bool]:
    patterns: list[str] = []
    for name in ('.gitignore', '.agignore'):
        path = root / name
        if path.exists():
            for line in path.read_text(encoding='utf-8').splitlines():
                item = line.strip()
                if item and not item.startswith('#'):
                    patterns.append(item)

    def is_ignored(rel: str) -> bool:
        return any(
            fnmatch(rel, pat) or fnmatch(Path(rel).name, pat) for pat in patterns
        )

    return is_ignored


register_hybrid_backend('local', LocalHybridSearchBackend())
