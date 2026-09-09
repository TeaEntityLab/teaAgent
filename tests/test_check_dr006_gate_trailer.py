from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.check_dr006_gate_trailer import (
    _has_gate_trailer,
    _is_feat_subject,
    _touches_teaagent,
)

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'check_dr006_gate_trailer.py'
REPO_ROOT = Path(__file__).resolve().parents[1]


def test_is_feat_subject() -> None:
    assert _is_feat_subject('feat: add feature')
    assert _is_feat_subject('feat(scope): add feature')
    assert _is_feat_subject('FEAT: uppercase is accepted')
    assert not _is_feat_subject('docs: add docs')
    assert not _is_feat_subject('feature: add feature')
    assert not _is_feat_subject('fix: bug')
    assert not _is_feat_subject('feat add feature')  # missing colon


def test_touches_teaagent() -> None:
    assert _touches_teaagent(['teaagent/foo.py'])
    assert _touches_teaagent(['teaagent/foo.py', 'docs/bar.md'])
    assert not _touches_teaagent(['docs/bar.md', 'tests/test.py'])
    assert not _touches_teaagent([])


def test_has_gate_trailer_accepts_valid_and_rejects_invalid() -> None:
    assert _has_gate_trailer('feat: x\n\nGate: friction-driven')
    assert _has_gate_trailer('feat: x\n\nGate: governance-gap (EFX-002)')
    assert _has_gate_trailer('feat: x\n\nGate: owner-override: co-maintainer dogfood')
    assert _has_gate_trailer(
        'feat: x\n\nConstraint: DR-006 governance-gap only; existing seams'
    )
    assert not _has_gate_trailer('feat: x\n\nGate: vibes')
    assert not _has_gate_trailer('feat: x\n\nConstraint: S-07–S-10')
    assert not _has_gate_trailer('feat: x\n\nNo trailer here')


def _init_repo(tmp_path: Path) -> None:
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )


def _commit(tmp_path: Path, message: str, files: dict[str, str]) -> None:
    for path, content in files.items():
        file_path = tmp_path / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        subprocess.run(
            ['git', 'add', path], cwd=tmp_path, check=True, capture_output=True
        )
    subprocess.run(
        ['git', 'commit', '-m', message],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )


def _run_script(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_commit_msg_mode_fails_for_feat_without_gate(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, 'initial', {'README.md': 'hello'})
    (tmp_path / 'teaagent').mkdir()
    (tmp_path / 'teaagent' / 'foo.py').write_text('x = 1', encoding='utf-8')
    subprocess.run(
        ['git', 'add', 'teaagent/foo.py'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    msg_file = tmp_path / 'commit-msg.txt'
    msg_file.write_text('feat: add thing without gate\n\nBody.', encoding='utf-8')
    result = _run_script(tmp_path, '--commit-msg', str(msg_file))
    assert result.returncode == 1
    assert 'DR-006 gate missing' in result.stderr
    assert 'feat:' in result.stderr


def test_commit_msg_mode_passes_for_feat_with_gate(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, 'initial', {'README.md': 'hello'})
    (tmp_path / 'teaagent').mkdir()
    (tmp_path / 'teaagent' / 'foo.py').write_text('x = 1', encoding='utf-8')
    subprocess.run(
        ['git', 'add', 'teaagent/foo.py'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    msg_file = tmp_path / 'commit-msg.txt'
    msg_file.write_text('feat: add thing\n\nGate: governance-gap', encoding='utf-8')
    result = _run_script(tmp_path, '--commit-msg', str(msg_file))
    assert result.returncode == 0, result.stderr


def test_commit_msg_mode_docs_commit_without_trailer_passes(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, 'initial', {'README.md': 'hello'})
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs' / 'foo.md').write_text('x', encoding='utf-8')
    subprocess.run(
        ['git', 'add', 'docs/foo.md'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    msg_file = tmp_path / 'commit-msg.txt'
    msg_file.write_text('docs: update docs\n\nNo trailer.', encoding='utf-8')
    result = _run_script(tmp_path, '--commit-msg', str(msg_file))
    assert result.returncode == 0, result.stderr


def test_commit_msg_mode_feat_touching_only_docs_passes(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, 'initial', {'README.md': 'hello'})
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs' / 'foo.md').write_text('x', encoding='utf-8')
    subprocess.run(
        ['git', 'add', 'docs/foo.md'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    msg_file = tmp_path / 'commit-msg.txt'
    msg_file.write_text('feat: add docs feature\n\nNo trailer.', encoding='utf-8')
    result = _run_script(tmp_path, '--commit-msg', str(msg_file))
    assert result.returncode == 0, result.stderr


def test_commit_msg_mode_invalid_gate_value_fails(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, 'initial', {'README.md': 'hello'})
    (tmp_path / 'teaagent').mkdir()
    (tmp_path / 'teaagent' / 'foo.py').write_text('x = 1', encoding='utf-8')
    subprocess.run(
        ['git', 'add', 'teaagent/foo.py'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    msg_file = tmp_path / 'commit-msg.txt'
    msg_file.write_text('feat: add thing\n\nGate: vibes', encoding='utf-8')
    result = _run_script(tmp_path, '--commit-msg', str(msg_file))
    assert result.returncode == 1
    assert 'DR-006 gate missing' in result.stderr


def test_commit_mode_fails_for_missing_gate(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, 'initial', {'README.md': 'hello'})
    _commit(tmp_path, 'feat: missing gate', {'teaagent/foo.py': 'x = 1'})
    result = _run_script(tmp_path, '--commit', 'HEAD')
    assert result.returncode == 1
    assert 'DR-006 gate missing' in result.stderr


def test_commit_mode_passes_for_valid_gate(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, 'initial', {'README.md': 'hello'})
    _commit(
        tmp_path,
        'feat: with gate\n\nGate: governance-gap',
        {'teaagent/foo.py': 'x = 1'},
    )
    result = _run_script(tmp_path, '--commit', 'HEAD')
    assert result.returncode == 0, result.stderr


def test_commit_mode_feat_touching_only_docs_passes(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, 'initial', {'README.md': 'hello'})
    _commit(tmp_path, 'feat: docs only', {'docs/foo.md': 'x'})
    result = _run_script(tmp_path, '--commit', 'HEAD')
    assert result.returncode == 0, result.stderr


def test_base_mode_iterates_range(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, 'initial', {'README.md': 'hello'})
    _commit(
        tmp_path,
        'feat: first\n\nGate: friction-driven',
        {'teaagent/a.py': '1'},
    )
    _commit(
        tmp_path,
        'feat: second missing gate',
        {'teaagent/b.py': '2'},
    )
    result = _run_script(tmp_path, '--base', 'HEAD~2')
    assert result.returncode == 1
    assert 'second missing gate' in result.stderr


def test_real_history_12e7148_fails() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), '--commit', '12e7148'],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, result.stderr
    assert '12e7148' in result.stderr


def test_real_history_87d1c61_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), '--commit', '87d1c61'],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
