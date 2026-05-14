"""Run export and import.

``export_run`` packs a single run's JSONL audit log into a ``tar.gz`` archive.
``import_run`` unpacks the archive into a :class:`~teaagent.run_store.RunStore`
directory so the run appears in ``list_runs`` on any machine.

Archive layout::

    run-<run_id>.jsonl          # the audit log (hash-chained JSONL)
    manifest.json               # run metadata (run_id, event_count, version)

Usage::

    from teaagent.run_export import export_run, import_run

    manifest = export_run('abc123', workspace_root, Path('abc123.tar.gz'))
    print(manifest.event_count)

    result = import_run(Path('abc123.tar.gz'), other_workspace_root)
    print(result.run_id)
"""

from __future__ import annotations

import io
import json
import tarfile
from dataclasses import dataclass
from pathlib import Path

_ARCHIVE_VERSION = 1
_MANIFEST_NAME = 'manifest.json'


@dataclass(frozen=True)
class ExportManifest:
    """Metadata about a completed export or import operation."""

    run_id: str
    event_count: int
    archive_path: Path
    version: int = _ARCHIVE_VERSION


def _run_jsonl_name(run_id: str) -> str:
    return f'run-{run_id}.jsonl'


def export_run(
    run_id: str,
    store_root: str | Path,
    output_path: str | Path,
) -> ExportManifest:
    """Export one run to a ``tar.gz`` archive.

    Parameters
    ----------
    run_id:
        The run identifier to export.
    store_root:
        Workspace root containing the ``.teaagent/runs/`` directory.
    output_path:
        Destination archive path (created or overwritten).

    Returns
    -------
    :class:`ExportManifest`
        Metadata about the exported run.

    Raises
    ------
    FileNotFoundError
        When *run_id* does not exist in *store_root*.
    """
    from teaagent.run_store import RunStore

    store = RunStore(store_root)
    run_path = store.run_path(run_id)
    if not run_path.exists():
        raise FileNotFoundError(f"run '{run_id}' not found in {store_root}")

    raw = run_path.read_bytes()
    event_count = sum(
        1 for line in raw.decode('utf-8', errors='replace').splitlines() if line.strip()
    )

    manifest_data = json.dumps(
        {'run_id': run_id, 'event_count': event_count, 'version': _ARCHIVE_VERSION},
        sort_keys=True,
    ).encode('utf-8')
    manifest_bytes = manifest_data

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(str(out), 'w:gz') as tar:
        # Add audit JSONL
        info_jsonl = tarfile.TarInfo(name=_run_jsonl_name(run_id))
        info_jsonl.size = len(raw)
        tar.addfile(info_jsonl, io.BytesIO(raw))

        # Add manifest
        info_manifest = tarfile.TarInfo(name=_MANIFEST_NAME)
        info_manifest.size = len(manifest_bytes)
        tar.addfile(info_manifest, io.BytesIO(manifest_bytes))

    return ExportManifest(
        run_id=run_id,
        event_count=event_count,
        archive_path=out,
    )


def import_run(
    archive_path: str | Path,
    store_root: str | Path,
) -> ExportManifest:
    """Import a run from a ``tar.gz`` archive into a :class:`RunStore`.

    Parameters
    ----------
    archive_path:
        Path to the ``tar.gz`` archive produced by :func:`export_run`.
    store_root:
        Workspace root whose ``.teaagent/runs/`` directory will receive the
        imported run.

    Returns
    -------
    :class:`ExportManifest`
        Metadata about the imported run.

    Raises
    ------
    FileNotFoundError
        When *archive_path* does not exist.
    ValueError
        When the archive is malformed or missing required members.
    """
    from teaagent.run_store import RunStore
    from teaagent.storage import atomic_write_text

    src = Path(archive_path)
    if not src.exists():
        raise FileNotFoundError(f'archive not found: {src}')

    store = RunStore(store_root)

    with tarfile.open(str(src), 'r:gz') as tar:
        # Read manifest
        try:
            manifest_member = tar.getmember(_MANIFEST_NAME)
        except KeyError as exc:
            raise ValueError(f'archive missing {_MANIFEST_NAME}') from exc

        mf = tar.extractfile(manifest_member)
        if mf is None:
            raise ValueError(f'cannot read {_MANIFEST_NAME} from archive')
        manifest_data = json.loads(mf.read().decode('utf-8'))
        run_id: str = str(manifest_data['run_id'])
        event_count: int = int(manifest_data.get('event_count', 0))

        # Read run JSONL
        jsonl_name = _run_jsonl_name(run_id)
        try:
            jsonl_member = tar.getmember(jsonl_name)
        except KeyError as exc:
            raise ValueError(f'archive missing {jsonl_name}') from exc

        jf = tar.extractfile(jsonl_member)
        if jf is None:
            raise ValueError(f'cannot read {jsonl_name} from archive')
        jsonl_text = jf.read().decode('utf-8')

    # Write into destination store (atomic, then secure)
    dest_path = store.run_path(run_id)
    atomic_write_text(dest_path, jsonl_text)
    from teaagent.audit import secure_audit_file

    secure_audit_file(dest_path)

    return ExportManifest(
        run_id=run_id,
        event_count=event_count,
        archive_path=src,
    )
