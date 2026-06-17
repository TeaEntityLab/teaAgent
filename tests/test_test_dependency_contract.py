from __future__ import annotations

import re
from pathlib import Path

import conftest


def test_missing_test_dependencies_reports_required_modules(monkeypatch):
    def fake_find_spec(module: str):
        if module == 'hypothesis':
            return None
        return object()

    monkeypatch.setattr(conftest.importlib.util, 'find_spec', fake_find_spec)

    assert conftest._missing_test_dependencies(['tests']) == ['hypothesis']


def test_missing_test_dependencies_ignores_unrelated_test_selection(monkeypatch):
    monkeypatch.setattr(conftest.importlib.util, 'find_spec', lambda module: None)

    assert conftest._missing_test_dependencies(['tests/acceptance']) == []


def test_missing_test_dependencies_checks_selected_hypothesis_tests(monkeypatch):
    monkeypatch.setattr(conftest.importlib.util, 'find_spec', lambda module: None)

    assert conftest._missing_test_dependencies(
        ['tests/test_property_invariants.py']
    ) == ['hypothesis']


def test_dev_extra_declares_required_test_dependencies():
    pyproject = Path(__file__).resolve().parents[1] / 'pyproject.toml'
    text = pyproject.read_text(encoding='utf-8')
    dev_block = re.search(r'dev = \[(.*?)\n\]', text, re.DOTALL)

    assert dev_block is not None
    assert '"hypothesis>=6.100"' in dev_block.group(1)
