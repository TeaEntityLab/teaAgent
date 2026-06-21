from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from teaagent.external_backends import BackendConfig, OkfKnowledgeAdapter
from teaagent.okf import validate_okf_bundle

pytestmark = [pytest.mark.acceptance]


def test_history_bundle_is_conformant_and_archive_only() -> None:
    repo = Path(__file__).resolve().parents[2]
    bundle = validate_okf_bundle(repo, 'knowledge/teaagent-history')

    assert bundle.conformant is True
    assert len(bundle.concepts) == 15
    for concept in bundle.concepts:
        extension = concept.metadata['teaagent']
        assert extension['docs_tier'] == 'archive'
        assert extension['lifecycle'] == 'historical'
        assert extension['authority'] == 'canonical'
        assert concept.metadata['type'] == 'Evidence'


def test_history_retrieval_returns_archive_labeled_results(
    tmp_path: Path,
) -> None:
    repo = Path(__file__).resolve().parents[2]
    source_bundle = repo / 'knowledge' / 'teaagent-history'
    target_bundle = tmp_path / 'knowledge' / 'teaagent-history'
    shutil.copytree(source_bundle, target_bundle)

    adapter = OkfKnowledgeAdapter(config=BackendConfig(root=tmp_path))
    indexed = adapter.index(
        root=tmp_path,
        args={
            'bundle': 'knowledge/teaagent-history',
            'collection': 'teaagent-history',
        },
    )
    assert indexed['index']['indexed'] == 17

    result = adapter.search(
        root=tmp_path,
        args={
            'query': 'system critical review audit governance architecture',
            'limit': 5,
            'collection': 'teaagent-history',
        },
    )
    assert len(result['hits']) > 0
    for hit in result['hits']:
        metadata = hit.get('metadata', {}).get('teaagent', {})
        assert metadata['docs_tier'] == 'archive'
        assert metadata['lifecycle'] == 'historical'


def test_current_bundle_does_not_contain_history(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]

    current_source = repo / 'knowledge' / 'teaagent-current'
    current_target = tmp_path / 'knowledge' / 'teaagent-current'
    shutil.copytree(current_source, current_target)

    adapter = OkfKnowledgeAdapter(config=BackendConfig(root=tmp_path))
    adapter.index(
        root=tmp_path,
        args={
            'bundle': 'knowledge/teaagent-current',
            'collection': 'teaagent-current',
        },
    )

    result = adapter.search(
        root=tmp_path,
        args={
            'query': 'system critical review audit 2026-06-10',
            'limit': 10,
            'collection': 'teaagent-current',
        },
    )
    for hit in result['hits']:
        metadata = hit.get('metadata', {}).get('teaagent', {})
        assert metadata['docs_tier'] != 'archive'
        assert metadata['lifecycle'] != 'historical'


def test_history_is_opt_in_only(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]

    current_source = repo / 'knowledge' / 'teaagent-current'
    history_source = repo / 'knowledge' / 'teaagent-history'
    shutil.copytree(current_source, tmp_path / 'knowledge' / 'teaagent-current')
    shutil.copytree(history_source, tmp_path / 'knowledge' / 'teaagent-history')

    adapter = OkfKnowledgeAdapter(config=BackendConfig(root=tmp_path))
    adapter.index(
        root=tmp_path,
        args={
            'bundle': 'knowledge/teaagent-current',
            'collection': 'teaagent-current',
        },
    )

    result = adapter.search(
        root=tmp_path,
        args={
            'query': 'comprehensive repository audit 2026-05-29',
            'limit': 10,
            'collection': 'teaagent-current',
        },
    )
    paths = {str(hit['path']) for hit in result['hits']}
    assert not any('comprehensive-audit' in path for path in paths)
