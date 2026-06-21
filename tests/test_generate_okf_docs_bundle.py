from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

from teaagent.okf import validate_okf_bundle


def _load_script(name: str, filename: str):
    script = Path(__file__).resolve().parents[1] / 'scripts' / filename
    spec = spec_from_file_location(name, script)
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_source(root: Path, path: str = 'docs/example.md') -> Path:
    source = root / path
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text('# Example Contract\n\nCanonical body.\n', encoding='utf-8')
    return source


def _write_manifest(
    root: Path,
    *,
    source: str = 'docs/example.md',
    concept_type: str = 'Contract',
    docs_tier: str = 'constitution',
    lifecycle: str = 'current',
    bundle: str = 'teaagent-current',
) -> Path:
    manifest = root / 'docs' / 'okf-catalog.yaml'
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        'catalog_version: 1\n'
        'okf_version: "0.1"\n'
        f'bundle: {bundle}\n'
        'change_date: "2026-06-21"\n'
        'change_summary: Generated a test catalog.\n'
        'documents:\n'
        f'  - source: {source}\n'
        f'    type: {concept_type}\n'
        '    description: Defines the test contract and its boundaries.\n'
        '    tags: [teaagent, test]\n'
        f'    docs_tier: {docs_tier}\n'
        '    authority: canonical\n'
        f'    lifecycle: {lifecycle}\n',
        encoding='utf-8',
    )
    return manifest


def test_repository_catalog_contains_constitution_and_current_truth() -> None:
    generator = _load_script(
        'generate_okf_docs_bundle_repo', 'generate_okf_docs_bundle.py'
    )
    inventory = _load_script(
        'generate_docs_inventory_repo', 'generate_docs_inventory.py'
    )
    root = Path(__file__).resolve().parents[1]

    catalog = generator.load_catalog(
        repo_root=root, manifest_path=root / 'docs' / 'okf-catalog.yaml'
    )

    constitution_sources = {f'docs/{path}' for path in inventory._CONSTITUTION_DOCS}
    catalog_sources = {entry.source for entry in catalog.entries}

    assert len(catalog.entries) == 15
    assert constitution_sources.issubset(catalog_sources)
    constitution_entries = [
        entry for entry in catalog.entries if entry.source in constitution_sources
    ]
    assert all(entry.docs_tier == 'constitution' for entry in constitution_entries)
    working_entries = [
        entry for entry in catalog.entries if entry.source not in constitution_sources
    ]
    assert all(entry.docs_tier == 'working' for entry in working_entries)
    assert all(entry.lifecycle == 'current' for entry in catalog.entries)
    assert all(len(entry.source_sha256) == 64 for entry in catalog.entries)


def test_repository_bundle_is_current_and_conformant() -> None:
    generator = _load_script(
        'generate_okf_docs_bundle_current', 'generate_okf_docs_bundle.py'
    )
    root = Path(__file__).resolve().parents[1]
    output = root / 'knowledge' / 'teaagent-current'

    errors = generator.check_bundle(
        repo_root=root,
        manifest_path=root / 'docs' / 'okf-catalog.yaml',
        output_path=output,
    )
    bundle = validate_okf_bundle(root, 'knowledge/teaagent-current')

    assert errors == []
    assert bundle.conformant is True
    assert len(bundle.concepts) == 15
    assert {concept.metadata['type'] for concept in bundle.concepts} == {
        'Architecture',
        'Contract',
        'Decision Record',
        'Evidence',
        'Plan',
        'Reference',
        'Runbook',
    }
    assert all('timestamp' not in concept.metadata for concept in bundle.concepts)


def test_generation_is_deterministic_and_stale_check_names_source(
    tmp_path: Path,
) -> None:
    generator = _load_script(
        'generate_okf_docs_bundle_determinism', 'generate_okf_docs_bundle.py'
    )
    source = _write_source(tmp_path)
    manifest = _write_manifest(tmp_path)
    output = tmp_path / 'knowledge' / 'teaagent-current'

    generator.generate_bundle(
        repo_root=tmp_path, manifest_path=manifest, output_path=output
    )
    first = {
        path.relative_to(output).as_posix(): path.read_bytes()
        for path in output.rglob('*')
        if path.is_file()
    }
    generator.generate_bundle(
        repo_root=tmp_path, manifest_path=manifest, output_path=output
    )
    second = {
        path.relative_to(output).as_posix(): path.read_bytes()
        for path in output.rglob('*')
        if path.is_file()
    }

    assert first == second
    assert (
        generator.check_bundle(
            repo_root=tmp_path, manifest_path=manifest, output_path=output
        )
        == []
    )

    source.write_text('# Example Contract\n\nChanged body.\n', encoding='utf-8')
    assert 'stale catalog entry for docs/example.md' in generator.check_bundle(
        repo_root=tmp_path, manifest_path=manifest, output_path=output
    )


@pytest.mark.parametrize(
    ('concept_type', 'docs_tier', 'lifecycle', 'bundle', 'message'),
    [
        (
            'Unknown',
            'constitution',
            'current',
            'teaagent-current',
            'type is not registered',
        ),
        (
            'Evidence',
            'archive',
            'historical',
            'teaagent-current',
            'cannot enter teaagent-current',
        ),
        (
            'Contract',
            'working',
            'current',
            'teaagent-history',
            'requires archive tier and historical lifecycle',
        ),
        (
            'Evidence',
            'archive',
            'current',
            'teaagent-history',
            'requires archive tier and historical lifecycle',
        ),
    ],
)
def test_bundle_tier_constraints_enforced(
    tmp_path: Path,
    concept_type: str,
    docs_tier: str,
    lifecycle: str,
    bundle: str,
    message: str,
) -> None:
    generator = _load_script(
        f'generate_okf_docs_bundle_constraint_{bundle}_{concept_type}',
        'generate_okf_docs_bundle.py',
    )
    _write_source(tmp_path)
    manifest = _write_manifest(
        tmp_path,
        concept_type=concept_type,
        docs_tier=docs_tier,
        lifecycle=lifecycle,
        bundle=bundle,
    )

    with pytest.raises(ValueError, match=message):
        generator.load_catalog(repo_root=tmp_path, manifest_path=manifest)


