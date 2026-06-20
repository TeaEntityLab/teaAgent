"""G-P2-1: directory-snapshot isolation acknowledgment flag tests.

Ensures that ``directory-snapshot`` isolation is gated behind the
``acknowledge_no_os_isolation`` flag instead of silently logging a warning.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from teaagent.subagents._isolation import prepare_subagent_isolation


def test_directory_snapshot_without_acknowledgment_is_rejected() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'src').mkdir()
        (root / 'src' / 'app.py').write_text('print("hi")\n', encoding='utf-8')
        (root / '.teaagent').mkdir()

        ctx, error = prepare_subagent_isolation(
            root,
            isolation='directory-snapshot',
            session_key='child-no-ack',
        )
        assert ctx is None
        assert error != ''
        assert 'acknowledge_no_os_isolation' in error
        # No snapshot directory should have been created.
        assert not (root / '.teaagent' / 'subagent-snapshots').exists()


def test_directory_snapshot_with_acknowledgment_proceeds() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'src').mkdir()
        (root / 'src' / 'app.py').write_text('print("hi")\n', encoding='utf-8')
        (root / '.teaagent').mkdir()
        (root / '.teaagent' / 'runs').mkdir()
        (root / '.teaagent' / 'runs' / 'parent.jsonl').write_text(
            'parent\n', encoding='utf-8'
        )

        ctx, error = prepare_subagent_isolation(
            root,
            isolation='directory-snapshot',
            session_key='child-ack',
            acknowledge_no_os_isolation=True,
        )
        assert error == ''
        assert ctx is not None
        assert (ctx.child_root / 'src' / 'app.py').is_file()
        assert not (ctx.child_root / '.teaagent' / 'runs').exists()
        ctx.cleanup()
        assert not ctx.container_path.exists()


def test_directory_snapshot_acknowledgment_error_mentions_docker() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / '.teaagent').mkdir()

        ctx, error = prepare_subagent_isolation(
            root,
            isolation='directory-snapshot',
            session_key='child-docker-hint',
        )
        assert ctx is None
        assert 'docker' in error.lower()


def test_shared_isolation_unaffected_by_acknowledgment_flag() -> None:
    """The acknowledgment flag only gates directory-snapshot, not shared."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        ctx, error = prepare_subagent_isolation(
            root,
            isolation='shared',
            session_key='child-shared',
        )
        assert ctx is not None
        assert error == ''
