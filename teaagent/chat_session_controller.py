"""Shared chat session controller for CLI and TUI surfaces.

This module provides ChatSessionController, a unified controller that both
CLI and TUI surfaces can use to execute chat agent tasks with consistent behavior
(CG-01 result handling, CG-02 undo, CG-03 cost tracking, CG-09/CG-10 suspension).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from teaagent.audit import AuditLogger
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.llm import create_llm_adapter
from teaagent.run_store import RunStore
from teaagent.run_undo import UndoJournal
from teaagent.runner._types import RunResult

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """Shared session state across CLI and TUI surfaces."""

    session_cost_cents: float = 0.0
    observations: list[dict[str, Any]] = field(default_factory=list)
    compaction_count: int = 0
    targeted_files: set[Path] = field(default_factory=set)


@dataclass
class ExecutionResult:
    """Result from executing a task through the controller."""

    run_result: RunResult
    cost_cents: float
    observations_updated: bool = True


class ChatSessionController:
    """Shared controller for chat session execution.

    This controller unifies the execution logic between CLI and TUI surfaces,
    ensuring consistent behavior for:
    - CG-01: Result handling (answer on success, error on failure)
    - CG-02: Undo via UndoJournal
    - CG-03: Real cost tracking
    - CG-09/CG-10: Suspension honesty and audit

    Usage:
        controller = ChatSessionController(
            root=workspace_root,
            output_fn=print,  # or TUI's self.output_fn
        )
        result = controller.execute_task(task, config)
    """

    def __init__(
        self,
        root: str | Path,
        *,
        output_fn: Callable[[str], None],
        session_state: Optional[SessionState] = None,
        _store_factory: Optional[Callable[[], RunStore]] = None,
    ):
        """Initialize the controller.

        Args:
            root: Workspace root directory
            output_fn: Function to output messages (print for CLI, self.output_fn for TUI)
            session_state: Optional shared session state
            _store_factory: Optional factory for RunStore (test seam)
        """
        self.root = Path(root).resolve()
        self.output_fn = output_fn
        self.session_state = session_state or SessionState()
        self._store_factory = _store_factory

    def _create_store(self) -> RunStore:
        """Create a RunStore instance (uses factory if set, else default).

        This is a test/mocking seam. Tests can inject a _store_factory that
        returns a mock or a specially configured store to simulate failures.
        """
        if self._store_factory is not None:
            return self._store_factory()
        return RunStore(self.root)

    def execute_task(
        self,
        task: str,
        config: ChatAgentConfig,
        *,
        adapter: Optional[Any] = None,
        audit: Optional[AuditLogger] = None,
        undo_journal: Optional[UndoJournal] = None,
        initial_observations: Optional[list[dict[str, Any]]] = None,
        initial_context_extra: Optional[dict[str, Any]] = None,
        resumed_from: Optional[str] = None,
        task_spec: Optional[Any] = None,
        emit_answer: bool = True,
    ) -> ExecutionResult:
        """Execute a chat agent task with consistent behavior.

        This method:
        1. Sets up audit and undo journal if not provided
        2. Runs the chat agent
        3. Saves undo journal if it has entries
        4. Handles result display (CG-01)
        5. Updates session state with cost and observations (CG-03)

        Args:
            task: The task to execute
            config: Chat agent configuration
            adapter: Optional LLM adapter (created from config if not provided)
            audit: Optional audit logger (created from RunStore if not provided)
            undo_journal: Optional undo journal (created if not provided)
            initial_observations: Optional initial observations
            resumed_from: Optional run_id if resuming
            task_spec: Optional task specification from clarification
            emit_answer: Whether to print the final answer/error to the output stream

        Returns:
            ExecutionResult with the run result and cost
        """
        # Set up audit and undo journal if not provided
        if audit is None:
            store = self._create_store()
            audit = store.audit_logger()
        if undo_journal is None:
            undo_journal = UndoJournal(self.root)
            audit.add_sink(undo_journal)

        # Create adapter if not provided
        if adapter is None:
            provider = (
                config.model.split('/')[0]
                if config.model and '/' in config.model
                else 'gpt'
            )
            model_part = (
                config.model.split('/', 1)[1]
                if config.model and '/' in config.model
                else None
            )
            adapter = create_llm_adapter(provider, model=model_part)

        # Run the agent
        merged_context_extra: dict[str, Any] | None = None
        if initial_context_extra or resumed_from:
            merged_context_extra = dict(initial_context_extra or {})
            if resumed_from:
                merged_context_extra['resumed_from'] = resumed_from

        result = run_chat_agent(
            config,
            task,
            adapter=adapter,
            audit=audit,
            task_spec=task_spec,
            initial_observations=initial_observations,
            initial_context_extra=merged_context_extra,
        )

        # Save result to store
        store = self._create_store()
        if (
            audit
            and hasattr(audit, 'path')
            and isinstance(audit.path, Path)
            and audit.path
        ):
            try:
                store.logger_for_result(result, audit)
            except (OSError, RuntimeError) as exc:
                logger.warning(
                    'Persistence failure: could not save run result to store '
                    '(run_id=%s): %s',
                    result.run_id,
                    exc,
                )

        # Save undo journal if it has entries
        if undo_journal.has_entries:
            try:
                undo_journal.save_to(store.undo_path(result.run_id))
            except (OSError, RuntimeError) as exc:
                logger.warning(
                    'Persistence failure: could not save undo journal (run_id=%s): %s',
                    result.run_id,
                    exc,
                )

        # Handle result display (CG-01)
        if emit_answer:
            if result.status == 'completed' and result.final_answer:
                self.output_fn(result.final_answer.content)
            else:
                self.output_fn(result.error_message or f'[{result.status}]')

        # Update session state (CG-03)
        self.session_state.session_cost_cents += result.cost_cents
        self.session_state.observations.append(
            {
                'task': task,
                'result': result,
                'cost_cents': result.cost_cents,
            }
        )

        return ExecutionResult(
            run_result=result,
            cost_cents=result.cost_cents,
        )

    def undo_last_run(self) -> bool:
        """Undo the last run using UndoJournal (CG-02).

        Returns:
            True if undo succeeded, False otherwise
        """
        try:
            store = self._create_store()
            run_id = store.latest_run_with_undo()
            if run_id is None:
                self.output_fn('[TeaAgent] Nothing to undo - no undo journal found')
                return False

            undo_path = store.undo_path(run_id)
            if not undo_path.is_file():
                self.output_fn(f'[TeaAgent] No undo journal for run {run_id}')
                return False

            journal = UndoJournal(self.root, path=undo_path)
            result = journal.restore()

            if result.ok:
                self.output_fn(
                    f'[TeaAgent] journal undo completed: restored {len(result.restored)} file(s)'
                )
                if result.deleted:
                    self.output_fn(
                        f'[TeaAgent] journal undo: deleted {len(result.deleted)} file(s)'
                    )
                undo_path.unlink(missing_ok=True)
                return True
            else:
                self.output_fn(
                    f'[TeaAgent] journal undo partially completed: {len(result.errors)} error(s)'
                )
                for error in result.errors:
                    self.output_fn(f'  - {error}')
                return False
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning('Undo persistence failure: %s', exc)
            self.output_fn(f'[TeaAgent] journal undo error: {exc}')
            return False

    def get_session_cost(self) -> float:
        """Get the current session cost in cents (CG-03)."""
        return self.session_state.session_cost_cents

    def get_session_cost_display(self) -> str:
        """Get the session cost formatted as USD."""
        return f'${self.session_state.session_cost_cents / 100:.2f}'
