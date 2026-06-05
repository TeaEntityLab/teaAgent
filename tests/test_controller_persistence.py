"""Tests for ChatSessionController persistence error handling (P1-C).

Verifies that store save failures and undo save failures are logged as
classified warnings instead of being silently swallowed or crashing the
controller.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from teaagent.chat_session_controller import ChatSessionController, SessionState
from teaagent.runner._types import FinalAnswer, RunResult


def _make_store_mock_factory(failing_method: str, exc: Exception):
    """Build a _store_factory that returns a store mock with a failing method."""

    def factory():
        store = MagicMock()
        store.audit_logger.return_value = MagicMock()
        store.logger_for_result = MagicMock()
        store.undo_path.return_value = Path(tempfile.mkdtemp()) / 'undo.jsonl'
        getattr(store, failing_method).side_effect = exc
        return store

    return factory


def _make_success_result() -> RunResult:
    return RunResult(
        run_id='test-run-persist',
        final_answer=FinalAnswer(content='answer'),
        iterations=1,
        tool_calls=0,
        status='completed',
        cost_cents=5.0,
        input_tokens=50,
        output_tokens=25,
    )


class TestStoreSaveFailure:
    """P1-C-002: Store save failure produces classified warning log."""

    def test_store_logger_for_result_oserror_is_logged(self, caplog):
        """OSError from RunStore.logger_for_result should emit a warning, not crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_messages: list[str] = []

            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda msg: output_messages.append(msg),
                _store_factory=_make_store_mock_factory(
                    'logger_for_result', OSError('disk full')
                ),
            )

            # Create an audit logger with a valid path so the save path is entered
            audit = MagicMock()
            audit.path = Path(tmpdir) / 'audit.jsonl'
            audit.add_sink = MagicMock()

            # Mock undo journal — no entries, so undo save is skipped
            undo_journal = MagicMock()
            undo_journal.has_entries = False

            mock_config = MagicMock()
            mock_config.model = 'gpt/gpt-4'

            with patch('teaagent.chat_session_controller.run_chat_agent') as mock_run:
                mock_run.return_value = _make_success_result()

                with caplog.at_level(logging.WARNING):
                    result = controller.execute_task(
                        'test task',
                        config=mock_config,
                        adapter=None,
                        audit=audit,
                        undo_journal=undo_journal,
                    )

            # Controller should NOT crash — ExecutionResult is returned
            assert result.run_result.status == 'completed'
            assert result.cost_cents == 5.0
            # Warning should be logged
            assert any(
                'Persistence failure: could not save run result to store'
                in record.message
                for record in caplog.records
            )
            # Answer should still be printed
            assert 'answer' in output_messages

    def test_store_logger_for_result_runtimeerror_is_logged(self, caplog):
        """RuntimeError (e.g. readonly mode) should emit a warning, not crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_messages: list[str] = []

            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda msg: output_messages.append(msg),
                _store_factory=_make_store_mock_factory(
                    'logger_for_result',
                    RuntimeError('Cannot persist logger result in readonly mode'),
                ),
            )

            audit = MagicMock()
            audit.path = Path(tmpdir) / 'audit.jsonl'
            audit.add_sink = MagicMock()

            undo_journal = MagicMock()
            undo_journal.has_entries = False

            mock_config = MagicMock()
            mock_config.model = 'gpt/gpt-4'

            with patch('teaagent.chat_session_controller.run_chat_agent') as mock_run:
                mock_run.return_value = _make_success_result()

                with caplog.at_level(logging.WARNING):
                    result = controller.execute_task(
                        'test task',
                        config=mock_config,
                        adapter=None,
                        audit=audit,
                        undo_journal=undo_journal,
                    )

            assert result.run_result.status == 'completed'
            assert any(
                'Persistence failure: could not save run result to store'
                in record.message
                for record in caplog.records
            )


class TestUndoSaveFailure:
    """P1-C-002: Undo journal save failure produces classified warning log."""

    def test_undo_journal_save_oserror_is_logged(self, caplog):
        """OSError from UndoJournal.save_to should emit a warning, not crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_messages: list[str] = []

            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda msg: output_messages.append(msg),
            )

            audit = MagicMock()
            audit.path = Path(tmpdir) / 'audit.jsonl'
            audit.add_sink = MagicMock()

            # Journal with entries that will fail on save
            undo_journal = MagicMock()
            undo_journal.has_entries = True
            undo_journal.save_to.side_effect = OSError('disk full')

            mock_config = MagicMock()
            mock_config.model = 'gpt/gpt-4'

            with (
                patch('teaagent.chat_session_controller.RunStore') as mock_store_cls,
                patch('teaagent.chat_session_controller.run_chat_agent') as mock_run,
            ):
                mock_store = MagicMock()
                mock_store_cls.return_value = mock_store
                mock_store.logger_for_result = MagicMock()
                mock_store.undo_path.return_value = Path(tmpdir) / 'undo.jsonl'

                mock_run.return_value = _make_success_result()

                with caplog.at_level(logging.WARNING):
                    result = controller.execute_task(
                        'test task',
                        config=mock_config,
                        adapter=None,
                        audit=audit,
                        undo_journal=undo_journal,
                    )

            assert result.run_result.status == 'completed'
            assert any(
                'Persistence failure: could not save undo journal' in record.message
                for record in caplog.records
            )

    def test_undo_journal_save_runtimeerror_is_logged(self, caplog):
        """RuntimeError from UndoJournal.save_to should emit a warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_messages: list[str] = []

            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda msg: output_messages.append(msg),
            )

            audit = MagicMock()
            audit.path = Path(tmpdir) / 'audit.jsonl'
            audit.add_sink = MagicMock()

            undo_journal = MagicMock()
            undo_journal.has_entries = True
            undo_journal.save_to.side_effect = RuntimeError('readonly store')

            mock_config = MagicMock()
            mock_config.model = 'gpt/gpt-4'

            with (
                patch('teaagent.chat_session_controller.RunStore') as mock_store_cls,
                patch('teaagent.chat_session_controller.run_chat_agent') as mock_run,
            ):
                mock_store = MagicMock()
                mock_store_cls.return_value = mock_store
                mock_store.logger_for_result = MagicMock()
                mock_store.undo_path.return_value = Path(tmpdir) / 'undo.jsonl'

                mock_run.return_value = _make_success_result()

                with caplog.at_level(logging.WARNING):
                    result = controller.execute_task(
                        'test task',
                        config=mock_config,
                        adapter=None,
                        audit=audit,
                        undo_journal=undo_journal,
                    )

            assert result.run_result.status == 'completed'
            assert any(
                'Persistence failure: could not save undo journal' in record.message
                for record in caplog.records
            )


class TestStoreSaveAttributeErrorStillPropagates:
    """P1-C-002: Non-OSError exceptions from store/undo still propagate."""

    def test_undo_journal_attributeerror_still_propagates(self):
        """AttributeError from UndoJournal.save_to should propagate (not swallowed)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_messages: list[str] = []

            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda msg: output_messages.append(msg),
                session_state=SessionState(),
            )

            bad_journal = MagicMock()
            bad_journal.has_entries = True
            bad_journal.save_to.side_effect = AttributeError('injected: bad attr')

            audit = MagicMock()
            audit.path = Path(tmpdir) / 'audit.jsonl'
            audit.add_sink = MagicMock()

            mock_config = MagicMock()
            mock_config.model = 'gpt/gpt-4'

            with (
                patch('teaagent.chat_session_controller.RunStore') as mock_store_cls,
                patch('teaagent.chat_session_controller.run_chat_agent') as mock_run,
            ):
                mock_store = MagicMock()
                mock_store_cls.return_value = mock_store
                mock_store.logger_for_result = MagicMock()
                mock_store.undo_path.return_value = Path(tmpdir) / 'undo.jsonl'

                mock_run.return_value = _make_success_result()

                with pytest.raises(AttributeError, match='injected'):
                    controller.execute_task(
                        'test task',
                        config=mock_config,
                        adapter=None,
                        audit=audit,
                        undo_journal=bad_journal,
                    )


