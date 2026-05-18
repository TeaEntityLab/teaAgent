from __future__ import annotations

import contextlib
import json
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol

from teaagent.hybrid_search import get_hybrid_backend
from teaagent.mcp_client import MCPHTTPClient


class KnowledgeSearchBackend(Protocol):
    def health(self, *, root: Path) -> dict[str, Any]: ...

    def index(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]: ...

    def search(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]: ...

    def get(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]: ...


class CodeParseBackend(Protocol):
    def health(self, *, root: Path) -> dict[str, Any]: ...

    def overview(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]: ...

    def symbols(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]: ...

    def definition(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]: ...

    def references(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]: ...


_KNOWLEDGE_BACKENDS: dict[str, KnowledgeSearchBackend] = {}
_CODE_PARSE_BACKENDS: dict[str, CodeParseBackend] = {}


def register_knowledge_backend(name: str, backend: KnowledgeSearchBackend) -> None:
    if not name.strip():
        raise ValueError('backend name must be non-empty')
    _KNOWLEDGE_BACKENDS[name] = backend


def get_knowledge_backend(name: str) -> KnowledgeSearchBackend:
    backend = _KNOWLEDGE_BACKENDS.get(name)
    if backend is None:
        raise ValueError(f"unknown knowledge backend '{name}'")
    return backend


def register_code_parse_backend(name: str, backend: CodeParseBackend) -> None:
    if not name.strip():
        raise ValueError('backend name must be non-empty')
    _CODE_PARSE_BACKENDS[name] = backend


def get_code_parse_backend(name: str) -> CodeParseBackend:
    backend = _CODE_PARSE_BACKENDS.get(name)
    if backend is None:
        raise ValueError(f"unknown code parse backend '{name}'")
    return backend


