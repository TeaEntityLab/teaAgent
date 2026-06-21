from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from teaagent.context_pack import build_context_pack
from teaagent.external_backends import BackendConfig, OkfKnowledgeAdapter
from teaagent.okf import validate_okf_bundle

pytestmark = [pytest.mark.acceptance]


def test_reference_bundle_is_conformant_and_non_archive() -> None:
    repo = Path(__file__).resolve().parents[2]
    bundle = validate_okf_bundle(repo, 'knowledge/teaagent-reference')

    assert bundle.conformant is True
    assert len(bundle.concepts) == 27
    for concept in bundle.concepts:
        extension = concept.metadata['teaagent']
        assert extension['docs_tier'] != 'archive'
        assert extension['lifecycle'] == 'current'
        assert extension['authority'] == 'canonical'


def test_reference_module_type_classification() -> None:
    repo = Path(__file__).resolve().parents[2]
    bundle = validate_okf_bundle(repo, 'knowledge/teaagent-reference')

    type_by_source: dict[str, str] = {
        str(concept.metadata['teaagent']['source_path']): concept.metadata['type']
        for concept in bundle.concepts
    }

    for source, expected_type in [
        ('docs/modules/cli/spec.md', 'Specification'),
        ('docs/modules/cli/api.md', 'Reference'),
        ('docs/modules/cli/inspection.md', 'Reference'),
        ('docs/modules/cli/risks.md', 'Risk Record'),
        ('docs/modules/audit/spec.md', 'Specification'),
        ('docs/modules/audit/api.md', 'Reference'),
        ('docs/modules/audit/risks.md', 'Risk Record'),
        ('docs/modules/runner/spec.md', 'Specification'),
        ('docs/modules/runner/inspection.md', 'Reference'),
        ('docs/modules/runner/risks.md', 'Risk Record'),
        ('docs/api/README.md', 'Reference'),
        ('docs/api/python-api.md', 'Reference'),
        ('docs/api/cli-api.md', 'Reference'),
        ('docs/guides/getting-started-solo-cli.md', 'Guide'),
        ('docs/ops/operations-manual.md', 'Runbook'),
        ('docs/ops/troubleshooting.md', 'Runbook'),
    ]:
        assert type_by_source[source] == expected_type, (
            f'{source}: expected {expected_type}, got {type_by_source[source]}'
        )


def test_reference_retrieval_and_trust_boundary(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    source_bundle = repo / 'knowledge' / 'teaagent-reference'
    target_bundle = tmp_path / 'knowledge' / 'teaagent-reference'
    shutil.copytree(source_bundle, target_bundle)

    adapter = OkfKnowledgeAdapter(config=BackendConfig(root=tmp_path))
    indexed = adapter.index(
        root=tmp_path,
        args={
            'bundle': 'knowledge/teaagent-reference',
            'collection': 'teaagent-reference',
        },
    )
    assert indexed['index']['indexed'] == 29

    cases = {
        'CLI module behavior specification entry point commands': (
            'docs/modules/cli/spec.md'
        ),
        'audit module hash-chained append-only event log': (
            'docs/modules/audit/spec.md'
        ),
        'approval manager destructive tool gate permission': (
            'docs/modules/approval_manager/spec.md'
        ),
        'runner module agent decision loop iteration': ('docs/modules/runner/spec.md'),
        'context pack module assembling model context knowledge': (
            'docs/modules/context_pack/spec.md'
        ),
        'external backends OKF knowledge adapter': (
            'docs/modules/external_backends/spec.md'
        ),
        'Python API specification module surface programmatic': (
            'docs/api/python-api.md'
        ),
        'troubleshooting guide common issues recovery': ('docs/ops/troubleshooting.md'),
    }
    matched = 0
    for query, expected in cases.items():
        result = adapter.search(
            root=tmp_path,
            args={'query': query, 'limit': 3, 'collection': 'teaagent-reference'},
        )
        paths = [str(hit['path']) for hit in result['hits']]
        matched += expected in paths
        assert all(
            hit.get('metadata', {}).get('teaagent', {}).get('docs_tier') != 'archive'
            for hit in result['hits']
        )
    assert matched >= 6

    context_pack = build_context_pack(
        'runner module agent decision loop iteration',
        root=tmp_path,
        readonly=True,
    )
    knowledge = context_pack.graph_rag['sources']['knowledge']
    assert knowledge['format'] == 'okf'
    assert knowledge['content_role'] == 'data'
    assert knowledge['trust_level'] == 'untrusted'
    assert knowledge['hits'][0]['trust_level'] == 'untrusted'
