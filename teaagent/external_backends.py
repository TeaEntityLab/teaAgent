from __future__ import annotations

import contextlib
import json
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol

from teaagent.backend_registry import get_default_backend_registry as _get_registry
from teaagent.hybrid_search import get_hybrid_backend
from teaagent.mcp_client import MCPHTTPClient


@dataclass
class BackendConfig:
    """Configuration for backend adapters."""

    root: Path
    timeout: int = 30
    max_retries: int = 3
    additional_config: dict[str, Any] | None = None


class BackendAdapter(ABC):
    """Base class for backend adapters with consistent interface."""

    def __init__(self, config: BackendConfig):
        self._config = config
        self._initialized = False

    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def shutdown(self) -> None: ...

    @abstractmethod
    def check_health(self) -> tuple[bool, str]: ...

    def is_initialized(self) -> bool:
        return self._initialized

    def get_config(self) -> BackendConfig:
        return self._config


class BackendError(Exception):
    """Base class for backend errors."""

    def __init__(
        self,
        message: str,
        backend_name: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self._backend_name = backend_name
        self._details = details or {}

    @property
    def backend_name(self) -> str:
        return self._backend_name

    @property
    def details(self) -> dict[str, Any]:
        return self._details


class BackendInitializationError(BackendError):
    pass


class BackendExecutionError(BackendError):
    pass


class BackendHealthCheckError(BackendError):
    pass


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


def register_knowledge_backend(name: str, backend: KnowledgeSearchBackend) -> None:
    _get_registry().register_knowledge_backend(name, backend)


def get_knowledge_backend(name: str) -> KnowledgeSearchBackend:
    return _get_registry().get_knowledge_backend(name)


def register_code_parse_backend(name: str, backend: CodeParseBackend) -> None:
    _get_registry().register_code_parse_backend(name, backend)


def get_code_parse_backend(name: str) -> CodeParseBackend:
    return _get_registry().get_code_parse_backend(name)


class BackendAdapterValidator:
    """Validator for backend adapter protocol compliance."""

    @staticmethod
    def validate_knowledge_backend(
        backend: Any,
    ) -> tuple[bool, list[str]]:
        errors = []
        for method in ('health', 'index', 'search', 'get'):
            if not hasattr(backend, method):
                errors.append(f'Missing required method: {method}')
        return (len(errors) == 0, errors)

    @staticmethod
    def validate_code_parse_backend(
        backend: Any,
    ) -> tuple[bool, list[str]]:
        errors = []
        for method in ('health', 'overview', 'symbols', 'definition', 'references'):
            if not hasattr(backend, method):
                errors.append(f'Missing required method: {method}')
        return (len(errors) == 0, errors)


class BackendAdapterFactory:
    """Factory for creating backend adapters."""

    @staticmethod
    def create_knowledge_backend(
        backend_type: str,
        config: BackendConfig,
    ) -> KnowledgeSearchBackend:
        if backend_type == 'local':
            return LocalKnowledgeAdapter(config=config)
        raise ValueError(f"Unknown knowledge backend type: '{backend_type}'")

    @staticmethod
    def create_code_parse_backend(
        backend_type: str,
        config: BackendConfig,
    ) -> CodeParseBackend:
        if backend_type == 'cx_cli':
            return CxCliAdapter()
        raise ValueError(f"Unknown code parse backend type: '{backend_type}'")


class BackendAdapterRegistry:
    """Registry for backend adapters with validation and lifecycle management."""

    def __init__(self, validate: bool = True):
        self._knowledge_backends: dict[str, KnowledgeSearchBackend] = {}
        self._code_parse_backends: dict[str, CodeParseBackend] = {}
        self._validate = validate
        self._validator = BackendAdapterValidator()

    def register_knowledge_backend(
        self,
        name: str,
        backend: KnowledgeSearchBackend,
    ) -> None:
        if not name.strip():
            raise ValueError('backend name must be non-empty')
        if self._validate:
            valid, errors = self._validator.validate_knowledge_backend(backend)
            if not valid:
                raise ValueError(f"Validation failed for '{name}': {', '.join(errors)}")
        self._knowledge_backends[name] = backend

    def register_code_parse_backend(
        self,
        name: str,
        backend: CodeParseBackend,
    ) -> None:
        if not name.strip():
            raise ValueError('backend name must be non-empty')
        if self._validate:
            valid, errors = self._validator.validate_code_parse_backend(backend)
            if not valid:
                raise ValueError(f"Validation failed for '{name}': {', '.join(errors)}")
        self._code_parse_backends[name] = backend

    def get_knowledge_backend(self, name: str) -> KnowledgeSearchBackend:
        backend = self._knowledge_backends.get(name)
        if backend is None:
            raise ValueError(f"unknown knowledge backend '{name}'")
        return backend

    def get_code_parse_backend(self, name: str) -> CodeParseBackend:
        backend = self._code_parse_backends.get(name)
        if backend is None:
            raise ValueError(f"unknown code parse backend '{name}'")
        return backend

    def initialize_all(self) -> None:
        for backend in list(self._knowledge_backends.values()):
            if hasattr(backend, 'initialize'):
                backend.initialize()  # type: ignore[union-attr]
        for backend in list(self._code_parse_backends.values()):  # type: ignore[assignment]
            if hasattr(backend, 'initialize'):
                backend.initialize()  # type: ignore[union-attr]

    def shutdown_all(self) -> None:
        for backend in list(self._knowledge_backends.values()):
            if hasattr(backend, 'shutdown'):
                backend.shutdown()  # type: ignore[union-attr]
        for backend in list(self._code_parse_backends.values()):  # type: ignore[assignment]
            if hasattr(backend, 'shutdown'):
                backend.shutdown()  # type: ignore[union-attr]

    def health_check_all(self) -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}
        for name, backend in self._knowledge_backends.items():
            if hasattr(backend, 'check_health'):
                try:
                    healthy, msg = backend.check_health()  # type: ignore[union-attr]
                    results[f'knowledge/{name}'] = {'healthy': healthy, 'message': msg}
                except (ConnectionError, TimeoutError, OSError) as exc:
                    results[f'knowledge/{name}'] = {
                        'healthy': False,
                        'message': str(exc),
                    }
        for name, backend in self._code_parse_backends.items():  # type: ignore[assignment]
            if hasattr(backend, 'check_health'):
                try:
                    healthy, msg = backend.check_health()  # type: ignore[union-attr]
                    results[f'codeparse/{name}'] = {'healthy': healthy, 'message': msg}
                except (ConnectionError, TimeoutError, OSError) as exc:
                    results[f'codeparse/{name}'] = {
                        'healthy': False,
                        'message': str(exc),
                    }
        return results

    def list_knowledge_backends(self) -> list[str]:
        return list(self._knowledge_backends.keys())

    def list_code_parse_backends(self) -> list[str]:
        return list(self._code_parse_backends.keys())


