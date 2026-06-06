"""Tests for command snippet inventory generation."""

from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_module():
    script = (
        Path(__file__).resolve().parents[1]
        / 'scripts'
        / 'generate_command_snippet_inventory.py'
    )
    spec = spec_from_file_location('generate_command_snippet_inventory_test', script)
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_registry_prefix_match() -> None:
    module = _load_module()
    registry = {
        'teaagent setup': {'coverage': 'smoke', 'verification': 'tests/x.py'},
    }
    matched = module._registry_match('teaagent setup --root .', registry)
    assert matched is not None
    assert matched[0] == 'teaagent setup'


def test_generate_inventory_for_repo() -> None:
    root = Path(__file__).resolve().parents[1]
    module = _load_module()
    text = module.generate_command_snippet_inventory(repo_root=root)
    assert 'Command Snippet Inventory' in text
    assert 'teaagent setup' in text
