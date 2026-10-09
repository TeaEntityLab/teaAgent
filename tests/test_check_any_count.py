# test-type: contract
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from check_any_count import (  # noqa: E402
    ANY_BASELINE,
    REPO_ROOT,
    count_any_in_source,
    main,
    scan,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _make_fixture(root: Path) -> None:
    _write(
        root / 'teaagent' / 'a.py',
        'from typing import Any, Optional\n'
        '# Any in a comment must not count\n'
        'x: Any = 1\n'
        'y: AnyStr = "s"\n'
        'def f(a: Any, b: list[Any]) -> Any:  # Any trailing comment is ignored\n'
        '    return a\n',
    )
    _write(
        root / 'teaagent' / 'sub' / 'b.py',
        'import typing\n\nz: typing.Any = None\nw: Any = None\n',
    )
    _write(
        root / 'teaagent' / 'c.py',
        'from typing import (\n    Any,\n    Dict,\n)\nv: Any = 0\n',
    )
    _write(root / 'teaagent' / 'e.py', 'n = 1\n')
    # Outside teaagent/ must never be scanned.
    _write(root / 'other' / 'd.py', 'x: Any = 1\n')


def test_scan_counts_per_file_and_ignores_comments_and_typing_imports(
    tmp_path: Path,
) -> None:
    _make_fixture(tmp_path)

    counts = scan(tmp_path)

    assert counts == {
        'teaagent/a.py': 4,
        'teaagent/c.py': 1,
        'teaagent/e.py': 0,
        'teaagent/sub/b.py': 2,
    }
    assert list(counts) == sorted(counts)
    assert sum(counts.values()) == 7


def test_count_any_in_source_skips_comment_only_and_typing_import_lines() -> None:
    assert count_any_in_source('# Any\nfrom typing import Any\nimport typing\n') == 0
    assert count_any_in_source('x: Any = 1  # Any\n') == 1
    assert count_any_in_source('def f(a: Any, b: Any) -> Any: ...\n') == 3


def test_main_fails_only_when_count_exceeds_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _make_fixture(tmp_path)

    assert main(['--root', str(tmp_path), '--baseline', '6']) == 1
    assert 'ERROR: Any count 7 exceeds baseline 6 (+1)' in capsys.readouterr().out

    assert main(['--root', str(tmp_path), '--baseline', '7']) == 0
    assert 'OK: Any count 7 <= baseline 7' in capsys.readouterr().out

    assert main(['--root', str(tmp_path), '--baseline', '9']) == 0
    output = capsys.readouterr().out
    assert 'OK: Any count 7 <= baseline 9' in output
    assert 'HINT: lower ANY_BASELINE to 7' in output


def test_real_repo_any_count_does_not_exceed_baseline() -> None:
    total = sum(scan(REPO_ROOT).values())

    assert total > 0
    assert total <= ANY_BASELINE
    assert main([]) == 0
