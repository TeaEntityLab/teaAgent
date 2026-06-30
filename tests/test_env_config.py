"""Tests for environment configuration and lockfile management."""

from __future__ import annotations

import hashlib
import importlib.metadata
import io
import json
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from teaagent.env_config import (
    EnvironmentSpec,
    EnvLockResolutionError,
    LockEntry,
    Lockfile,
    PackageSpec,
    dict_to_lockfile,
    generate_lockfile,
    lockfile_to_dict,
    parse_teaagent_toml,
    read_lockfile,
    resolve_installed_entry,
    verify_installed_entry,
    verify_lockfile_integrity,
    write_lockfile,
)
from teaagent.env_manager import EnvironmentManager


def test_package_spec_defaults() -> None:
    spec = PackageSpec(name='ruff')
    assert spec.name == 'ruff'
    assert spec.version is None
    assert spec.extras == []
    assert spec.source is None


def test_package_spec_with_version() -> None:
    spec = PackageSpec(name='ruff', version='0.4.0')
    assert spec.name == 'ruff'
    assert spec.version == '0.4.0'


def test_package_spec_with_extras() -> None:
    spec = PackageSpec(name='ruff', extras=['lint', 'format'])
    assert spec.extras == ['lint', 'format']


def test_environment_spec_defaults() -> None:
    spec = EnvironmentSpec()
    assert spec.packages == []
    assert spec.python_version is None
    assert spec.linters == []
    assert spec.tools == []
    assert spec.environment_type == 'uv'


def test_environment_spec_with_packages() -> None:
    spec = EnvironmentSpec(
        packages=[PackageSpec(name='ruff'), PackageSpec(name='mypy')],
        python_version='3.11',
    )
    assert len(spec.packages) == 2
    assert spec.python_version == '3.11'


def test_parse_missing_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'teaagent.toml'
        with pytest.raises(FileNotFoundError):
            parse_teaagent_toml(path)


def test_parse_simple_config() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'teaagent.toml'
        path.write_text(
            """
[env]
python_version = "3.11"
packages = ["ruff", "mypy"]
""",
            encoding='utf-8',
        )
        spec = parse_teaagent_toml(path)
        assert spec.python_version == '3.11'
        assert len(spec.packages) == 2
        assert spec.packages[0].name == 'ruff'
        assert spec.packages[1].name == 'mypy'


def test_parse_complex_config() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'teaagent.toml'
        path.write_text(
            """
[env]
python_version = "3.11"
type = "nix"
linters = ["ruff", "mypy"]
tools = ["ripgrep"]

[[env.packages]]
name = "ruff"
version = "0.4.0"
extras = ["lint"]

[[env.packages]]
name = "mypy"
version = "1.10.0"
""",
            encoding='utf-8',
        )
        spec = parse_teaagent_toml(path)
        assert spec.environment_type == 'nix'
        assert len(spec.packages) == 2
        assert spec.packages[0].version == '0.4.0'
        assert spec.packages[0].extras == ['lint']
        assert spec.linters == ['ruff', 'mypy']
        assert spec.tools == ['ripgrep']


def test_generate_lockfile_installed_pytest() -> None:
    spec = EnvironmentSpec(packages=[PackageSpec(name='pytest')])
    lockfile = generate_lockfile(spec, '3.11')
    assert len(lockfile.entries) == 1
    entry = lockfile.entries[0]
    assert entry.name == 'pytest'
    assert entry.version == importlib.metadata.version('pytest')
    assert entry.hash
    assert entry.source == 'installed'
    assert verify_lockfile_integrity(lockfile)


def test_generate_lockfile_missing_package_raises() -> None:
    spec = EnvironmentSpec(
        packages=[PackageSpec(name='teaagent-nonexistent-package-xyz123')]
    )
    with pytest.raises(
        EnvLockResolutionError,
        match="cannot lock 'teaagent-nonexistent-package-xyz123'",
    ):
        generate_lockfile(spec, '3.11')


def test_resolve_installed_entry_includes_extras() -> None:
    entry = resolve_installed_entry(PackageSpec(name='pytest', extras=['dev']))
    assert entry.extras == ['dev']


def test_verify_installed_entry_round_trip() -> None:
    entry = resolve_installed_entry(PackageSpec(name='pytest'))
    ok, reason = verify_installed_entry(entry)
    assert ok is True
    assert reason == ''


def test_env_lock_round_trip_verify_and_tamper(tmp_path: Path) -> None:
    config = tmp_path / 'teaagent.toml'
    config.write_text(
        """
[env]
packages = ["pytest"]
""",
        encoding='utf-8',
    )
    manager = EnvironmentManager(tmp_path)
    spec = manager.load_spec()
    lockfile = generate_lockfile(spec, '3.11')
    write_lockfile(lockfile, manager._lockfile_path)

    assert manager.verify() is True

    tampered = Lockfile(
        python_version=lockfile.python_version,
        environment_type=lockfile.environment_type,
        entries=[
            LockEntry(
                name=lockfile.entries[0].name,
                version=lockfile.entries[0].version,
                hash='deadbeef',
                source=lockfile.entries[0].source,
                extras=lockfile.entries[0].extras,
            )
        ],
        lockfile_hash=lockfile.lockfile_hash,
    )
    write_lockfile(tampered, manager._lockfile_path)
    assert manager.verify() is False


