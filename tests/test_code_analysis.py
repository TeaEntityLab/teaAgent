from __future__ import annotations

from teaagent.code_analysis import CodeAnalysisConfig, register_code_analysis_tools
from teaagent.tools import ToolRegistry


def test_code_analysis_tools_not_registered_when_disabled(tmp_path):
    registry = ToolRegistry()
    config = CodeAnalysisConfig.from_root(tmp_path, enabled=False)
    register_code_analysis_tools(registry, config)
    for name in (
        'code_definition',
        'code_references',
        'code_diagnostics',
        'code_symbols',
    ):
        try:
            registry.get(name)
            raise AssertionError(f'{name} should not exist when disabled')
        except KeyError:
            pass


def test_code_analysis_tools_registered_and_callable(tmp_path):
    registry = ToolRegistry()
    config = CodeAnalysisConfig.from_root(tmp_path, enabled=True)
    register_code_analysis_tools(registry, config)

    out1 = registry.execute(
        'code_definition', {'path': 'README.md', 'line': 1, 'column': 1}
    )
    out2 = registry.execute(
        'code_references', {'path': 'README.md', 'line': 1, 'column': 1}
    )
    out3 = registry.execute('code_diagnostics', {'path': 'README.md'})
    out4 = registry.execute('code_symbols', {'path': 'README.md'})

    assert out1 == {'references': []}
    assert out2 == {'references': []}
    assert out3 == {'diagnostics': []}
    assert out4 == {'symbols': []}
