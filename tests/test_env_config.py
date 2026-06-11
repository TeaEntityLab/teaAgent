"""Tests for environment configuration and lockfile management."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from teaagent.env_config import (
    EnvironmentSpec,
    LockEntry,
    Lockfile,
    PackageSpec,
    dict_to_lockfile,
    generate_lockfile,
    lockfile_to_dict,
    parse_teaagent_toml,
    read_lockfile,
    verify_lockfile_integrity,
    write_lockfile,
)


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


def test_lockfile_generation() -> None:
    spec = EnvironmentSpec(packages=[PackageSpec(name='ruff', version='0.4.0')])
    lockfile = generate_lockfile(spec, '3.11')
    assert lockfile.python_version == '3.11'
    assert len(lockfile.entries) == 1
    assert lockfile.entries[0].name == 'ruff'
    assert lockfile.entries[0].version == '0.4.0'
    assert len(lockfile.lockfile_hash) > 0


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
    spec = EnvironmentSpec(packages=[PackageSpec(name='ruff', version='0.4.0')])
    lockfile = generate_lockfile(spec, '3.11')
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
