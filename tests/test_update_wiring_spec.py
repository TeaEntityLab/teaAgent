# test-type: contract
"""Executable specification for the H6 update-CLI hold and trust boundary.

Companion to docs/specs/update-cli-wiring-and-packaging-spec-2026-07-11.md
(roadmap H6: update/* intentionally not CLI-wired; wiring is friction-gated).

The CLI-absence guard makes the hold executable. The Version quirk pins and
the tar-guard test freeze the trust-boundary facts the wiring-day checklist
depends on. Adversarial cases are noted per-test; the file is typed contract
because its primary job is freezing interfaces.
"""

from __future__ import annotations

import argparse
import io
import tarfile
from pathlib import Path

import pytest

from teaagent.cli import build_parser
from teaagent.update.installer import _safe_extract
from teaagent.update.update import Version


def _subcommand_names(parser: argparse.ArgumentParser) -> set[str]:
    """Collect registered top-level subcommand names from the CLI parser."""
    names: set[str] = set()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            names.update(action.choices)
    return names


def test_cli_has_no_update_subcommand() -> None:
    """Roadmap H6 hold guard: `teaagent update` is intentionally unwired.

    docs/roadmap-status.md H6 exit evidence states update/* has no CLI daily
    surface, and DR-006 gates wiring on owner friction evidence. If this test
    fails, someone registered an `update` subcommand: that is the wiring
    decision — the same commit must update the roadmap H6 row, satisfy the
    spec's section 3.2 trust-boundary preconditions, and delete this guard.
    """
    names = _subcommand_names(build_parser())
    assert names, 'expected the CLI parser to expose subcommands'
    assert 'update' not in names


def test_prerelease_ordering_is_lexicographic_not_semver() -> None:
    """Version prerelease comparison is plain string ordering today.

    Quirk pin (spec section 3.2 blocker 2): lexicographically
    '1.0.0-rc.10' < '1.0.0-rc.9', while semver numeric-identifier rules would
    order rc.9 < rc.10. A future `update apply` downgrade guard built on this
    ordering would misjudge prerelease chains. If this fails, the ordering
    was fixed — update the spec's blocker list and the wiring checklist.
    """
    rc9 = Version.from_string('1.0.0-rc.9')
    rc10 = Version.from_string('1.0.0-rc.10')
    assert rc10 < rc9
    assert not (rc9 < rc10)


def test_build_metadata_breaks_version_total_ordering() -> None:
    """Versions differing only in build metadata are unordered and unequal.

    Quirk pin (spec section 3.2 blocker 3): __eq__ includes build metadata
    while __lt__ ignores it, so 1.0.0+b1 and 1.0.0+b2 satisfy neither < nor
    == in either direction. An update loop comparing such versions would see
    a permanent 'different but not newer' state.
    """
    b1 = Version.from_string('1.0.0+b1')
    b2 = Version.from_string('1.0.0+b2')
    assert not (b1 < b2)
    assert not (b2 < b1)
    assert b1 != b2
    assert b1 <= b1
    assert b1 == Version.from_string('1.0.0+b1')


def _tar_with_member(name: str, content: bytes = b'x') -> tarfile.TarFile:
    """Build an in-memory tar archive containing a single named member."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as tar:
        info = tarfile.TarInfo(name=name)
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))
    buffer.seek(0)
    return tarfile.open(fileobj=buffer, mode='r')


def test_safe_extract_refuses_parent_directory_traversal(
    tmp_path: Path,
) -> None:
    """_safe_extract pre-scans members and raises before extracting anything.

    Adversarial case for the update trust boundary (spec section 3.2.4): a
    member named '../escape.txt' must raise tarfile.ExtractError and leave
    the parent directory untouched. The pre-scan property matters: the raise
    happens before extractall, so no partial extraction occurs. (The known
    str.startswith prefix-collision weakness is documented in the spec as a
    wiring precondition; it is not exploitable through any production caller
    today.)
    """
    extract_dir = tmp_path / 'install'
    extract_dir.mkdir()
    with (
        _tar_with_member('../escape.txt') as tar,
        pytest.raises(tarfile.ExtractError, match='escape'),
    ):
        _safe_extract(tar, extract_dir)
    assert not (tmp_path / 'escape.txt').exists()
    assert list(extract_dir.iterdir()) == []