def test_lockfile_serialization() -> None:
    lockfile = Lockfile(
        python_version='3.11',
        environment_type='uv',
        entries=[
            LockEntry(
                name='ruff',
                version='0.4.0',
                hash='abc123',
                source='pypi',
            )
        ],
        lockfile_hash='xyz789',
    )
    data = lockfile_to_dict(lockfile)
    assert data['python_version'] == '3.11'
    assert data['environment_type'] == 'uv'
    assert len(data['entries']) == 1
    assert data['lockfile_hash'] == 'xyz789'


def test_lockfile_deserialization() -> None:
    data = {
        'python_version': '3.11',
        'environment_type': 'uv',
        'entries': [
            {
                'name': 'ruff',
                'version': '0.4.0',
                'hash': 'abc123',
                'source': 'pypi',
                'extras': [],
            }
        ],
        'lockfile_hash': 'xyz789',
    }
    lockfile = dict_to_lockfile(data)
    assert lockfile.python_version == '3.11'
    assert len(lockfile.entries) == 1
    assert lockfile.entries[0].name == 'ruff'


def test_lockfile_write_read() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'teaagent.lock'
        lockfile = Lockfile(
            python_version='3.11',
            environment_type='uv',
            entries=[
                LockEntry(
                    name='ruff',
                    version='0.4.0',
                    hash='abc123',
                    source='pypi',
                )
            ],
            lockfile_hash='xyz789',
        )
        write_lockfile(lockfile, path)
        assert path.exists()

        read_lock = read_lockfile(path)
        assert read_lock is not None
        assert read_lock.python_version == '3.11'
        assert len(read_lock.entries) == 1


def test_read_missing_lockfile() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'teaagent.lock'
        lockfile = read_lockfile(path)
        assert lockfile is None


def test_lockfile_integrity_verification() -> None:
    lockfile = Lockfile(
        python_version='3.11',
        environment_type='uv',
        entries=[
            LockEntry(
                name='ruff',
                version='0.4.0',
                hash='abc123',
                source='pypi',
            )
        ],
    )
    lockfile_dict = lockfile_to_dict(lockfile)
    lockfile_dict['lockfile_hash'] = ''
    lockfile_hash = hashlib.sha256(
        json.dumps(lockfile_dict, sort_keys=True).encode()
    ).hexdigest()
    lockfile = Lockfile(
        python_version=lockfile.python_version,
        environment_type=lockfile.environment_type,
        entries=lockfile.entries,
        lockfile_hash=lockfile_hash,
    )
    assert verify_lockfile_integrity(lockfile)


def test_lockfile_integrity_tampered() -> None:
    lockfile = Lockfile(
        python_version='3.11',
        environment_type='uv',
        entries=[
            LockEntry(
                name='ruff',
                version='0.4.0',
                hash='abc123',
                source='pypi',
            )
        ],
        lockfile_hash='wrong_hash',
    )
    assert not verify_lockfile_integrity(lockfile)


def test_env_lock_command_writes_lockfile(tmp_path: Path) -> None:
    from teaagent.cli import main

    config = tmp_path / 'teaagent.toml'
    config.write_text(
        """
[env]
packages = ["pytest"]
""",
        encoding='utf-8',
    )
    lock_path = tmp_path / 'teaagent.lock'
    output = io.StringIO()

    with redirect_stdout(output):
        exit_code = main(['env', 'lock', '--root', str(tmp_path)])

    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert payload['status'] == 'success'
    assert payload['packages_count'] == 1
    assert lock_path.exists()


def test_env_lock_command_missing_package_returns_error(tmp_path: Path) -> None:
    from teaagent.cli import main

    config = tmp_path / 'teaagent.toml'
    config.write_text(
        """
[env]
packages = ["teaagent-nonexistent-package-xyz123"]
""",
        encoding='utf-8',
    )
    lock_path = tmp_path / 'teaagent.lock'
    output = io.StringIO()

    with redirect_stdout(output):
        exit_code = main(['env', 'lock', '--root', str(tmp_path)])

    payload = json.loads(output.getvalue())
    assert exit_code == 1
    assert payload['status'] == 'error'
    assert 'cannot lock' in payload['message']
    assert not lock_path.exists()


def test_env_lock_command_missing_config_returns_error(tmp_path: Path) -> None:
    from teaagent.cli import main

    output = io.StringIO()
    with redirect_stdout(output):
        exit_code = main(['env', 'lock', '--root', str(tmp_path)])

    payload = json.loads(output.getvalue())
    assert exit_code == 1
    assert payload['status'] == 'error'
    assert 'teaagent.toml not found' in payload['message']


def test_env_lock_subcommand_visible_in_help() -> None:
    import argparse

    from teaagent.cli import build_parser

    parser = build_parser()
    env_parser = None
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            env_parser = action.choices.get('env')
            if env_parser is not None:
                break
    assert env_parser is not None

    help_text = env_parser.format_help()
    assert 'Generate lockfile from currently installed packages' in help_text
    assert 'lock' in help_text.lower()
    assert 'provision' in help_text.lower()
    assert 'verify' in help_text.lower()
    assert '==SUPPRESS==' not in help_text
