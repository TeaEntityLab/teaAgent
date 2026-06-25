"""Cross-generator agreement for documentation tier classification."""

from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_script(name: str):
    script = Path(__file__).resolve().parents[1] / 'scripts' / name
    spec = spec_from_file_location(name.replace('.py', ''), script)
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_working_current_truth_overrides_agree() -> None:
    docs_tier = _load_script('docs_tier.py')
    inventory = _load_script('generate_docs_inventory.py')
    aging = _load_script('report_docs_aging.py')

    for rel_path in docs_tier.WORKING_CURRENT_TRUTH_DOCS:
        assert inventory._classify_tier(rel_path) == 'working'
        assert not aging._is_archive_tier(rel_path)
        assert not aging._is_archive_tier(f'docs/{rel_path}')


def test_all_docs_archive_tier_agreement() -> None:
    root = Path(__file__).resolve().parents[1]
    docs_root = root / 'docs'
    inventory = _load_script('generate_docs_inventory.py')
    aging = _load_script('report_docs_aging.py')

    for path in sorted(docs_root.rglob('*.md')):
        rel_path = path.relative_to(docs_root).as_posix()
        inv_tier = inventory._classify_tier(rel_path)
        if inv_tier == 'constitution':
            continue
        aging_archive = aging._is_archive_tier(rel_path)
        assert aging_archive == (inv_tier == 'archive'), rel_path
