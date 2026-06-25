from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_inventory_module():
    script = (
        Path(__file__).resolve().parents[1] / 'scripts' / 'generate_docs_inventory.py'
    )
    spec = spec_from_file_location('generate_docs_inventory', script)
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_generate_docs_inventory_is_deterministic(tmp_path: Path) -> None:
    module = _load_inventory_module()
    docs_root = tmp_path / 'docs'
    (docs_root / 'alpha').mkdir(parents=True)
    (docs_root / 'beta').mkdir()
    (docs_root / 'alpha' / 'a.md').write_text('# A\n', encoding='utf-8')
    (docs_root / 'beta' / 'b.md').write_text('# B\n', encoding='utf-8')

    first = module.generate_docs_inventory(docs_root=docs_root)
    second = module.generate_docs_inventory(docs_root=docs_root)
    assert first == second
    assert 'Not current truth' in first
    assert '`alpha/a.md`' in first
    assert '`beta/b.md`' in first
    # Check that tier column is present
    assert '| Tier |' in first


def test_classify_tier_constitution(tmp_path: Path) -> None:
    module = _load_inventory_module()
    assert module._classify_tier('product-contract.md') == 'constitution'
    assert module._classify_tier('architecture.md') == 'constitution'
    assert module._classify_tier('terminology.md') == 'constitution'
    assert module._classify_tier('acceptance.md') == 'constitution'
    assert module._classify_tier('roadmap-status.md') == 'constitution'
    assert module._classify_tier('agent-contribution-contract.md') == 'constitution'
    assert (
        module._classify_tier('strategy/harness-first-direction-2026-06-13.md')
        == 'constitution'
    )
    assert module._classify_tier('governance-compliance.md') == 'constitution'


def test_classify_tier_archive(tmp_path: Path) -> None:
    module = _load_inventory_module()
    assert module._classify_tier('analysis/foo-2026-06-12.md') == 'archive'
    assert module._classify_tier('analysis/review-2026-01-01.md') == 'archive'
    assert module._classify_tier('some-doc-2025-12-25.md') == 'archive'


def test_classify_tier_working(tmp_path: Path) -> None:
    module = _load_inventory_module()
    assert module._classify_tier('USAGE.md') == 'working'
    assert module._classify_tier('cli.md') == 'working'
    assert module._classify_tier('adr/0001-foo.md') == 'working'
    assert (
        module._classify_tier('analysis/active-findings-status-ledger-2026-06-06.md')
        == 'working'
    )


def test_check_docs_inventory_detects_stale_output(tmp_path: Path) -> None:
    module = _load_inventory_module()
    docs_root = tmp_path / 'docs'
    docs_root.mkdir()
    (docs_root / 'one.md').write_text('# one\n', encoding='utf-8')
    output_path = tmp_path / 'inventory.md'
    output_path.write_text('# stale\n', encoding='utf-8')

    errors = module.check_docs_inventory(
        docs_root=docs_root,
        output_path=output_path,
    )
    assert errors
    assert 'out of date' in errors[0]


def test_generate_docs_inventory_passes_for_repo() -> None:
    root = Path(__file__).resolve().parents[1]
    module = _load_inventory_module()
    output_path = root / 'docs' / 'generated' / 'docs-inventory.md'
    if not output_path.is_file():
        module.write_docs_inventory(
            docs_root=root / 'docs',
            output_path=output_path,
        )
    errors = module.check_docs_inventory(
        docs_root=root / 'docs',
        output_path=output_path,
    )
    assert errors == []
