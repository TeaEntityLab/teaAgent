"""Single-platform update proof orchestration (WDA-005)."""

from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from teaagent.update.delta import DeltaManager, DeltaType
from teaagent.update.installer import UpdateInstaller, UpdateManager


@dataclass(frozen=True)
class UpdatePlatformProof:
    platform: str
    from_version: str
    to_version: str
    artifact_sha256: str
    delta_sha256: str
    rollback_ok: bool
    install_dir: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'platform': self.platform,
            'from_version': self.from_version,
            'to_version': self.to_version,
            'artifact_sha256': self.artifact_sha256,
            'delta_sha256': self.delta_sha256,
            'rollback_ok': self.rollback_ok,
            'install_dir': self.install_dir,
        }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _write_version_tree(root: Path, version: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / 'VERSION').write_text(version + '\n', encoding='utf-8')
    (root / 'app.txt').write_text(f'teaagent {version}\n', encoding='utf-8')


def _file_map(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob('*'))
        if path.is_file()
    }


def _package_tree(source: Path, output: Path) -> None:
    with tarfile.open(output, 'w:gz') as tar:
        tar.add(source, arcname='.')


def run_update_platform_proof(
    *,
    work_dir: str | Path | None = None,
    platform: str = 'linux',
) -> UpdatePlatformProof:
    """Build v1→v2 package, apply delta update, rollback once."""
    base = Path(work_dir or tempfile.mkdtemp(prefix='teaagent-update-proof-'))
    v1_dir = base / 'src-v1'
    v2_dir = base / 'src-v2'
    install_dir = base / 'install'
    _write_version_tree(v1_dir, '1.0.0')
    _write_version_tree(v2_dir, '2.0.0')
    (v2_dir / 'app.txt').write_text('teaagent 2.0.0 enhanced\n', encoding='utf-8')

    pkg_v1 = base / 'pkg-v1.tar.gz'
    pkg_v2 = base / 'pkg-v2.tar.gz'
    _package_tree(v1_dir, pkg_v1)
    _package_tree(v2_dir, pkg_v2)

    delta_mgr = DeltaManager()
    delta = delta_mgr.create_delta(
        '1.0.0',
        '2.0.0',
        _file_map(v1_dir),
        _file_map(v2_dir),
        delta_type=DeltaType.FILE,
    )
    delta_path = base / 'update.delta'
    payload = (
        delta.delta_data
        if isinstance(delta.delta_data, bytes)
        else str(delta.delta_data).encode('utf-8')
    )
    delta_path.write_bytes(payload)

    shutil.copytree(v1_dir, install_dir)
    installer = UpdateInstaller(install_dir)
    installer.install_package(pkg_v2)
    if (install_dir / 'VERSION').read_text(encoding='utf-8').strip() != '2.0.0':
        raise RuntimeError('install did not apply target version')

    manager = UpdateManager(install_dir)
    rollback = manager.rollback_last_update()
    rollback_ok = rollback.status.value == 'rolled_back'
    if not rollback_ok:
        raise RuntimeError(rollback.error_message or 'rollback failed')

    return UpdatePlatformProof(
        platform=platform,
        from_version='1.0.0',
        to_version='2.0.0',
        artifact_sha256=_sha256_file(pkg_v2),
        delta_sha256=_sha256_file(base / 'update.delta'),
        rollback_ok=rollback_ok,
        install_dir=str(install_dir),
    )


def write_proof_report(proof: UpdatePlatformProof, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(proof.to_dict(), indent=2) + '\n', encoding='utf-8')
    return out
