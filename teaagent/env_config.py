"""Environment configuration parser for declarative hermetic agent environments.

This module handles parsing teaagent.toml configuration files that declare
required linters, compilers, and library runtimes for reproducible agent execution.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Use tomllib from stdlib for Python 3.11+, fall back to tomli
tomllib: Any = None
if sys.version_info >= (3, 11):
    import tomllib as _tomllib

    tomllib = _tomllib
    TOMLLIB_AVAILABLE = True
else:
    try:
        import tomli as _tomli

        tomllib = _tomli
        TOMLLIB_AVAILABLE = True
    except ImportError:
        TOMLLIB_AVAILABLE = False


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


ENV_LOCK_NOT_IMPLEMENTED_MSG = (
    'env lock cannot produce verifiable checksums yet; '
    'real package resolution is not implemented'
)


class EnvLockNotImplementedError(NotImplementedError):
    """Raised when lockfile generation cannot produce verifiable package checksums."""


class EnvLockResolutionError(LookupError):
    """Raised when a declared package cannot be resolved from the current environment."""


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

    if not TOMLLIB_AVAILABLE:
        raise ImportError(
            'tomli is required for TOML parsing on Python < 3.11. '
            'Install with: pip install teaagent[config]'
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


def _installed_distribution_hash(name: str) -> str:
    """Compute a stable content hash for an installed distribution."""
    dist = importlib.metadata.distribution(name)
    files = dist.files
    if files is not None:
        hashed_lines = sorted(
            f'{path} {file_hash}'
            for path in files
            if (file_hash := path.hash) is not None
        )
        if hashed_lines:
            return hashlib.sha256('\n'.join(hashed_lines).encode()).hexdigest()

    try:
        metadata = dist.read_text('METADATA')
    except (FileNotFoundError, KeyError, OSError):
        metadata = None
    if metadata is not None:
        return hashlib.sha256(metadata.encode()).hexdigest()

    version = importlib.metadata.version(name)
    return hashlib.sha256(f'{name}{version}'.encode()).hexdigest()


def resolve_installed_entry(pkg: PackageSpec) -> LockEntry:
    """Build a lock entry from the package as installed in the current interpreter."""
    try:
        version = importlib.metadata.version(pkg.name)
    except importlib.metadata.PackageNotFoundError as exc:
        raise EnvLockResolutionError(
            f"cannot lock '{pkg.name}': not installed in the current environment; "
            'run env provision first'
        ) from exc

    return LockEntry(
        name=pkg.name,
        version=version,
        hash=_installed_distribution_hash(pkg.name),
        source='installed',
        extras=list(pkg.extras),
    )


def verify_installed_entry(entry: LockEntry) -> tuple[bool, str]:
    """Verify a lock entry against the currently installed package."""
    try:
        installed_version = importlib.metadata.version(entry.name)
    except importlib.metadata.PackageNotFoundError:
        return False, 'not installed in the current environment'

    if installed_version != entry.version:
        return (
            False,
            f'version mismatch (installed {installed_version}, locked {entry.version})',
        )

    installed_hash = _installed_distribution_hash(entry.name)
    if installed_hash != entry.hash:
        return False, 'content hash mismatch'

    return True, ''


def generate_lockfile(spec: EnvironmentSpec, python_version: str) -> Lockfile:
    """Generate a lockfile from environment specification.

    Args:
        spec: Environment specification.
        python_version: Current Python version.

    Returns:
        Lockfile with resolved dependencies.

    Raises:
        EnvLockResolutionError: If a declared package is not installed.
    """
    entries = sorted(
        [resolve_installed_entry(pkg) for pkg in spec.packages],
        key=lambda entry: entry.name,
    )
    lockfile_without_hash = Lockfile(
        python_version=python_version,
        environment_type=spec.environment_type,
        entries=entries,
        lockfile_hash='',
    )
    lockfile_dict = lockfile_to_dict(lockfile_without_hash)
    lockfile_dict['lockfile_hash'] = ''
    lockfile_hash = hashlib.sha256(
        json.dumps(lockfile_dict, sort_keys=True).encode()
    ).hexdigest()
    result = Lockfile(
        python_version=python_version,
        environment_type=spec.environment_type,
        entries=entries,
        lockfile_hash=lockfile_hash,
    )
    assert verify_lockfile_integrity(result)
    return result


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
