from __future__ import annotations

import re
from pathlib import Path

import conftest
import tomllib


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
    """Every module in conftest._REQUIRED_TEST_DEPENDENCIES must be declared in
    the dev extra so full pytest collection has all required test dependencies."""
    pyproject = Path(__file__).resolve().parents[1] / 'pyproject.toml'
    data = tomllib.loads(pyproject.read_text(encoding='utf-8'))
    dev_requirements = data['project']['optional-dependencies']['dev']
    declared = {
        re.split(r'[<>=!~;\[ ]', req, maxsplit=1)[0].lower() for req in dev_requirements
    }
    assert conftest._REQUIRED_TEST_DEPENDENCIES, (
        'conftest._REQUIRED_TEST_DEPENDENCIES must enumerate the test deps to enforce'
    )
    for module in conftest._REQUIRED_TEST_DEPENDENCIES:
        assert module.lower() in declared, (
            f'{module} is required by conftest._REQUIRED_TEST_DEPENDENCIES but is not '
            'declared in pyproject.toml [project.optional-dependencies].dev'
        )
