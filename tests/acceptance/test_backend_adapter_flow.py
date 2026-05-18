"""AC-NEW-25: Backend adapter and fallback routing flow.

As a platform engineer, I want pluggable knowledge/code backends with safe
fallback behavior so external tools (qmd/cx/codegraph-like) can be integrated
without hard-coding one provider.

Acceptance criteria:
- workspace_knowledge_search supports backend=auto and falls back on primary failure.
- workspace_code_parse routes actions to a registered CodeParseBackend.
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
