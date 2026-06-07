from __future__ import annotations

from pathlib import Path

from teaagent.workspace_tools._config import (
    WorkspaceToolConfig,
    _load_gitignore_matcher,
)


class TestWorkspaceToolConfig:
    def test_defaults(self) -> None:
        config = WorkspaceToolConfig(root=Path('/test'))
        assert config.root == Path('/test')
        assert config.command_timeout_seconds == 30
        assert config.max_read_bytes == 200_000
        assert config.max_write_bytes == 200_000
        assert config.max_shell_command_bytes == 4_096
        assert config.max_shell_output_bytes == 200_000
        assert config.max_shell_timeout_seconds == 30

    def test_from_root_resolves(self) -> None:
        config = WorkspaceToolConfig.from_root('.')
        assert config.root.is_absolute()

    def test_custom_values(self) -> None:
        config = WorkspaceToolConfig(
            root=Path('/custom'),
            command_timeout_seconds=60,
            max_read_bytes=100,
        )
        assert config.command_timeout_seconds == 60
        assert config.max_read_bytes == 100


class TestGitignoreMatcher:
    def test_no_gitignore_returns_allow(self, tmp_path: Path) -> None:
        matcher = _load_gitignore_matcher(tmp_path)
        assert matcher('any/file.py') is False

    def test_basic_pattern(self, tmp_path: Path) -> None:
        (tmp_path / '.gitignore').write_text('__pycache__\n')
        matcher = _load_gitignore_matcher(tmp_path)
        assert matcher('__pycache__') is True
        assert matcher('src/foo.py') is False

    def test_negated_pattern(self, tmp_path: Path) -> None:
        (tmp_path / '.gitignore').write_text('*.log\n!important.log\n')
        matcher = _load_gitignore_matcher(tmp_path)
        assert matcher('debug.log') is True
        assert matcher('important.log') is False

    def test_comment_and_blank_lines(self, tmp_path: Path) -> None:
        (tmp_path / '.gitignore').write_text('# comment\n\n*.pyc\n')
        matcher = _load_gitignore_matcher(tmp_path)
        assert matcher('file.pyc') is True

    def test_directory_only_pattern(self, tmp_path: Path) -> None:
        (tmp_path / '.gitignore').write_text('build/\n')
        matcher = _load_gitignore_matcher(tmp_path)
        assert matcher('build') is True

    def test_leading_slash_pattern(self, tmp_path: Path) -> None:
        (tmp_path / '.gitignore').write_text('/vendored\n')
        matcher = _load_gitignore_matcher(tmp_path)
        assert matcher('vendored') is True

    def test_agignore_loaded(self, tmp_path: Path) -> None:
        (tmp_path / '.agignore').write_text('secrets.*\n')
        matcher = _load_gitignore_matcher(tmp_path)
        assert matcher('secrets.env') is True

    def test_multiple_patterns_ordering(self, tmp_path: Path) -> None:
        (tmp_path / '.gitignore').write_text('*.tmp\n!important.tmp\n*.log\n')
        matcher = _load_gitignore_matcher(tmp_path)
        assert matcher('debug.tmp') is True
        assert matcher('important.tmp') is False
        assert matcher('access.log') is True

    def test_double_star_pattern(self, tmp_path: Path) -> None:
        (tmp_path / '.gitignore').write_text('node_modules/**\n')
        matcher = _load_gitignore_matcher(tmp_path)
        assert matcher('node_modules') is True
        assert matcher('src/app.js') is False

    def test_double_star_dir_trailing_slash(self, tmp_path: Path) -> None:
        (tmp_path / '.gitignore').write_text('dist/**\n')
        matcher = _load_gitignore_matcher(tmp_path)
        assert matcher('dist') is True

    def test_read_error_returns_allow(self, tmp_path: Path) -> None:
        (tmp_path / '.gitignore').write_text('*.pyc\n')
        (tmp_path / '.gitignore').chmod(0o000)
        matcher = _load_gitignore_matcher(tmp_path)
        assert matcher('any.file') is False

    def test_only_negated_patterns(self, tmp_path: Path) -> None:
        (tmp_path / '.gitignore').write_text('!keep.txt\n')
        matcher = _load_gitignore_matcher(tmp_path)
        # Negated pattern un-ignores; no positive pattern to ignore means file is not ignored
        assert matcher('keep.txt') is False
        assert matcher('other.txt') is False

    def test_empty_gitignore(self, tmp_path: Path) -> None:
        (tmp_path / '.gitignore').write_text('')
        matcher = _load_gitignore_matcher(tmp_path)
        assert matcher('any.txt') is False
