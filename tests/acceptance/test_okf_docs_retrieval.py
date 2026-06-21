from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from teaagent.context_pack import build_context_pack
from teaagent.external_backends import BackendConfig, OkfKnowledgeAdapter
from teaagent.okf import validate_okf_bundle

pytestmark = [pytest.mark.acceptance]


def test_constitution_catalog_retrieval_and_trust_boundary(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    source_bundle = repo / 'knowledge' / 'teaagent-current'
    target_bundle = tmp_path / 'knowledge' / 'teaagent-current'
    shutil.copytree(source_bundle, target_bundle)

    bundle = validate_okf_bundle(tmp_path, 'knowledge/teaagent-current')
    assert bundle.conformant is True
    for concept in bundle.concepts:
        extension = concept.metadata['teaagent']
        source = str(extension['source_path'])
        source_path = tmp_path / source
        source_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / source, source_path)
        assert (
            hashlib.sha256(source_path.read_bytes()).hexdigest()
            == extension['source_sha256']
        )

    adapter = OkfKnowledgeAdapter(config=BackendConfig(root=tmp_path))
    indexed = adapter.index(
        root=tmp_path,
        args={
            'bundle': 'knowledge/teaagent-current',
            'collection': 'teaagent-current',
        },
    )
    assert indexed['index']['indexed'] == 10

    cases = {
        'product identity scope trust boundaries': 'docs/product-contract.md',
        'governance-first architecture module boundaries': 'docs/architecture.md',
        'canonical vocabulary terminology': 'docs/terminology.md',
        'acceptance tiers workflows verification': 'docs/acceptance.md',
        'roadmap horizons milestones next gates': 'docs/roadmap-status.md',
        'automated agents contribution gates': 'docs/agent-contribution-contract.md',
        'harness-first product direction scope constraints': (
            'docs/strategy/harness-first-direction-2026-06-13.md'
        ),
        'repository governance automated verification': (
            'docs/governance-compliance.md'
        ),
    }
    matched = 0
    for query, expected in cases.items():
        result = adapter.search(
            root=tmp_path,
            args={'query': query, 'limit': 3, 'collection': 'teaagent-current'},
        )
        paths = [str(hit['path']) for hit in result['hits']]
        matched += expected in paths
        assert all(
            hit.get('metadata', {}).get('teaagent', {}).get('docs_tier')
            == 'constitution'
            for hit in result['hits']
        )
    assert matched == len(cases)

    context_pack = build_context_pack(
        'product identity scope trust boundaries', root=tmp_path, readonly=True
    )
    knowledge = context_pack.graph_rag['sources']['knowledge']
    assert knowledge['format'] == 'okf'
    assert knowledge['content_role'] == 'data'
    assert knowledge['trust_level'] == 'untrusted'
    assert knowledge['hits'][0]['trust_level'] == 'untrusted'
    assert all(
        hit['metadata']['teaagent']['docs_tier'] == 'constitution'
        for hit in knowledge['hits']
    )
