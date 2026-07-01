from __future__ import annotations

import builtins
from pathlib import Path
from typing import Any

import pytest
import tomllib


def _project_optional_dependencies() -> dict[str, list[str]]:
    pyproject = Path(__file__).resolve().parents[1] / 'pyproject.toml'
    data = tomllib.loads(pyproject.read_text(encoding='utf-8'))
    return data['project']['optional-dependencies']


def _requirement_names(requirements: list[str]) -> set[str]:
    names: set[str] = set()
    for requirement in requirements:
        prefix = requirement.split(';', 1)[0]
        name = prefix.split('[', 1)[0]
        for marker in ('>=', '<=', '==', '~=', '!=', '>', '<'):
            name = name.split(marker, 1)[0]
        names.add(name.strip().lower())
    return names


def _block_import(monkeypatch: pytest.MonkeyPatch, module_name: str) -> None:
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name == module_name or name.startswith(f'{module_name}.'):
            raise ImportError(f'blocked {module_name}')
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, '__import__', guarded_import)


def test_sc02_anthropic_extra_declared_and_import_guard_actionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extras = _project_optional_dependencies()
    assert 'anthropic' in extras
    assert 'anthropic' in _requirement_names(extras['anthropic'])

    from teaagent.managed_runtime import (
        AnthropicManagedRuntime,
        managed_runtime_capabilities,
    )

    capabilities = {item['name']: item for item in managed_runtime_capabilities()}
    assert 'teaagent[anthropic]' in capabilities['anthropic']['install_hint']

    _block_import(monkeypatch, 'anthropic')
    with pytest.raises(ImportError) as exc:
        AnthropicManagedRuntime(agent_id='x')
    assert 'teaagent[anthropic]' in str(exc.value)


def test_sc02_yaml_extra_declared_and_okf_guard_actionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extras = _project_optional_dependencies()
    assert 'yaml' in extras
    assert 'pyyaml' in _requirement_names(extras['yaml'])

    from teaagent import okf

    _block_import(monkeypatch, 'yaml')
    with pytest.raises(RuntimeError) as exc:
        okf._load_yaml_mapping('name: demo')
    assert 'teaagent[yaml]' in str(exc.value)