_default_registry = BackendAdapterRegistry(validate=False)


def get_default_registry() -> BackendAdapterRegistry:
    return _default_registry


@dataclass(frozen=True)
class FallbackKnowledgeBackend:
    primary: str
    fallback: str = 'local'

    def health(self, *, root: Path) -> dict[str, Any]:
        healthy = []
        for name in (self.primary, self.fallback):
            try:
                healthy.append(get_knowledge_backend(name).health(root=root))
            except (ConnectionError, TimeoutError, OSError, ImportError) as exc:
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


@dataclass
class LocalKnowledgeAdapter(BackendAdapter):
    """Local knowledge backend adapter with BackendAdapter base class."""

    config: BackendConfig
    hybrid_backend_name: str = 'local'

    def __post_init__(self) -> None:
        BackendAdapter.__init__(self, self.config)

    def initialize(self) -> None:
        self._initialized = True

    def shutdown(self) -> None:
        self._initialized = False

    def check_health(self) -> tuple[bool, str]:
        return (True, 'Local backend is healthy')

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


@dataclass
class QmdMcpAdapter(BackendAdapter):
    """QMD MCP backend adapter with BackendAdapter base class."""

    endpoint: str
    config: BackendConfig
    auth_token: Optional[str] = None

    def __post_init__(self) -> None:
        BackendAdapter.__init__(self, self.config)

    def initialize(self) -> None:
        self._initialized = True

    def shutdown(self) -> None:
        self._initialized = False

    def check_health(self) -> tuple[bool, str]:
        try:
            with self._client() as client:
                client.initialize()
                status = client.call_tool('status', {})
            return (True, f'QMD MCP backend is healthy: {status}')
        except Exception as exc:
            return (False, f'QMD MCP backend health check failed: {exc}')

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
    timeout: int = 30

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
        try:
            result = subprocess.run(
                cmd,
                cwd=str(root),
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            raise BackendExecutionError(
                f'qmd command timed out after {self.timeout}s',
                backend_name='qmd_cli',
                details={
                    'reason': 'timeout',
                    'timeout_seconds': self.timeout,
                    'command': cmd,
                },
            ) from None
        if result.returncode != 0:
            raise BackendExecutionError(
                result.stderr.strip() or 'qmd command failed',
                backend_name='qmd_cli',
                details={
                    'reason': 'non_zero_exit',
                    'exit_code': result.returncode,
                    'stderr': result.stderr.strip(),
                },
            )
        return result.stdout.strip()

    def _parse(self, text: str) -> Any:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {'raw': text}


@dataclass(frozen=True)
class CxCliAdapter:
    binary: str = 'cx'
    timeout: int = 30

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
        try:
            result = subprocess.run(
                cmd,
                cwd=str(root),
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            raise BackendExecutionError(
                f'cx command timed out after {self.timeout}s',
                backend_name='cx_cli',
                details={
                    'reason': 'timeout',
                    'timeout_seconds': self.timeout,
                    'command': cmd,
                },
            ) from None
        if result.returncode != 0:
            raise BackendExecutionError(
                result.stderr.strip() or 'cx command failed',
                backend_name='cx_cli',
                details={
                    'reason': 'non_zero_exit',
                    'exit_code': result.returncode,
                    'stderr': result.stderr.strip(),
                },
            )
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
_default_local = LocalKnowledgeAdapter(config=BackendConfig(root=Path()))
register_knowledge_backend('local', _default_local)
register_code_parse_backend('cx_cli', CxCliAdapter())
_default_registry.register_knowledge_backend('local', _default_local)
_default_registry.register_code_parse_backend('cx_cli', CxCliAdapter())