@dataclass(frozen=True)
class FallbackKnowledgeBackend:
    primary: str
    fallback: str = 'local'

    def health(self, *, root: Path) -> dict[str, Any]:
        healthy = []
        for name in (self.primary, self.fallback):
            try:
                healthy.append(get_knowledge_backend(name).health(root=root))
            except Exception as exc:
                healthy.append({'backend': name, 'ok': False, 'error': str(exc)})
        return {'backends': healthy}

    def index(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        return self._call('index', root=root, args=args)

    def search(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        return self._call('search', root=root, args=args)

    def get(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        return self._call('get', root=root, args=args)

    def _call(self, method: str, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        primary_backend = get_knowledge_backend(self.primary)
        fallback_backend = get_knowledge_backend(self.fallback)
        try:
            result = getattr(primary_backend, method)(root=root, args=args)
            result.setdefault('backend', self.primary)
            result.setdefault('fallback_used', False)
            return result
        except Exception as exc:
            result = getattr(fallback_backend, method)(root=root, args=args)
            result.setdefault('backend', self.fallback)
            result['fallback_used'] = True
            result['primary_error'] = str(exc)
            return result


@dataclass(frozen=True)
class LocalKnowledgeAdapter:
    hybrid_backend_name: str = 'local'

    def health(self, *, root: Path) -> dict[str, Any]:
        _ = root
        return {'backend': 'local', 'ok': True}

    def index(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        backend = get_hybrid_backend(self.hybrid_backend_name)
        result = backend.index(root=root, args=args)
        result.setdefault('backend', 'local')
        return result

    def search(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        backend = get_hybrid_backend(self.hybrid_backend_name)
        result = backend.search(root=root, args=args)
        result.setdefault('backend', 'local')
        return result

    def get(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        path = root / str(args['path'])
        content = path.read_text(encoding='utf-8')
        return {'backend': 'local', 'path': str(args['path']), 'content': content}


@dataclass(frozen=True)
class QmdMcpAdapter:
    endpoint: str
    auth_token: Optional[str] = None

    def health(self, *, root: Path) -> dict[str, Any]:
        _ = root
        with self._client() as client:
            client.initialize()
            status = client.call_tool('status', {})
        return {'backend': 'qmd_mcp', 'ok': True, 'status': status}

    def index(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        _ = root
        with self._client() as client:
            client.initialize()
            status = client.call_tool('status', {'collection': args.get('collection')})
        return {
            'backend': 'qmd_mcp',
            'indexed': int(status.get('indexed', 0)) if isinstance(status, dict) else 0,
            'status': status,
        }

    def search(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        _ = root
        query = str(args['query'])
        params = {'q': query, 'n': int(args.get('limit', 5))}
        if 'collection' in args:
            params['collection'] = args['collection']
        with self._client() as client:
            client.initialize()
            result = client.call_tool('query', params)
        return {'backend': 'qmd_mcp', 'query': query, 'result': result}

    def get(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        _ = root
        target = str(args['target'])
        with self._client() as client:
            client.initialize()
            result = client.call_tool('get', {'target': target})
        return {'backend': 'qmd_mcp', 'target': target, 'result': result}

    @contextlib.contextmanager
    def _client(self) -> Iterator[MCPHTTPClient]:
        client = MCPHTTPClient(self.endpoint, auth_token=self.auth_token)
        try:
            yield client
        finally:
            with contextlib.suppress(Exception):
                client.close()


@dataclass(frozen=True)
class QmdCliAdapter:
    binary: str = 'qmd'

    def health(self, *, root: Path) -> dict[str, Any]:
        out = self._run(root, [self.binary, 'status', '--json'])
        return {'backend': 'qmd_cli', 'ok': True, 'status': self._parse(out)}

    def index(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        _ = args
        out = self._run(root, [self.binary, 'status', '--json'])
        status = self._parse(out)
        return {'backend': 'qmd_cli', 'status': status}

    def search(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        cmd = [
            self.binary,
            'query',
            str(args['query']),
            '--json',
            '-n',
            str(int(args.get('limit', 5))),
        ]
        if args.get('collection'):
            cmd.extend(['-c', str(args['collection'])])
        out = self._run(root, cmd)
        return {
            'backend': 'qmd_cli',
            'query': args['query'],
            'result': self._parse(out),
        }

    def get(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        out = self._run(root, [self.binary, 'get', str(args['target']), '--json'])
        return {
            'backend': 'qmd_cli',
            'target': args['target'],
            'result': self._parse(out),
        }

    def _run(self, root: Path, cmd: list[str]) -> str:
        result = subprocess.run(
            cmd, cwd=str(root), capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or 'qmd command failed')
        return result.stdout.strip()

    def _parse(self, text: str) -> Any:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {'raw': text}


@dataclass(frozen=True)
class CxCliAdapter:
    binary: str = 'cx'

    def health(self, *, root: Path) -> dict[str, Any]:
        out = self._run(root, [self.binary, 'lang', 'list'])
        return {'backend': 'cx_cli', 'ok': True, 'raw': out}

    def overview(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        return {
            'backend': 'cx_cli',
            'raw': self._run(root, [self.binary, 'overview', str(args['path'])]),
        }

    def symbols(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        cmd = [self.binary, 'symbols']
        if args.get('name'):
            cmd.extend(['--name', str(args['name'])])
        if args.get('kind'):
            cmd.extend(['--kind', str(args['kind'])])
        if args.get('file'):
            cmd.extend(['--file', str(args['file'])])
        return {'backend': 'cx_cli', 'raw': self._run(root, cmd)}

    def definition(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        cmd = [self.binary, 'definition', '--name', str(args['name'])]
        if args.get('from'):
            cmd.extend(['--from', str(args['from'])])
        if args.get('kind'):
            cmd.extend(['--kind', str(args['kind'])])
        return {'backend': 'cx_cli', 'raw': self._run(root, cmd)}

    def references(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        cmd = [self.binary, 'references', '--name', str(args['name'])]
        if args.get('file'):
            cmd.extend(['--file', str(args['file'])])
        return {'backend': 'cx_cli', 'raw': self._run(root, cmd)}

    def _run(self, root: Path, cmd: list[str]) -> str:
        result = subprocess.run(
            cmd, cwd=str(root), capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or 'cx command failed')
        return result.stdout.strip()


@dataclass(frozen=True)
class CodegraphMcpAdapter:
    endpoint: str
    auth_token: Optional[str] = None

    def health(self, *, root: Path) -> dict[str, Any]:
        _ = root
        with self._client() as client:
            client.initialize()
            status = client.call_tool('codegraph_status', {})
        return {'backend': 'codegraph_mcp', 'ok': True, 'status': status}

    def overview(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        _ = root
        with self._client() as client:
            client.initialize()
            result = client.call_tool(
                'codegraph_files', {'path': args.get('path', '.'), 'format': 'tree'}
            )
        return {'backend': 'codegraph_mcp', 'result': result}

    def symbols(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        _ = root
        with self._client() as client:
            client.initialize()
            result = client.call_tool(
                'codegraph_search',
                {'query': args.get('name', ''), 'kind': args.get('kind')},
            )
        return {'backend': 'codegraph_mcp', 'result': result}

    def definition(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        _ = root
        with self._client() as client:
            client.initialize()
            result = client.call_tool('codegraph_node', {'id': args['name']})
        return {'backend': 'codegraph_mcp', 'result': result}

    def references(self, *, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        _ = root
        with self._client() as client:
            client.initialize()
            result = client.call_tool('codegraph_callers', {'symbol': args['name']})
        return {'backend': 'codegraph_mcp', 'result': result}

    @contextlib.contextmanager
    def _client(self) -> Iterator[MCPHTTPClient]:
        client = MCPHTTPClient(self.endpoint, auth_token=self.auth_token)
        try:
            yield client
        finally:
            with contextlib.suppress(Exception):
                client.close()


# Default registrations
register_knowledge_backend('local', LocalKnowledgeAdapter())
register_code_parse_backend('cx_cli', CxCliAdapter())