class TestUndoLastRunPersistence:
    """P1-C-002: undo_last_run error handling is specific and logged."""

    def test_undo_last_run_oserror_is_logged(self, caplog):
        """OSError in undo_last_run should log warning and return False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_messages: list[str] = []

            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda msg: output_messages.append(msg),
            )

            with patch('teaagent.chat_session_controller.RunStore') as mock_store_cls:
                mock_store = MagicMock()
                mock_store_cls.return_value = mock_store
                mock_store.latest_run_with_undo.side_effect = OSError(
                    'permission denied'
                )

                with caplog.at_level(logging.WARNING):
                    result = controller.undo_last_run()

            assert result is False
            assert any(
                'Undo persistence failure' in record.message
                for record in caplog.records
            )
            assert any('journal undo error' in msg for msg in output_messages)

    def test_undo_last_run_valueerror_is_logged(self, caplog):
        """ValueError in undo_last_run should log warning and return False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_messages: list[str] = []

            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda msg: output_messages.append(msg),
            )

            with patch('teaagent.chat_session_controller.RunStore') as mock_store_cls:
                mock_store = MagicMock()
                mock_store_cls.return_value = mock_store
                mock_store.latest_run_with_undo.side_effect = ValueError(
                    'invalid state'
                )

                with caplog.at_level(logging.WARNING):
                    result = controller.undo_last_run()

            assert result is False
            assert any(
                'Undo persistence failure' in record.message
                for record in caplog.records
            )


class TestStoreFactorySeam:
    """P1-C-002: The _store_factory mocking seam works correctly."""

    def test_store_factory_is_used_when_provided(self):
        """When _store_factory is set, _create_store uses it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            factory_called = [0]

            def my_factory():
                factory_called[0] += 1
                return MagicMock()

            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda _: None,
                _store_factory=my_factory,
            )

            store1 = controller._create_store()
            store2 = controller._create_store()

            assert factory_called[0] == 2
            assert store1 is not store2  # Each call creates a new store

    def test_default_store_without_factory(self):
        """Without _store_factory, _create_store uses real RunStore."""
        with tempfile.TemporaryDirectory() as tmpdir:
            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda _: None,
            )

            store = controller._create_store()

            from teaagent.run_store import RunStore

            assert isinstance(store, RunStore)
            assert store.root == Path(tmpdir).resolve()
