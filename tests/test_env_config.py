"""Tests for environment configuration and lockfile management."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

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


class PackageSpecTests(unittest.TestCase):
    def test_package_spec_defaults(self) -> None:
        spec = PackageSpec(name="ruff")
        self.assertEqual(spec.name, "ruff")
        self.assertIsNone(spec.version)
        self.assertEqual(spec.extras, [])
        self.assertIsNone(spec.source)

    def test_package_spec_with_version(self) -> None:
        spec = PackageSpec(name="ruff", version="0.4.0")
        self.assertEqual(spec.name, "ruff")
        self.assertEqual(spec.version, "0.4.0")

    def test_package_spec_with_extras(self) -> None:
        spec = PackageSpec(name="ruff", extras=["lint", "format"])
        self.assertEqual(spec.extras, ["lint", "format"])


class EnvironmentSpecTests(unittest.TestCase):
    def test_environment_spec_defaults(self) -> None:
        spec = EnvironmentSpec()
        self.assertEqual(spec.packages, [])
        self.assertIsNone(spec.python_version)
        self.assertEqual(spec.linters, [])
        self.assertEqual(spec.tools, [])
        self.assertEqual(spec.environment_type, "uv")

    def test_environment_spec_with_packages(self) -> None:
        spec = EnvironmentSpec(
            packages=[PackageSpec(name="ruff"), PackageSpec(name="mypy")],
            python_version="3.11",
        )
        self.assertEqual(len(spec.packages), 2)
        self.assertEqual(spec.python_version, "3.11")


class ParseTeaagentTomlTests(unittest.TestCase):
    def test_parse_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "teaagent.toml"
            with self.assertRaises(FileNotFoundError):
                parse_teaagent_toml(path)

    def test_parse_simple_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "teaagent.toml"
            path.write_text(
                """
[env]
python_version = "3.11"
packages = ["ruff", "mypy"]
""",
                encoding="utf-8",
            )
            spec = parse_teaagent_toml(path)
            self.assertEqual(spec.python_version, "3.11")
            self.assertEqual(len(spec.packages), 2)
            self.assertEqual(spec.packages[0].name, "ruff")
            self.assertEqual(spec.packages[1].name, "mypy")

    def test_parse_complex_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "teaagent.toml"
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
                encoding="utf-8",
            )
            spec = parse_teaagent_toml(path)
            self.assertEqual(spec.environment_type, "nix")
            self.assertEqual(len(spec.packages), 2)
            self.assertEqual(spec.packages[0].version, "0.4.0")
            self.assertEqual(spec.packages[0].extras, ["lint"])
            self.assertEqual(spec.linters, ["ruff", "mypy"])
            self.assertEqual(spec.tools, ["ripgrep"])


class LockfileTests(unittest.TestCase):
    def test_lockfile_generation(self) -> None:
        spec = EnvironmentSpec(
            packages=[PackageSpec(name="ruff", version="0.4.0")]
        )
        lockfile = generate_lockfile(spec, "3.11")
        self.assertEqual(lockfile.python_version, "3.11")
        self.assertEqual(len(lockfile.entries), 1)
        self.assertEqual(lockfile.entries[0].name, "ruff")
        self.assertEqual(lockfile.entries[0].version, "0.4.0")
        self.assertTrue(len(lockfile.lockfile_hash) > 0)

    def test_lockfile_serialization(self) -> None:
        lockfile = Lockfile(
            python_version="3.11",
            environment_type="uv",
            entries=[
                LockEntry(
                    name="ruff",
                    version="0.4.0",
                    hash="abc123",
                    source="pypi",
                )
            ],
            lockfile_hash="xyz789",
        )
        data = lockfile_to_dict(lockfile)
        self.assertEqual(data["python_version"], "3.11")
        self.assertEqual(data["environment_type"], "uv")
        self.assertEqual(len(data["entries"]), 1)
        self.assertEqual(data["lockfile_hash"], "xyz789")

    def test_lockfile_deserialization(self) -> None:
        data = {
            "python_version": "3.11",
            "environment_type": "uv",
            "entries": [
                {
                    "name": "ruff",
                    "version": "0.4.0",
                    "hash": "abc123",
                    "source": "pypi",
                    "extras": [],
                }
            ],
            "lockfile_hash": "xyz789",
        }
        lockfile = dict_to_lockfile(data)
        self.assertEqual(lockfile.python_version, "3.11")
        self.assertEqual(len(lockfile.entries), 1)
        self.assertEqual(lockfile.entries[0].name, "ruff")

    def test_lockfile_write_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "teaagent.lock"
            lockfile = Lockfile(
                python_version="3.11",
                environment_type="uv",
                entries=[
                    LockEntry(
                        name="ruff",
                        version="0.4.0",
                        hash="abc123",
                        source="pypi",
                    )
                ],
                lockfile_hash="xyz789",
            )
            write_lockfile(lockfile, path)
            self.assertTrue(path.exists())

            read_lock = read_lockfile(path)
            self.assertIsNotNone(read_lock)
            self.assertEqual(read_lock.python_version, "3.11")
            self.assertEqual(len(read_lock.entries), 1)

    def test_read_missing_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "teaagent.lock"
            lockfile = read_lockfile(path)
            self.assertIsNone(lockfile)

    def test_lockfile_integrity_verification(self) -> None:
        spec = EnvironmentSpec(
            packages=[PackageSpec(name="ruff", version="0.4.0")]
        )
        lockfile = generate_lockfile(spec, "3.11")
        self.assertTrue(verify_lockfile_integrity(lockfile))

    def test_lockfile_integrity_tampered(self) -> None:
        lockfile = Lockfile(
            python_version="3.11",
            environment_type="uv",
            entries=[
                LockEntry(
                    name="ruff",
                    version="0.4.0",
                    hash="abc123",
                    source="pypi",
                )
            ],
            lockfile_hash="wrong_hash",
        )
        self.assertFalse(verify_lockfile_integrity(lockfile))


if __name__ == "__main__":
    unittest.main()