def test_source_escape_and_symlink_are_rejected(tmp_path: Path) -> None:
    generator = _load_script(
        'generate_okf_docs_bundle_escape', 'generate_okf_docs_bundle.py'
    )
    outside = tmp_path / 'outside-okf-doc.md'
    outside.write_text('# Outside\n', encoding='utf-8')
    manifest = _write_manifest(tmp_path, source='docs/../outside-okf-doc.md')
    with pytest.raises(ValueError, match='relative path below docs'):
        generator.load_catalog(repo_root=tmp_path, manifest_path=manifest)

    docs = tmp_path / 'docs'
    docs.mkdir(exist_ok=True)
    link = docs / 'linked.md'
    link.symlink_to(outside)
    manifest = _write_manifest(tmp_path, source='docs/linked.md')
    with pytest.raises(ValueError, match='symlinks are not allowed'):
        generator.load_catalog(repo_root=tmp_path, manifest_path=manifest)


def test_duplicate_source_and_output_name_mismatch_fail_closed(
    tmp_path: Path,
) -> None:
    generator = _load_script(
        'generate_okf_docs_bundle_duplicates', 'generate_okf_docs_bundle.py'
    )
    _write_source(tmp_path)
    manifest = _write_manifest(tmp_path)
    text = manifest.read_text(encoding='utf-8')
    duplicate = text[text.index('  - source:') :]
    manifest.write_text(text + duplicate, encoding='utf-8')
    with pytest.raises(ValueError, match='duplicate catalog source'):
        generator.load_catalog(repo_root=tmp_path, manifest_path=manifest)

    manifest = _write_manifest(tmp_path)
    with pytest.raises(ValueError, match='output directory must match'):
        generator.generate_bundle(
            repo_root=tmp_path,
            manifest_path=manifest,
            output_path=tmp_path / 'knowledge' / 'wrong-name',
        )


def test_failed_generation_preserves_previous_bundle(tmp_path: Path) -> None:
    generator = _load_script(
        'generate_okf_docs_bundle_preserve', 'generate_okf_docs_bundle.py'
    )
    _write_source(tmp_path)
    manifest = _write_manifest(tmp_path)
    output = tmp_path / 'knowledge' / 'teaagent-current'
    generator.generate_bundle(
        repo_root=tmp_path, manifest_path=manifest, output_path=output
    )
    previous = (output / 'index.md').read_bytes()
    manifest.write_text('catalog_version: 999\n', encoding='utf-8')

    with pytest.raises(ValueError, match='catalog_version'):
        generator.generate_bundle(
            repo_root=tmp_path, manifest_path=manifest, output_path=output
        )

    assert (output / 'index.md').read_bytes() == previous


def test_repository_reference_catalog_is_conformant() -> None:
    generator = _load_script(
        'generate_okf_docs_bundle_reference', 'generate_okf_docs_bundle.py'
    )
    root = Path(__file__).resolve().parents[1]
    output = root / 'knowledge' / 'teaagent-reference'

    errors = generator.check_bundle(
        repo_root=root,
        manifest_path=root / 'docs' / 'okf-catalog-reference.yaml',
        output_path=output,
    )
    bundle = validate_okf_bundle(root, 'knowledge/teaagent-reference')

    assert errors == []
    assert bundle.conformant is True
    assert len(bundle.concepts) == 27
    assert {concept.metadata['type'] for concept in bundle.concepts} == {
        'Guide',
        'Reference',
        'Risk Record',
        'Runbook',
        'Specification',
    }
    assert all(
        concept.metadata['teaagent']['docs_tier'] != 'archive'
        for concept in bundle.concepts
    )


def test_repository_reference_bundle_deterministic() -> None:
    generator = _load_script(
        'generate_okf_docs_bundle_reference_det', 'generate_okf_docs_bundle.py'
    )
    root = Path(__file__).resolve().parents[1]

    catalog1 = generator.load_catalog(
        repo_root=root,
        manifest_path=root / 'docs' / 'okf-catalog-reference.yaml',
    )
    catalog2 = generator.load_catalog(
        repo_root=root,
        manifest_path=root / 'docs' / 'okf-catalog-reference.yaml',
    )

    assert catalog1.entries == catalog2.entries
    assert len(catalog1.entries) == 27


def test_repository_history_catalog_is_archive_only() -> None:
    generator = _load_script(
        'generate_okf_docs_bundle_history', 'generate_okf_docs_bundle.py'
    )
    root = Path(__file__).resolve().parents[1]
    output = root / 'knowledge' / 'teaagent-history'

    errors = generator.check_bundle(
        repo_root=root,
        manifest_path=root / 'docs' / 'okf-catalog-history.yaml',
        output_path=output,
    )
    bundle = validate_okf_bundle(root, 'knowledge/teaagent-history')

    assert errors == []
    assert bundle.conformant is True
    assert len(bundle.concepts) == 15
    assert all(
        concept.metadata['teaagent']['docs_tier'] == 'archive'
        for concept in bundle.concepts
    )
    assert all(
        concept.metadata['teaagent']['lifecycle'] == 'historical'
        for concept in bundle.concepts
    )
    assert all(concept.metadata['type'] == 'Evidence' for concept in bundle.concepts)
