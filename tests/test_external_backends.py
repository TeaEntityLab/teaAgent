from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from teaagent.external_backends import (
    BackendConfig,
    BackendExecutionError,
    CxCliAdapter,
    FallbackKnowledgeBackend,
    LocalKnowledgeAdapter,
    QmdCliAdapter,
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


def test_register_knowledge_backend_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match='non-empty'):
        register_knowledge_backend('  ', _OkKnowledge())


def test_get_unknown_knowledge_backend_raises() -> None:
    with pytest.raises(ValueError, match='unknown knowledge'):
        get_knowledge_backend('definitely-missing-backend-name')


def test_fallback_health_reports_primary_failure(tmp_path: Path) -> None:
    register_knowledge_backend('primary_fail_h', _FailKnowledge())
    register_knowledge_backend('fallback_ok_h', _OkKnowledge())
    backend = FallbackKnowledgeBackend(
        primary='primary_fail_h', fallback='fallback_ok_h'
    )
    report = backend.health(root=tmp_path)
    assert len(report['backends']) == 2
    assert report['backends'][0]['ok'] is False


def test_fallback_index_and_get_use_fallback(tmp_path: Path) -> None:
    register_knowledge_backend('primary_fail_ix', _FailKnowledge())
    register_knowledge_backend('fallback_ok_ix', _OkKnowledge())
    backend = FallbackKnowledgeBackend(
        primary='primary_fail_ix', fallback='fallback_ok_ix'
    )
    indexed = backend.index(root=tmp_path, args={'collection': 'c'})
    assert indexed['fallback_used'] is True
    got = backend.get(root=tmp_path, args={'path': 'x'})
    assert got['action'] == 'get'


def test_cx_cli_adapter_parses_json_and_raw_output(tmp_path: Path) -> None:
    adapter = CxCliAdapter(binary='echo')
    with patch('teaagent.external_backends.subprocess.run') as run:
        run.return_value = MagicMock(returncode=0, stdout='{"ok": true}', stderr='')
        health = adapter.health(root=tmp_path)
        assert health['ok'] is True
        run.return_value = MagicMock(returncode=0, stdout='plain-text', stderr='')
        overview = adapter.overview(root=tmp_path, args={'path': 'teaagent/cli.py'})
        assert overview['raw'] == 'plain-text'


def test_local_knowledge_adapter_reads_file(tmp_path: Path) -> None:
    doc = tmp_path / 'note.txt'
    doc.write_text('local knowledge', encoding='utf-8')
    adapter = LocalKnowledgeAdapter(config=BackendConfig(root=tmp_path))
    payload = adapter.get(root=tmp_path, args={'path': 'note.txt'})
    assert payload['content'] == 'local knowledge'
    assert adapter.health(root=tmp_path)['ok'] is True


def test_cx_cli_adapter_timeout_raises_backend_execution_error(
    tmp_path: Path,
) -> None:
    adapter = CxCliAdapter(binary='cx', timeout=5)
    with patch('teaagent.external_backends.subprocess.run') as run:
        run.side_effect = subprocess.TimeoutExpired(
            cmd=['cx', 'lang', 'list'], timeout=5
        )
        with pytest.raises(BackendExecutionError) as exc_info:
            adapter.health(root=tmp_path)
        err = exc_info.value
        assert err.details['reason'] == 'timeout'
        assert err.details['timeout_seconds'] == 5
        assert err.backend_name == 'cx_cli'


def test_cx_cli_adapter_non_zero_exit_raises_backend_execution_error(
    tmp_path: Path,
) -> None:
    adapter = CxCliAdapter(binary='cx', timeout=10)
    with patch('teaagent.external_backends.subprocess.run') as run:
        run.return_value = MagicMock(returncode=1, stdout='', stderr='not found')
        with pytest.raises(BackendExecutionError) as exc_info:
            adapter.health(root=tmp_path)
        err = exc_info.value
        assert err.details['reason'] == 'non_zero_exit'
        assert err.details['exit_code'] == 1
        assert err.details['stderr'] == 'not found'


def test_cx_cli_adapter_success_passes_timeout(tmp_path: Path) -> None:
    adapter = CxCliAdapter(binary='echo', timeout=15)
    with patch('teaagent.external_backends.subprocess.run') as run:
        run.return_value = MagicMock(returncode=0, stdout='{"ok": true}', stderr='')
        adapter.health(root=tmp_path)
        _, kwargs = run.call_args
        assert kwargs['timeout'] == 15


def test_qmd_cli_adapter_timeout_raises_backend_execution_error(
    tmp_path: Path,
) -> None:
    adapter = QmdCliAdapter(binary='qmd', timeout=8)
    with patch('teaagent.external_backends.subprocess.run') as run:
        run.side_effect = subprocess.TimeoutExpired(
            cmd=['qmd', 'status', '--json'], timeout=8
        )
        with pytest.raises(BackendExecutionError) as exc_info:
            adapter.health(root=tmp_path)
        err = exc_info.value
        assert err.details['reason'] == 'timeout'
        assert err.details['timeout_seconds'] == 8
        assert err.backend_name == 'qmd_cli'


def test_qmd_cli_adapter_non_zero_exit_raises_backend_execution_error(
    tmp_path: Path,
) -> None:
    adapter = QmdCliAdapter(binary='qmd', timeout=10)
    with patch('teaagent.external_backends.subprocess.run') as run:
        run.return_value = MagicMock(returncode=2, stdout='', stderr='fatal error')
        with pytest.raises(BackendExecutionError) as exc_info:
            adapter.health(root=tmp_path)
        err = exc_info.value
        assert err.details['reason'] == 'non_zero_exit'
        assert err.details['exit_code'] == 2
        assert err.details['stderr'] == 'fatal error'
