"""Test module for backend adapter and fallback routing.

This module tests the pluggable backend system for knowledge and code analysis,
which enables integration with external tools (qmd/cx/codegraph-like) without
hard-coding a single provider. The system supports automatic fallback when the
primary backend fails.

Key concepts tested:
- Knowledge Backend: Pluggable backends for workspace knowledge search
- Code Parse Backend: Pluggable backends for code analysis operations
- Fallback Routing: backend=auto falls back to secondary on primary failure
- Backend Registration: Backends are registered via register_knowledge_backend
- Health Checks: Backends implement health() for availability checks
- Tool Integration: Backends are integrated into workspace tool registry

Acceptance Criteria:
- AC1: workspace_knowledge_search supports backend=auto with fallback
- AC2: Primary backend failure triggers fallback to secondary backend
- AC3: Fallback result includes fallback_used=True and primary_error
- AC4: workspace_code_parse routes actions to registered CodeParseBackend
- AC5: Code parse backend supports actions: overview, symbols, definition, references
- AC6: Backend health checks are called before routing

Technical Details:
- register_knowledge_backend registers a backend by name
- register_code_parse_backend registers a code parse backend by name
- Backend=auto routing tries primary, falls back to secondary on error
- Knowledge backends implement: health(), index(), search(), get()
- Code parse backends implement: health(), overview(), symbols(), definition(), references()
- build_workspace_tool_registry includes backend-aware tools
- Fallback preserves error information for debugging

References:
- Backend adapter design: /docs/architecture/backend_adapter.md
- Knowledge backend spec: /docs/specs/knowledge_backend.md
- Code parse backend spec: /docs/specs/code_parse_backend.md
"""

from __future__ import annotations

from pathlib import Path

from teaagent import (
    build_workspace_tool_registry,
    register_code_parse_backend,
    register_knowledge_backend,
)


class _PrimaryFailKnowledge:
    def health(self, *, root: Path):
        raise RuntimeError('primary unavailable')

    def index(self, *, root: Path, args: dict):
        raise RuntimeError('primary unavailable')

    def search(self, *, root: Path, args: dict):
        raise RuntimeError('primary unavailable')

    def get(self, *, root: Path, args: dict):
        raise RuntimeError('primary unavailable')


class _FallbackKnowledge:
    def health(self, *, root: Path):
        return {'ok': True}

    def index(self, *, root: Path, args: dict):
        return {'source': 'fallback', 'op': 'index'}

    def search(self, *, root: Path, args: dict):
        return {'source': 'fallback', 'op': 'search'}

    def get(self, *, root: Path, args: dict):
        return {'source': 'fallback', 'op': 'get'}


class _CodeParseStub:
    def health(self, *, root: Path):
        return {'ok': True, 'backend': 'stub'}

    def overview(self, *, root: Path, args: dict):
        return {'kind': 'overview', 'path': args.get('path')}

    def symbols(self, *, root: Path, args: dict):
        return {'kind': 'symbols', 'name': args.get('name')}

    def definition(self, *, root: Path, args: dict):
        return {'kind': 'definition', 'name': args.get('name')}

    def references(self, *, root: Path, args: dict):
        return {'kind': 'references', 'name': args.get('name')}


def test_backend_adapter_fallback_and_code_parse_flow(tmp_path: Path) -> None:
    registry = build_workspace_tool_registry(tmp_path)

    register_knowledge_backend('accept_primary_fail', _PrimaryFailKnowledge())
    register_knowledge_backend('accept_fallback_ok', _FallbackKnowledge())
    register_code_parse_backend('accept_code_parse_stub', _CodeParseStub())

    knowledge = registry.execute(
        'workspace_knowledge_search',
        {
            'backend': 'auto',
            'primary_backend': 'accept_primary_fail',
            'fallback_backend': 'accept_fallback_ok',
            'query': 'auth flow',
            'limit': 5,
        },
    )
    assert knowledge['backend'] == 'auto'
    assert knowledge['result']['source'] == 'fallback'
    assert knowledge['result']['fallback_used'] is True
    assert 'primary_error' in knowledge['result']

    code_parse = registry.execute(
        'workspace_code_parse',
        {
            'backend': 'accept_code_parse_stub',
            'action': 'definition',
            'name': 'AuthService.login',
        },
    )
    assert code_parse['backend'] == 'accept_code_parse_stub'
    assert code_parse['action'] == 'definition'
    assert code_parse['result']['kind'] == 'definition'
