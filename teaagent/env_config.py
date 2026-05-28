"""Environment configuration parser for declarative hermetic agent environments.

This module handles parsing teaagent.toml configuration files that declare
required linters, compilers, and library runtimes for reproducible agent execution.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Use tomllib from stdlib for Python 3.11+, fall back to tomli
if sys.version_info >= (3, 11):
    import tomllib
else:
    from contextlib import suppress

    with suppress(ImportError):
        import tomli as tomllib  # type: ignore


@dataclass(frozen=True)
class PackageSpec:
    """Specification for a single package dependency."""

    name: str
    version: str | None = None
    extras: list[str] = field(default_factory=list)
    source: str | None = None  # pypi, git, local path


@dataclass(frozen=True)
class EnvironmentSpec:
    """Complete environment specification from teaagent.toml."""

    packages: list[PackageSpec] = field(default_factory=list)
    python_version: str | None = None
    linters: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    environment_type: str = 'uv'  # uv, nix, docker


@dataclass(frozen=True)
class LockEntry:
    """Single entry in teaagent.lock for reproducible dependency tracking."""

    name: str
    version: str
    hash: str  # SHA256 hash of the package/binary
    source: str
    extras: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Lockfile:
    """Complete lockfile for bit-for-bit reproducibility."""

    python_version: str
    environment_type: str
    entries: list[LockEntry] = field(default_factory=list)
    lockfile_hash: str = ''  # Hash of the entire lockfile for integrity


def parse_teaagent_toml(path: Path) -> EnvironmentSpec:
    """Parse teaagent.toml configuration file.

    Args:
        path: Path to teaagent.toml file.

    Returns:
        EnvironmentSpec with parsed configuration.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config is invalid.
    """
    if not path.is_file():
        raise FileNotFoundError(f'teaagent.toml not found at {path}')

    if tomllib is None:
        raise ValueError(
            'tomli is required for Python < 3.11. Install with: pip install tomli'
        )

    try:
        data = tomllib.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise ValueError(f'Failed to parse teaagent.toml: {exc}') from exc

    env_section = data.get('env', {})

    packages = []
    for pkg_spec in env_section.get('packages', []):
        if isinstance(pkg_spec, str):
            packages.append(PackageSpec(name=pkg_spec))
        elif isinstance(pkg_spec, dict):
            packages.append(
                PackageSpec(
                    name=pkg_spec['name'],
                    version=pkg_spec.get('version'),
                    extras=pkg_spec.get('extras', []),
                    source=pkg_spec.get('source'),
                )
            )

    return EnvironmentSpec(
        packages=packages,
        python_version=env_section.get('python_version'),
        linters=env_section.get('linters', []),
        tools=env_section.get('tools', []),
        environment_type=env_section.get('type', 'uv'),
    )


def generate_lockfile(spec: EnvironmentSpec, python_version: str) -> Lockfile:
    """Generate a lockfile from environment specification.

    Args:
        spec: Environment specification.
        python_version: Current Python version.

    Returns:
        Lockfile with resolved dependencies.
    """
    # In a real implementation, this would resolve package versions
    # and compute actual hashes. For now, we create placeholder entries.
    entries = []
    for pkg in spec.packages:
        # Placeholder hash - in production, compute actual package hash
        hash_value = hashlib.sha256(
            f'{pkg.name}:{pkg.version or "latest"}'.encode()
        ).hexdigest()

        entries.append(
            LockEntry(
                name=pkg.name,
                version=pkg.version or 'latest',
                hash=hash_value,
                source=pkg.source or 'pypi',
                extras=pkg.extras,
            )
        )

    lockfile = Lockfile(
        python_version=python_version,
        environment_type=spec.environment_type,
        entries=entries,
    )

    # Compute lockfile integrity hash
    lockfile_dict = lockfile_to_dict(lockfile)
    lockfile_dict['lockfile_hash'] = ''
    lockfile_hash = hashlib.sha256(
        json.dumps(lockfile_dict, sort_keys=True).encode()
    ).hexdigest()

    return Lockfile(
        python_version=lockfile.python_version,
        environment_type=lockfile.environment_type,
        entries=lockfile.entries,
        lockfile_hash=lockfile_hash,
    )


def lockfile_to_dict(lockfile: Lockfile) -> dict[str, Any]:
    """Convert lockfile to dictionary for JSON serialization."""
    return {
        'python_version': lockfile.python_version,
        'environment_type': lockfile.environment_type,
        'entries': [
            {
                'name': entry.name,
                'version': entry.version,
                'hash': entry.hash,
                'source': entry.source,
                'extras': entry.extras,
            }
            for entry in lockfile.entries
        ],
        'lockfile_hash': lockfile.lockfile_hash,
    }


def dict_to_lockfile(data: dict[str, Any]) -> Lockfile:
    """Convert dictionary to lockfile."""
    entries = [
        LockEntry(
            name=entry['name'],
            version=entry['version'],
            hash=entry['hash'],
            source=entry['source'],
            extras=entry.get('extras', []),
        )
        for entry in data['entries']
    ]

    return Lockfile(
        python_version=data['python_version'],
        environment_type=data['environment_type'],
        entries=entries,
        lockfile_hash=data.get('lockfile_hash', ''),
    )


def write_lockfile(lockfile: Lockfile, path: Path) -> None:
    """Write lockfile to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(lockfile_to_dict(lockfile), indent=2) + '\n',
        encoding='utf-8',
    )


def read_lockfile(path: Path) -> Lockfile | None:
    """Read lockfile from disk.

    Returns None if file doesn't exist.
    """
    if not path.is_file():
        return None

    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return dict_to_lockfile(data)
    except (json.JSONDecodeError, KeyError):
        return None


def verify_lockfile_integrity(lockfile: Lockfile) -> bool:
    """Verify lockfile integrity by recomputing hash.

    Returns True if lockfile hash matches computed hash.
    """
    lockfile_dict = lockfile_to_dict(lockfile)
    original_hash = lockfile_dict['lockfile_hash']
    lockfile_dict['lockfile_hash'] = ''

    computed_hash = hashlib.sha256(
        json.dumps(lockfile_dict, sort_keys=True).encode()
    ).hexdigest()

    return original_hash == computed_hash
