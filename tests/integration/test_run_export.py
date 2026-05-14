"""IT: Run export and import.

export_run() creates a tar.gz archive of one run's audit log.
import_run() unpacks it into a RunStore.  The round-trip must be lossless.
"""

from __future__ import annotations

from teaagent.run_export import ExportManifest, export_run, import_run
from teaagent.run_store import RunStore


def _seed_run(store: RunStore, run_id: str, task: str = 'export test') -> None:
    audit = store.audit_logger(run_id)
    audit.record('run_started', run_id, task=task)
    audit.record('iteration_started', run_id, iteration=1)
    audit.record('run_completed', run_id, answer='done')


def test_export_creates_archive(tmp_path):
    store = RunStore(tmp_path / 'src')
    _seed_run(store, 'run-abc123')

    archive = tmp_path / 'run-abc123.tar.gz'
    manifest = export_run('run-abc123', tmp_path / 'src', archive)

    assert archive.exists()
    assert manifest.run_id == 'run-abc123'
    assert manifest.event_count == 3


def test_import_restores_run(tmp_path):
    src = RunStore(tmp_path / 'src')
    _seed_run(src, 'run-xyz789', task='round-trip')
    archive = tmp_path / 'export.tar.gz'
    export_run('run-xyz789', tmp_path / 'src', archive)

    dst = RunStore(tmp_path / 'dst')
    result = import_run(archive, tmp_path / 'dst')

    assert result.run_id == 'run-xyz789'
    events = dst.show_run('run-xyz789')
    assert len(events) == 3
    assert events[0]['event_type'] == 'run_started'
    assert events[2]['event_type'] == 'run_completed'


def test_round_trip_preserves_all_event_fields(tmp_path):
    src = RunStore(tmp_path / 'src')
    _seed_run(src, 'run-full', task='preserve fields')
    archive = tmp_path / 'full.tar.gz'
    export_run('run-full', tmp_path / 'src', archive)

    dst = RunStore(tmp_path / 'dst')
    import_run(archive, tmp_path / 'dst')

    src_events = src.show_run('run-full')
    dst_events = dst.show_run('run-full')
    assert src_events == dst_events


def test_import_into_existing_store_does_not_clobber_other_runs(tmp_path):
    src = RunStore(tmp_path / 'src')
    _seed_run(src, 'run-import')

    dst = RunStore(tmp_path / 'dst')
    _seed_run(dst, 'run-existing', task='pre-existing')

    archive = tmp_path / 'export.tar.gz'
    export_run('run-import', tmp_path / 'src', archive)
    import_run(archive, tmp_path / 'dst')

    # Both runs must be present in dst
    run_ids = {s.run_id for s in dst.list_runs()}
    assert 'run-import' in run_ids
    assert 'run-existing' in run_ids


def test_export_manifest_fields(tmp_path):
    store = RunStore(tmp_path)
    _seed_run(store, 'run-manifest')
    archive = tmp_path / 'out.tar.gz'
    manifest = export_run('run-manifest', tmp_path, archive)

    assert isinstance(manifest, ExportManifest)
    assert manifest.run_id == 'run-manifest'
    assert manifest.event_count > 0
    assert manifest.archive_path == archive


def test_import_nonexistent_archive_raises(tmp_path):
    import pytest

    with pytest.raises(FileNotFoundError):
        import_run(tmp_path / 'does_not_exist.tar.gz', tmp_path)


def test_export_nonexistent_run_raises(tmp_path):
    import pytest

    with pytest.raises(FileNotFoundError):
        export_run('run-does-not-exist', tmp_path, tmp_path / 'out.tar.gz')


def test_hash_chain_survives_round_trip(tmp_path):
    """Exported and re-imported events must still form a valid hash chain."""
    from teaagent.audit_chain import verify_audit_chain

    src = RunStore(tmp_path / 'src')
    _seed_run(src, 'run-chain')
    archive = tmp_path / 'chain.tar.gz'
    export_run('run-chain', tmp_path / 'src', archive)

    dst = RunStore(tmp_path / 'dst')
    import_run(archive, tmp_path / 'dst')

    run_path = dst.run_path('run-chain')
    result = verify_audit_chain(run_path)
    assert result.valid, result.error
