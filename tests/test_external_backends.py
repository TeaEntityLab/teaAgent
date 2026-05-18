from __future__ import annotations

from pathlib import Path

from teaagent.external_backends import (
    FallbackKnowledgeBackend,
    get_code_parse_backend,
    get_knowledge_backend,
    register_code_parse_backend,
    register_knowledge_backend,
)


class _OkKnowledge:
    def health(self, *, root: Path):
        return {'ok': True}

    def index(self, *, root: Path, args: dict):
        return {'ok': True, 'action': 'index'}

    def search(self, *, root: Path, args: dict):
        return {'ok': True, 'action': 'search'}

    def get(self, *, root: Path, args: dict):
        return {'ok': True, 'action': 'get'}


class _FailKnowledge:
    def health(self, *, root: Path):
        raise RuntimeError('down')

    def index(self, *, root: Path, args: dict):
        raise RuntimeError('down')

    def search(self, *, root: Path, args: dict):
        raise RuntimeError('down')

    def get(self, *, root: Path, args: dict):
        raise RuntimeError('down')


class _FakeCodeParse:
    def health(self, *, root: Path):
        return {'ok': True}

    def overview(self, *, root: Path, args: dict):
        return {'kind': 'overview'}

    def symbols(self, *, root: Path, args: dict):
        return {'kind': 'symbols'}

    def definition(self, *, root: Path, args: dict):
        return {'kind': 'definition'}

    def references(self, *, root: Path, args: dict):
        return {'kind': 'references'}


def test_fallback_knowledge_backend_uses_primary_when_available(tmp_path):
    register_knowledge_backend('primary_ok', _OkKnowledge())
    register_knowledge_backend('fallback_ok', _OkKnowledge())
    backend = FallbackKnowledgeBackend(primary='primary_ok', fallback='fallback_ok')

    result = backend.search(root=tmp_path, args={'query': 'hello'})

    assert result['action'] == 'search'
    assert result['fallback_used'] is False
    assert result['backend'] == 'primary_ok'


def test_fallback_knowledge_backend_falls_back_on_error(tmp_path):
    register_knowledge_backend('primary_fail', _FailKnowledge())
    register_knowledge_backend('fallback_ok2', _OkKnowledge())
    backend = FallbackKnowledgeBackend(primary='primary_fail', fallback='fallback_ok2')

    result = backend.search(root=tmp_path, args={'query': 'hello'})

    assert result['action'] == 'search'
    assert result['fallback_used'] is True
    assert result['backend'] == 'fallback_ok2'
    assert 'primary_error' in result


def test_code_parse_backend_registry_roundtrip():
    register_code_parse_backend('fake_code_parse', _FakeCodeParse())
    backend = get_code_parse_backend('fake_code_parse')

    assert backend.overview(root=Path('.'), args={'path': 'x.py'})['kind'] == 'overview'


def test_knowledge_backend_registry_roundtrip():
    register_knowledge_backend('ok_roundtrip', _OkKnowledge())
    backend = get_knowledge_backend('ok_roundtrip')

    assert backend.health(root=Path('.'))['ok'] is True
