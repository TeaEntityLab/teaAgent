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
from teaagent.okf import OKF_VERSION, get_okf_concept, validate_okf_bundle
from teaagent.path_safety import resolve_contained_path
from teaagent.rag import tokenize
from teaagent.storage import atomic_write_text
from teaagent.types import JsonMapping


@dataclass
class BackendConfig:
    """Configuration for backend adapters."""

    root: Path
    timeout: int = 30
    max_retries: int = 3
    additional_config: JsonMapping | None = None


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
        details: JsonMapping | None = None,
    ):
        super().__init__(message)
        self._backend_name = backend_name
        self._details = details or {}

    @property
    def backend_name(self) -> str:
        return self._backend_name

    @property
    def details(self) -> JsonMapping:
        return self._details


class BackendInitializationError(BackendError):
    pass


class BackendExecutionError(BackendError):
    pass


class BackendHealthCheckError(BackendError):
    pass


class KnowledgeSearchBackend(Protocol):
    def health(self, *, root: Path) -> JsonMapping: ...

    def index(self, *, root: Path, args: JsonMapping) -> JsonMapping: ...

    def search(self, *, root: Path, args: JsonMapping) -> JsonMapping: ...

    def get(self, *, root: Path, args: JsonMapping) -> JsonMapping: ...


class CodeParseBackend(Protocol):
    def health(self, *, root: Path) -> JsonMapping: ...

    def overview(self, *, root: Path, args: JsonMapping) -> JsonMapping: ...

    def symbols(self, *, root: Path, args: JsonMapping) -> JsonMapping: ...

    def definition(self, *, root: Path, args: JsonMapping) -> JsonMapping: ...

    def references(self, *, root: Path, args: JsonMapping) -> JsonMapping: ...


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
        if backend_type == 'okf':
            return OkfKnowledgeAdapter(config=config)
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
        for kb_backend in self._knowledge_backends.values():
            if hasattr(kb_backend, 'initialize'):
                kb_backend.initialize()
        for cp_backend in self._code_parse_backends.values():
            if hasattr(cp_backend, 'initialize'):
                cp_backend.initialize()
        for cp_backend in self._code_parse_backends.values():
            if hasattr(cp_backend, 'shutdown'):
                cp_backend.shutdown()

    def health_check_all(self) -> dict[str, JsonMapping]:
        results: dict[str, JsonMapping] = {}
        for name, backend in self._knowledge_backends.items():
            if hasattr(backend, 'check_health'):
                try:
                    healthy, msg = backend.check_health()
                    results[f'knowledge/{name}'] = {'healthy': healthy, 'message': msg}
                except (ConnectionError, TimeoutError, OSError) as exc:
                    results[f'knowledge/{name}'] = {
                        'healthy': False,
                        'message': str(exc),
                    }
        for name, cp_backend in self._code_parse_backends.items():
            if hasattr(cp_backend, 'check_health'):
                try:
                    healthy, msg = cp_backend.check_health()
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

    def health(self, *, root: Path) -> JsonMapping:
        healthy = []
        for name in (self.primary, self.fallback):
            try:
                healthy.append(get_knowledge_backend(name).health(root=root))
            except (
                ConnectionError,
                TimeoutError,
                OSError,
                ImportError,
                RuntimeError,
                ValueError,
                TypeError,
                AttributeError,
            ) as exc:
                healthy.append({'backend': name, 'ok': False, 'error': str(exc)})
        return {'backends': healthy}

    def index(self, *, root: Path, args: JsonMapping) -> JsonMapping:
        return self._call('index', root=root, args=args)

    def search(self, *, root: Path, args: JsonMapping) -> JsonMapping:
        return self._call('search', root=root, args=args)

    def get(self, *, root: Path, args: JsonMapping) -> JsonMapping:
        return self._call('get', root=root, args=args)

    def _call(self, method: str, *, root: Path, args: JsonMapping) -> JsonMapping:
        primary_backend = get_knowledge_backend(self.primary)
        fallback_backend = get_knowledge_backend(self.fallback)
        try:
            result = getattr(primary_backend, method)(root=root, args=args)
            result.setdefault('backend', self.primary)
            result.setdefault('fallback_used', False)
            return result
        except (
            ConnectionError,
            TimeoutError,
            OSError,
            ImportError,
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
        ) as exc:
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

    def health(self, *, root: Path) -> JsonMapping:
        _ = root
        return {'backend': 'local', 'ok': True}

    def index(self, *, root: Path, args: JsonMapping) -> JsonMapping:
        backend = get_hybrid_backend(self.hybrid_backend_name)
        result = backend.index(root=root, args=args)
        result.setdefault('backend', 'local')
        return result

    def search(self, *, root: Path, args: JsonMapping) -> JsonMapping:
        backend = get_hybrid_backend(self.hybrid_backend_name)
        result = backend.search(root=root, args=args)
        result.setdefault('backend', 'local')
        return result

    def get(self, *, root: Path, args: JsonMapping) -> JsonMapping:
        path = resolve_contained_path(
            root, str(args['path']), must_exist=True, require_file=True
        )
        content = path.read_text(encoding='utf-8')
        return {'backend': 'local', 'path': str(args['path']), 'content': content}


