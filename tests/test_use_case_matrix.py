from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'build_use_case_matrix.py'
_SPEC = spec_from_file_location('build_use_case_matrix', _SCRIPT)
assert _SPEC and _SPEC.loader
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
build_matrix_markdown = _MODULE.build_matrix_markdown
parse_acceptance_test_files = _MODULE.parse_acceptance_test_files


def test_parse_acceptance_test_files_extracts_test_names() -> None:
    md = '| `test_a.py` | x |\n| `test_b.py` | y |'
    names = parse_acceptance_test_files(md)
    assert names == {'test_a.py', 'test_b.py'}


def test_build_matrix_marks_missing_tests() -> None:
    available = {'test_agents_md_injection_flow.py'}
    matrix = build_matrix_markdown(available)
    assert 'Project instruction conformance' in matrix
    assert 'no' in matrix.split('Project instruction conformance')[1].split('|')[1]
    assert '`test_first_run_experience_flow.py`' in matrix


def test_build_matrix_marks_covered_use_case() -> None:
    available = {
        'test_agents_md_injection_flow.py',
        'test_first_run_experience_flow.py',
    }
    matrix = build_matrix_markdown(available)
    assert 'Project instruction conformance' in matrix
    assert 'yes' in matrix.split('Project instruction conformance')[1].split('|')[1]
