"""Tests for time-travel replay CLI (TASK-012)."""

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from teaagent.cli._handlers._replay import (
    replay_fork,
    replay_list,
    replay_resume,
    replay_steps,
)


def _make_audit_log(run_path: Path, num_entries: int = 3) -> None:
    """Create a minimal audit JSONL at *run_path* for testing."""
    from teaagent.types import AuditLogger

    run_path.parent.mkdir(parents=True, exist_ok=True)
    log = AuditLogger(path=run_path)
    for i in range(num_entries):
        log.record(
            event_type='PreToolUse' if i % 2 == 0 else 'PostToolUse',
            run_id=run_path.stem,
            summary=f'Step {i}',
            tool='read_file',
        )


class ReplayCLITests(unittest.TestCase):
    def test_replay_list_empty(self) -> None:
        """Test replay list with no runs."""
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                root=tmp,
                limit=50,
            )

            result = replay_list(args)

            self.assertEqual(result, 0)

    def test_replay_steps_nonexistent_run(self) -> None:
        """Test replay steps with nonexistent run."""
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                root=tmp,
                run_id='nonexistent-run',
            )

            result = replay_steps(args)

            self.assertEqual(result, 1)

    def test_replay_fork_nonexistent_run(self) -> None:
        """Test replay fork with nonexistent run."""
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                root=tmp,
                run_id='nonexistent-run',
                step=0,
                branch_name='test-branch',
            )

            result = replay_fork(args)

            self.assertEqual(result, 1)

    def test_replay_fork_invalid_step(self) -> None:
        """Test replay fork with invalid step number."""
        with tempfile.TemporaryDirectory() as tmp:
            from teaagent.run_store import RunStore

            run_id = 'test-run'
            store = RunStore(Path(tmp))
            run_path = store.run_path(run_id)
            _make_audit_log(run_path, num_entries=2)

            args = argparse.Namespace(
                root=tmp,
                run_id=run_id,
                step=99,
                branch_name='test-branch',
            )

            result = replay_fork(args)

            self.assertEqual(result, 1)

    def test_replay_fork_valid(self) -> None:
        """Test replay fork with valid parameters."""
        with tempfile.TemporaryDirectory() as tmp:
            from teaagent.run_store import RunStore

            run_id = 'test-run'
            store = RunStore(Path(tmp))
            run_path = store.run_path(run_id)
            _make_audit_log(run_path, num_entries=3)

            args = argparse.Namespace(
                root=tmp,
                run_id=run_id,
                step=1,
                branch_name='test-branch',
            )

            result = replay_fork(args)

            self.assertEqual(result, 0)

    def test_replay_resume_nonexistent_checkpoint(self) -> None:
        """Test replay resume with nonexistent checkpoint."""
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                root=tmp,
                branch_name='nonexistent-branch',
            )

            result = replay_resume(args)

            self.assertEqual(result, 1)

    def test_replay_resume_valid(self) -> None:
        """Test replay resume with valid checkpoint."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create a checkpoint
            checkpoint_dir = Path(tmp) / '.teaagent' / 'replay'
            checkpoint_dir.mkdir(parents=True, exist_ok=True)

            checkpoint_path = checkpoint_dir / 'test-branch.json'
            checkpoint_data = {
                'run_id': 'test-run',
                'fork_step': 0,
                'branch_name': 'test-branch',
                'fork_timestamp': '2024-01-01T00:00:00Z',
                'fork_entry': {'event_type': 'test', 'summary': 'test'},
            }
            checkpoint_path.write_text(
                json.dumps(checkpoint_data, indent=2), encoding='utf-8'
            )

            args = argparse.Namespace(
                root=tmp,
                branch_name='test-branch',
            )

            result = replay_resume(args)

            self.assertEqual(result, 0)

    def test_replay_steps_with_entries(self) -> None:
        """Test replay steps with actual run entries."""
        with tempfile.TemporaryDirectory() as tmp:
            from teaagent.run_store import RunStore

            run_id = 'test-run'
            store = RunStore(Path(tmp))
            run_path = store.run_path(run_id)
            _make_audit_log(run_path, num_entries=3)

            args = argparse.Namespace(
                root=tmp,
                run_id=run_id,
            )

            result = replay_steps(args)

            self.assertEqual(result, 0)

    def test_replay_fork_creates_checkpoint(self) -> None:
        """Test that replay fork creates proper checkpoint structure."""
        with tempfile.TemporaryDirectory() as tmp:
            from teaagent.run_store import RunStore

            run_id = 'test-run'
            store = RunStore(Path(tmp))
            run_path = store.run_path(run_id)
            _make_audit_log(run_path, num_entries=3)

            args = argparse.Namespace(
                root=tmp,
                run_id=run_id,
                step=0,
                branch_name='test-branch',
            )

            result = replay_fork(args)
            self.assertEqual(result, 0)

            checkpoint_path = Path(tmp) / '.teaagent' / 'replay' / 'test-branch.json'
            self.assertTrue(checkpoint_path.is_file())

            data = json.loads(checkpoint_path.read_text(encoding='utf-8'))
            self.assertEqual(data['run_id'], run_id)
            self.assertEqual(data['branch_name'], 'test-branch')
            self.assertEqual(data['fork_step'], 0)


if __name__ == '__main__':
    unittest.main()