@dataclass
class OkfKnowledgeAdapter(BackendAdapter):
    """OKF v0.1 validation and retrieval over the local hybrid index."""

    config: BackendConfig
    hybrid_backend_name: str = 'local'
    default_bundle: str = 'knowledge'
    default_collection: str = 'knowledge'

    def __post_init__(self) -> None:
        BackendAdapter.__init__(self, self.config)

    def initialize(self) -> None:
        self._initialized = True

    def shutdown(self) -> None:
        self._initialized = False

    def check_health(self) -> tuple[bool, str]:
        report = self.health(root=self.config.root)
        if not report.get('available', False):
            return (True, 'OKF backend is ready; no default bundle is present')
        return (bool(report.get('ok')), str(report))

    def health(self, *, root: Path) -> JsonMapping:
        try:
            bundle_path = resolve_contained_path(root, self.default_bundle)
        except ValueError as exc:
            return {
                'backend': 'okf',
                'ok': False,
                'available': False,
                'version': OKF_VERSION,
                'error': str(exc),
            }
        if not bundle_path.is_dir():
            return {
                'backend': 'okf',
                'ok': True,
                'available': False,
                'version': OKF_VERSION,
            }
        bundle = validate_okf_bundle(root, self.default_bundle)
        return {
            'backend': 'okf',
            'ok': bundle.conformant,
            'available': True,
            'version': OKF_VERSION,
            'validation': bundle.to_dict(),
        }

    def index(self, *, root: Path, args: JsonMapping) -> JsonMapping:
        bundle_arg = str(args.get('bundle') or self.default_bundle)
        collection = str(args.get('collection') or self.default_collection)
        bundle = validate_okf_bundle(root, bundle_arg)
        if not bundle.conformant:
            raise BackendExecutionError(
                'OKF bundle is not conformant and was not indexed',
                backend_name='okf',
                details={'validation': bundle.to_dict()},
            )

        workspace_root = root.resolve()
        relative_bundle = bundle.root.relative_to(workspace_root).as_posix()
        include = f'{relative_bundle}/**' if relative_bundle != '.' else '**/*.md'
        payload = dict(args)
        payload.update({'include': include, 'collection': collection})
        result = get_hybrid_backend(self.hybrid_backend_name).index(
            root=workspace_root, args=payload
        )
        marker = workspace_root / '.teaagent' / 'knowledge'
        atomic_write_text(
            marker,
            json.dumps(
                {
                    'backend': 'okf',
                    'bundle': relative_bundle,
                    'collection': collection,
                    'okf_version': bundle.version or OKF_VERSION,
                },
                sort_keys=True,
            )
            + '\n',
        )
        return {
            'backend': 'okf',
            'bundle': relative_bundle,
            'collection': collection,
            'validation': bundle.to_dict(),
            'index': result,
        }

    def search(self, *, root: Path, args: JsonMapping) -> JsonMapping:
        payload = dict(args)
        original_query = str(args['query'])
        payload['query'] = ' '.join(tokenize(original_query)) or original_query
        payload['collection'] = str(args.get('collection') or self.default_collection)
        result = get_hybrid_backend(self.hybrid_backend_name).search(
            root=root.resolve(), args=payload
        )
        bundle_arg = self._indexed_bundle(root=root, args=args)
        if bundle_arg is not None:
            bundle = validate_okf_bundle(root, bundle_arg)
            if not bundle.conformant:
                raise BackendExecutionError(
                    'indexed OKF bundle is no longer conformant',
                    backend_name='okf',
                    details={'validation': bundle.to_dict()},
                )
            relative_bundle = bundle.root.relative_to(root.resolve())
            concepts = {concept.path: concept for concept in bundle.concepts}
            enriched_hits: list[JsonMapping] = []
            for raw_hit in result.get('hits', []):
                if not isinstance(raw_hit, dict):
                    continue
                hit = dict(raw_hit)
                try:
                    concept_path = (
                        Path(str(hit.get('path', '')))
                        .relative_to(relative_bundle)
                        .as_posix()
                    )
                except ValueError:
                    enriched_hits.append(hit)
                    continue
                concept = concepts.get(concept_path)
                if concept is None:
                    continue
                metadata = dict(concept.metadata)
                extension = metadata.get('teaagent')
                source_path = (
                    extension.get('source_path')
                    if isinstance(extension, dict)
                    else None
                )
                hit.update(
                    {
                        'concept_id': concept.concept_id,
                        'concept_path': str(raw_hit.get('path', '')),
                        'format': 'okf',
                        'metadata': metadata,
                    }
                )
                if isinstance(source_path, str) and source_path.strip():
                    hit['path'] = source_path.strip()
                enriched_hits.append(hit)
            result['hits'] = enriched_hits
            result['bundle'] = relative_bundle.as_posix()
        result['backend'] = 'okf'
        result['query'] = original_query
        return result

    def get(self, *, root: Path, args: JsonMapping) -> JsonMapping:
        bundle_arg = self._indexed_bundle(root=root, args=args) or self.default_bundle
        concept_id = str(args.get('concept_id') or args.get('path') or '')
        bundle, concept = get_okf_concept(root, bundle_arg, concept_id)
        return {
            'backend': 'okf',
            'bundle': bundle.root.relative_to(root.resolve()).as_posix(),
            'version': bundle.version,
            'concept': concept.to_dict(),
            'findings': [finding.to_dict() for finding in bundle.findings],
        }

    def _indexed_bundle(self, *, root: Path, args: JsonMapping) -> str | None:
        requested = args.get('bundle')
        if isinstance(requested, str) and requested.strip():
            return requested.strip()
        marker = root.resolve() / '.teaagent' / 'knowledge'
        if not marker.is_file():
            return None
        try:
            payload = json.loads(marker.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or payload.get('backend') != 'okf':
            return None
        bundle = payload.get('bundle')
        return bundle.strip() if isinstance(bundle, str) and bundle.strip() else None


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
        except (
            ConnectionError,
            TimeoutError,
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
        ) as exc:
            return (False, f'QMD MCP backend health check failed: {exc}')

    def health(self, *, root: Path) -> JsonMapping:
        _ = root
        with self._client() as client:
            client.initialize()
            status = client.call_tool('status', {})
        return {'backend': 'qmd_mcp', 'ok': True, 'status': status}

    def index(self, *, root: Path, args: JsonMapping) -> JsonMapping:
        _ = root
        with self._client() as client:
            client.initialize()
            status = client.call_tool('status', {'collection': args.get('collection')})
        return {
            'backend': 'qmd_mcp',
            'indexed': int(status.get('indexed', 0)) if isinstance(status, dict) else 0,
            'status': status,
        }

    def search(self, *, root: Path, args: JsonMapping) -> JsonMapping:
        _ = root
        query = str(args['query'])
        params = {'q': query, 'n': int(args.get('limit', 5))}
        if 'collection' in args:
            params['collection'] = args['collection']
        with self._client() as client:
            client.initialize()
            result = client.call_tool('query', params)
        return {'backend': 'qmd_mcp', 'query': query, 'result': result}

    def get(self, *, root: Path, args: JsonMapping) -> JsonMapping:
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

    def health(self, *, root: Path) -> JsonMapping:
        out = self._run(root, [self.binary, 'status', '--json'])
        return {'backend': 'qmd_cli', 'ok': True, 'status': self._parse(out)}

    def index(self, *, root: Path, args: JsonMapping) -> JsonMapping:
        _ = args
        out = self._run(root, [self.binary, 'status', '--json'])
        status = self._parse(out)
        return {'backend': 'qmd_cli', 'status': status}

    def search(self, *, root: Path, args: JsonMapping) -> JsonMapping:
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

    def get(self, *, root: Path, args: JsonMapping) -> JsonMapping:
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

    def health(self, *, root: Path) -> JsonMapping:
        out = self._run(root, [self.binary, 'lang', 'list'])
        return {'backend': 'cx_cli', 'ok': True, 'raw': out}

    def overview(self, *, root: Path, args: JsonMapping) -> JsonMapping:
        return {
            'backend': 'cx_cli',
            'raw': self._run(root, [self.binary, 'overview', str(args['path'])]),
        }

    def symbols(self, *, root: Path, args: JsonMapping) -> JsonMapping:
        cmd = [self.binary, 'symbols']
        if args.get('name'):
            cmd.extend(['--name', str(args['name'])])
        if args.get('kind'):
            cmd.extend(['--kind', str(args['kind'])])
        if args.get('file'):
            cmd.extend(['--file', str(args['file'])])
        return {'backend': 'cx_cli', 'raw': self._run(root, cmd)}

    def definition(self, *, root: Path, args: JsonMapping) -> JsonMapping:
        cmd = [self.binary, 'definition', '--name', str(args['name'])]
        if args.get('from'):
            cmd.extend(['--from', str(args['from'])])
        if args.get('kind'):
            cmd.extend(['--kind', str(args['kind'])])
        return {'backend': 'cx_cli', 'raw': self._run(root, cmd)}

    def references(self, *, root: Path, args: JsonMapping) -> JsonMapping:
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

    def health(self, *, root: Path) -> JsonMapping:
        _ = root
        with self._client() as client:
            client.initialize()
            status = client.call_tool('codegraph_status', {})
        return {'backend': 'codegraph_mcp', 'ok': True, 'status': status}

    def overview(self, *, root: Path, args: JsonMapping) -> JsonMapping:
        _ = root
        with self._client() as client:
            client.initialize()
            result = client.call_tool(
                'codegraph_files', {'path': args.get('path', '.'), 'format': 'tree'}
            )
        return {'backend': 'codegraph_mcp', 'result': result}

    def symbols(self, *, root: Path, args: JsonMapping) -> JsonMapping:
        _ = root
        with self._client() as client:
            client.initialize()
            result = client.call_tool(
                'codegraph_search',
                {'query': args.get('name', ''), 'kind': args.get('kind')},
            )
        return {'backend': 'codegraph_mcp', 'result': result}

    def definition(self, *, root: Path, args: JsonMapping) -> JsonMapping:
        _ = root
        with self._client() as client:
            client.initialize()
            result = client.call_tool('codegraph_node', {'id': args['name']})
        return {'backend': 'codegraph_mcp', 'result': result}

    def references(self, *, root: Path, args: JsonMapping) -> JsonMapping:
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
_default_okf = OkfKnowledgeAdapter(config=BackendConfig(root=Path()))
register_knowledge_backend('local', _default_local)
register_knowledge_backend('okf', _default_okf)
register_code_parse_backend('cx_cli', CxCliAdapter())
_default_registry.register_knowledge_backend('local', _default_local)
_default_registry.register_knowledge_backend('okf', _default_okf)
_default_registry.register_code_parse_backend('cx_cli', CxCliAdapter())
