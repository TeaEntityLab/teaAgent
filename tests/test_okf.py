from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from teaagent.okf import get_okf_concept, validate_okf_bundle


def _write_bundle(root: Path, *, concept_body: str = 'Portable knowledge.') -> Path:
    bundle = root / 'knowledge'
    (bundle / 'concepts').mkdir(parents=True)
    (bundle / 'index.md').write_text(
        '---\nokf_version: "0.1"\n---\n\n'
        '# Knowledge\n\n'
        '* [Example](concepts/example.md) - Example concept.\n',
        encoding='utf-8',
    )
    (bundle / 'concepts' / 'example.md').write_text(
        '---\n'
        'type: Reference\n'
        'title: Example\n'
        'custom_key: preserved\n'
        'teaagent:\n'
        '  review_state: approved\n'
        '---\n\n'
        f'{concept_body}\n',
        encoding='utf-8',
    )
    return bundle


def test_example_bundle_is_conformant_and_preserves_extensions() -> None:
    root = Path(__file__).resolve().parents[1]

    bundle = validate_okf_bundle(root, 'examples/okf/teaagent')

    assert bundle.conformant is True
    assert bundle.version == '0.1'
    assert {concept.concept_id for concept in bundle.concepts} == {
        'concepts/context-packs',
        'concepts/governance-boundary',
    }
    governance = next(
        concept
        for concept in bundle.concepts
        if concept.concept_id == 'concepts/governance-boundary'
    )
    assert governance.metadata['teaagent']['review_state'] == 'approved'
    assert governance.metadata['timestamp'] == '2026-06-21T00:00:00Z'
    json.dumps(bundle.to_dict())


def test_broken_links_are_warnings_and_do_not_break_conformance(
    tmp_path: Path,
) -> None:
    _write_bundle(tmp_path, concept_body='See [future](/concepts/future.md).')

    bundle = validate_okf_bundle(tmp_path)

    assert bundle.conformant is True
    assert any(finding.code == 'broken_link' for finding in bundle.findings)


def test_missing_type_blocks_conformance(tmp_path: Path) -> None:
    bundle_path = _write_bundle(tmp_path)
    concept = bundle_path / 'concepts' / 'example.md'
    concept.write_text('---\ntitle: Missing type\n---\nBody\n', encoding='utf-8')

    bundle = validate_okf_bundle(tmp_path)

    assert bundle.conformant is False
    assert any(finding.code == 'missing_type' for finding in bundle.findings)


def test_numeric_version_and_invalid_reserved_files_are_errors(
    tmp_path: Path,
) -> None:
    bundle_path = _write_bundle(tmp_path)
    (bundle_path / 'index.md').write_text(
        '---\nokf_version: 0.1\n---\n# No entries\n', encoding='utf-8'
    )
    (bundle_path / 'log.md').write_text(
        '# Log\n\n## 2026-01-01\n\nNo list entry.\n', encoding='utf-8'
    )

    bundle = validate_okf_bundle(tmp_path)

    assert bundle.conformant is False
    codes = {finding.code for finding in bundle.findings}
    assert 'invalid_version' in codes
    assert 'invalid_index' in codes
    assert 'invalid_log' in codes


def test_unsafe_bundle_link_blocks_conformance(tmp_path: Path) -> None:
    _write_bundle(tmp_path, concept_body='See [outside](../../outside.md).')
    (tmp_path / 'outside.md').write_text('outside', encoding='utf-8')

    bundle = validate_okf_bundle(tmp_path)

    assert bundle.conformant is False
    assert any(finding.code == 'unsafe_link' for finding in bundle.findings)


@pytest.mark.skipif(not hasattr(os, 'symlink'), reason='symlinks unavailable')
def test_symlinked_concept_is_rejected(tmp_path: Path) -> None:
    bundle_path = _write_bundle(tmp_path)
    target = tmp_path / 'outside.md'
    target.write_text('---\ntype: Reference\n---\noutside\n', encoding='utf-8')
    linked = bundle_path / 'concepts' / 'linked.md'
    linked.symlink_to(target)

    bundle = validate_okf_bundle(tmp_path)

    assert bundle.conformant is False
    assert any(finding.code == 'symlink_not_allowed' for finding in bundle.findings)


def test_get_concept_preserves_body_and_blocks_traversal(tmp_path: Path) -> None:
    _write_bundle(tmp_path)

    bundle, concept = get_okf_concept(tmp_path, 'knowledge', 'concepts/example')

    assert bundle.conformant is True
    assert concept.metadata['custom_key'] == 'preserved'
    assert 'Portable knowledge.' in concept.body
    with pytest.raises(ValueError, match='path escapes root'):
        get_okf_concept(tmp_path, 'knowledge', '../outside')


def test_markdown_link_titles_are_parsed_without_false_broken_link(
    tmp_path: Path,
) -> None:
    _write_bundle(
        tmp_path,
        concept_body='See [the index](/index.md "Bundle index").',
    )

    bundle = validate_okf_bundle(tmp_path)

    assert bundle.conformant is True
    assert not any(finding.code == 'broken_link' for finding in bundle.findings)


def test_non_json_yaml_values_are_rejected(tmp_path: Path) -> None:
    bundle_path = _write_bundle(tmp_path)
    concept = bundle_path / 'concepts' / 'example.md'
    concept.write_text(
        '---\ntype: Reference\ninvalid: !!set {one: null}\n---\nBody\n',
        encoding='utf-8',
    )

    bundle = validate_okf_bundle(tmp_path)

    assert bundle.conformant is False
    assert any(
        finding.code == 'invalid_document'
        and 'unsupported YAML value' in finding.message
        for finding in bundle.findings
    )


def test_bundle_entry_limit_stops_validation(tmp_path: Path) -> None:
    _write_bundle(tmp_path)

    bundle = validate_okf_bundle(tmp_path, max_bundle_files=1)

    assert bundle.conformant is False
    assert bundle.findings[0].code == 'bundle_too_large'
