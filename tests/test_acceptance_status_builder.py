from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'build_acceptance_status.py'
_SPEC = spec_from_file_location('build_acceptance_status', _SCRIPT)
assert _SPEC and _SPEC.loader
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
parse_passed_count = _MODULE.parse_passed_count
update_acceptance_status = _MODULE.update_acceptance_status


def test_parse_passed_count_from_pytest_output() -> None:
    output = '.................................... [100%]\n69 passed in 1.23s\n'
    assert parse_passed_count(output) == 69


def test_update_acceptance_status_replaces_marker() -> None:
    doc = 'Status line: `12 passed`\n'
    updated = update_acceptance_status(doc, 69)
    assert '`69 passed`' in updated
