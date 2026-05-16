from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[1] / 'scripts' / 'render_use_case_dashboard.py'
)
_SPEC = spec_from_file_location('render_use_case_dashboard', _SCRIPT)
assert _SPEC and _SPEC.loader
_MODULE = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
parse_matrix_markdown = _MODULE.parse_matrix_markdown
render_html = _MODULE.render_html


def test_parse_matrix_markdown_extracts_rows() -> None:
    markdown = """
| Use Case | Covered | Required Tests | Missing Tests |
|---|---|---|---|
| Foo | yes | `test_a.py` | - |
| Bar | no | `test_b.py` | `test_b.py` |
"""
    rows = parse_matrix_markdown(markdown)
    assert len(rows) == 2
    assert rows[0].use_case == 'Foo'
    assert rows[0].covered == 'yes'
    assert rows[1].missing_tests == '`test_b.py`'


def test_render_html_includes_coverage_summary() -> None:
    markdown = """
| Use Case | Covered | Required Tests | Missing Tests |
|---|---|---|---|
| Foo | yes | `test_a.py` | - |
| Bar | no | `test_b.py` | `test_b.py` |
"""
    rows = parse_matrix_markdown(markdown)
    rendered = render_html(rows)
    assert 'Covered: 1/2 (50.0%)' in rendered
    assert 'TeaAgent Use-case Coverage' in rendered
