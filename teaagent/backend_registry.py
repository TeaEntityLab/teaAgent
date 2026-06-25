"""Lifecycle-aware backend registry (ADR-004, ADR-008).

Replaces the module-level global dicts in ``external_backends.py`` with a
class-based registry that supports ``initialize()``, ``shutdown()``,
``check_health()``, and ``is_initialized()`` lifecycle methods.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BackendRegistry:
    """Lifecycle-aware registry for knowledge search and code parse backends."""

    def __init__(self, *, validate: bool = True) -> None:
        self._knowledge_backends: dict[str, Any] = {}
        self._code_parse_backends: dict[str, Any] = {}
        self._validate = validate
        self._initialized = False

    def initialize(self) -> None:
        for backend in list(self._knowledge_backends.values()):
            if hasattr(backend, 'initialize'):
                try:
                    backend.initialize()
                except (OSError, RuntimeError, ConnectionError) as exc:
                    logger.exception('Failed to initialize knowledge backend: %s', exc)
        for backend in list(self._code_parse_backends.values()):
            if hasattr(backend, 'initialize'):
                try:
                    backend.initialize()
                except (OSError, RuntimeError, ConnectionError) as exc:
                    logger.exception('Failed to initialize code parse backend: %s', exc)
        self._initialized = True

    def shutdown(self) -> None:
        for backend in list(self._knowledge_backends.values()):
            if hasattr(backend, 'shutdown'):
                try:
                    backend.shutdown()
                except (OSError, RuntimeError, ConnectionError) as exc:
                    logger.exception('Failed to shutdown knowledge backend: %s', exc)
        for backend in list(self._code_parse_backends.values()):
            if hasattr(backend, 'shutdown'):
                try:
                    backend.shutdown()
                except (OSError, RuntimeError, ConnectionError) as exc:
                    logger.exception('Failed to shutdown code parse backend: %s', exc)
        self._initialized = False

    def check_health(self) -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}
        for name, backend in self._knowledge_backends.items():
            results[f'knowledge/{name}'] = self._health_of(backend)
        for name, backend in self._code_parse_backends.items():
            results[f'codeparse/{name}'] = self._health_of(backend)
        return results

    def is_initialized(self) -> bool:
        return self._initialized

    def register_knowledge_backend(self, name: str, backend: Any) -> None:
        if not name.strip():
            raise ValueError('backend name must be non-empty')
        self._knowledge_backends[name] = backend

    def get_knowledge_backend(self, name: str) -> Any:
        backend = self._knowledge_backends.get(name)
        if backend is None:
            raise ValueError(f"unknown knowledge backend '{name}'")
        return backend

    def list_knowledge_backends(self) -> list[str]:
        return list(self._knowledge_backends.keys())

    def register_code_parse_backend(self, name: str, backend: Any) -> None:
        if not name.strip():
            raise ValueError('backend name must be non-empty')
        self._code_parse_backends[name] = backend

    def get_code_parse_backend(self, name: str) -> Any:
        backend = self._code_parse_backends.get(name)
        if backend is None:
            raise ValueError(f"unknown code parse backend '{name}'")
        return backend

    def list_code_parse_backends(self) -> list[str]:
        return list(self._code_parse_backends.keys())

    @staticmethod
    def _health_of(backend: Any) -> dict[str, Any]:
        if hasattr(backend, 'check_health'):
            try:
                healthy, msg = backend.check_health()
                return {'healthy': healthy, 'message': msg}
            except (
                OSError,
                RuntimeError,
                ValueError,
                TypeError,
                AttributeError,
            ) as exc:
                return {'healthy': False, 'message': str(exc)}
        if hasattr(backend, 'health'):
            try:
                result = backend.health(root=Path('.'))
                ok = result.get('ok', True) if isinstance(result, dict) else True
                return {'healthy': bool(ok), 'message': str(result)}
            except (
                OSError,
                RuntimeError,
                ValueError,
                TypeError,
                AttributeError,
            ) as exc:
                return {'healthy': False, 'message': str(exc)}
        return {'healthy': True, 'message': 'no health check available'}


_default_registry = BackendRegistry(validate=False)


def get_default_backend_registry() -> BackendRegistry:
    return _default_registry


__all__ = [
    'BackendRegistry',
    'get_default_backend_registry',
]
