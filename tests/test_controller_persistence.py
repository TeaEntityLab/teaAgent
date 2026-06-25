"""Tests for ChatSessionController persistence error handling (P1-C).

Verifies that store save failures and undo save failures are logged as
classified warnings instead of being silently swallowed or crashing the
controller.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from conftest import FakeAdapter

from teaagent.chat_agent import ChatAgentConfig
from teaagent.chat_session_controller import ChatSessionController, SessionState
from teaagent.run_store import RunStore
from teaagent.run_undo import UndoJournal
from teaagent.runner._types import RunResult


def _allow_config(root: str | Path) -> ChatAgentConfig:
    return ChatAgentConfig.from_root(
        root,
        model='fake/fake-model',
        permission_mode='allow',
        max_iterations=5,
        max_tool_calls=5,
    )


def _success_adapter() -> FakeAdapter:
    return FakeAdapter(['{"type":"final","content":"answer"}'])


def _write_then_final_adapter() -> FakeAdapter:
    return FakeAdapter(
        [
            (
                '{"type":"tool","tool_name":"workspace_write_file",'
                '"arguments":{"path":"notes.txt","content":"after\\n"},'
                '"call_id":"write-existing"}'
            ),
            '{"type":"final","content":"writes complete"}',
        ]
    )


class _FailingRunStore(RunStore):
    """RunStore stub that injects persistence failures for one method."""

    def __init__(self, root: str | Path, *, exc: Exception) -> None:
        super().__init__(root)
        self._exc = exc

    def logger_for_result(self, result, audit) -> None:  # noqa: ANN001
        raise self._exc

    def latest_run_with_undo(self) -> str | None:
        raise self._exc


class _FailingUndoJournal(UndoJournal):
    """UndoJournal stub that fails on save_to."""

    def __init__(self, root: str | Path, *, exc: Exception) -> None:
        super().__init__(root)
        self._exc = exc

    def save_to(self, path: str | Path) -> None:
        raise self._exc


class _BrokenUndoJournal(UndoJournal):
    """UndoJournal stub that always has entries and raises AttributeError on save."""

    @property
    def has_entries(self) -> bool:
        return True

    def save_to(self, path: str | Path) -> None:
        raise AttributeError('injected: bad attr')


class TestStoreSaveFailure:
    """P1-C-002: Store save failure produces classified warning log."""

    def test_store_logger_for_result_oserror_is_logged(self, caplog) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_messages: list[str] = []
            store = RunStore(tmpdir)
            audit = store.audit_logger()

            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda msg: output_messages.append(msg),
                _store_factory=lambda: _FailingRunStore(
                    tmpdir, exc=OSError('disk full')
                ),
            )

            with caplog.at_level(logging.WARNING):
                result = controller.execute_task(
                    'test task',
                    _allow_config(tmpdir),
                    adapter=_success_adapter(),
                    audit=audit,
                )

            assert result.run_result.status == 'completed'
            assert result.run_result.final_answer is not None
            assert result.run_result.final_answer.content == 'answer'
            assert any(
                'Persistence failure: could not save run result to store'
                in record.message
                for record in caplog.records
            )
            assert 'answer' in output_messages

    def test_store_logger_for_result_runtimeerror_is_logged(self, caplog) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_messages: list[str] = []
            store = RunStore(tmpdir)
            audit = store.audit_logger()

            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda msg: output_messages.append(msg),
                _store_factory=lambda: _FailingRunStore(
                    tmpdir,
                    exc=RuntimeError('Cannot persist logger result in readonly mode'),
                ),
            )

            with caplog.at_level(logging.WARNING):
                result = controller.execute_task(
                    'test task',
                    _allow_config(tmpdir),
                    adapter=_success_adapter(),
                    audit=audit,
                )

            assert result.run_result.status == 'completed'
            assert any(
                'Persistence failure: could not save run result to store'
                in record.message
                for record in caplog.records
            )


class TestUndoSaveFailure:
    """P1-C-002: Undo journal save failure produces classified warning log."""

    def test_undo_journal_save_oserror_is_logged(self, caplog) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_messages: list[str] = []
            store = RunStore(tmpdir)
            audit = store.audit_logger()
            journal = _FailingUndoJournal(tmpdir, exc=OSError('disk full'))
            audit.add_sink(journal)

            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda msg: output_messages.append(msg),
            )

            with caplog.at_level(logging.WARNING):
                result = controller.execute_task(
                    'test task',
                    _allow_config(tmpdir),
                    adapter=_write_then_final_adapter(),
                    audit=audit,
                    undo_journal=journal,
                )

            assert result.run_result.status == 'completed'
            assert any(
                'Persistence failure: could not save undo journal' in record.message
                for record in caplog.records
            )

    def test_undo_journal_save_runtimeerror_is_logged(self, caplog) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_messages: list[str] = []
            store = RunStore(tmpdir)
            audit = store.audit_logger()
            journal = _FailingUndoJournal(tmpdir, exc=RuntimeError('readonly store'))
            audit.add_sink(journal)

            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda msg: output_messages.append(msg),
            )

            with caplog.at_level(logging.WARNING):
                result = controller.execute_task(
                    'test task',
                    _allow_config(tmpdir),
                    adapter=_write_then_final_adapter(),
                    audit=audit,
                    undo_journal=journal,
                )

            assert result.run_result.status == 'completed'
            assert any(
                'Persistence failure: could not save undo journal' in record.message
                for record in caplog.records
            )


class TestStoreSaveAttributeErrorStillPropagates:
    """P1-C-002: Non-OSError exceptions from store/undo still propagate."""

    def test_undo_journal_attributeerror_still_propagates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_messages: list[str] = []
            store = RunStore(tmpdir)
            audit = store.audit_logger()
            journal = _BrokenUndoJournal(tmpdir)
            audit.add_sink(journal)

            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda msg: output_messages.append(msg),
                session_state=SessionState(),
            )

            with pytest.raises(AttributeError, match='injected'):
                controller.execute_task(
                    'test task',
                    _allow_config(tmpdir),
                    adapter=_write_then_final_adapter(),
                    audit=audit,
                    undo_journal=journal,
                )


class TestUndoLastRunPersistence:
    """P1-C-002: undo_last_run error handling is specific and logged."""

    def test_undo_last_run_oserror_is_logged(self, caplog) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_messages: list[str] = []

            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda msg: output_messages.append(msg),
                _store_factory=lambda: _FailingRunStore(
                    tmpdir, exc=OSError('permission denied')
                ),
            )

            with caplog.at_level(logging.WARNING):
                result = controller.undo_last_run()

            assert result is False
            assert any(
                'Undo persistence failure' in record.message
                for record in caplog.records
            )
            assert any('journal undo error' in msg for msg in output_messages)

    def test_undo_last_run_valueerror_is_logged(self, caplog) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_messages: list[str] = []

            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda msg: output_messages.append(msg),
                _store_factory=lambda: _FailingRunStore(
                    tmpdir, exc=ValueError('invalid state')
                ),
            )

            with caplog.at_level(logging.WARNING):
                result = controller.undo_last_run()

            assert result is False
            assert any(
                'Undo persistence failure' in record.message
                for record in caplog.records
            )


class TestStoreFactorySeam:
    """P1-C-002: The _store_factory seam works correctly."""

    def test_store_factory_is_used_when_provided(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            factory_called = [0]

            def my_factory() -> RunStore:
                factory_called[0] += 1
                return RunStore(tmpdir)

            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda _: None,
                _store_factory=my_factory,
            )

            store1 = controller._create_store()
            store2 = controller._create_store()

            assert factory_called[0] == 2
            assert store1 is not store2

    def test_default_store_without_factory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda _: None,
            )

            store = controller._create_store()

            assert isinstance(store, RunStore)
            assert store.root == Path(tmpdir).resolve()

    def test_execute_task_uses_store_factory_when_audit_missing(self) -> None:
        """RISK-2: audit bootstrap must use _create_store(), not RunStore() directly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            factory_called = [0]

            def my_factory() -> RunStore:
                factory_called[0] += 1
                return RunStore(tmpdir)

            controller = ChatSessionController(
                root=tmpdir,
                output_fn=lambda _: None,
                _store_factory=my_factory,
            )
            config = _allow_config(tmpdir)
            with patch(
                'teaagent.chat_session_controller.run_chat_agent',
                return_value=RunResult(
                    run_id='factory-audit-run',
                    status='completed',
                    iterations=1,
                    tool_calls=0,
                    cost_cents=0.0,
                    input_tokens=1,
                    output_tokens=1,
                    final_answer=None,
                    metadata={},
                    error_message=None,
                ),
            ):
                controller.execute_task('task', config, adapter=_success_adapter())

            assert factory_called[0] >= 1
