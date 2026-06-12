"""Command execution abstraction layer between CLI and core.

This module provides interfaces and factories to decouple CLI handlers from
direct core component instantiation, enabling better testability and separation
of concerns.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.code_analysis import CodeAnalysisConfig
from teaagent.ergonomics.background_run import BackgroundRunStore
from teaagent.run_store import RunStore
from teaagent.run_undo import UndoJournal
from teaagent.runner import ApprovalHandler, RunResult
from teaagent.sandbox import GitBranchSandbox, GitTransactionSink
from teaagent.types import AuditLogger, PermissionMode


@dataclass
class ExecutionContext:
    """Context for executing an agent task."""

    task: str
    root: Path
    adapter: Any  # LLMAdapter
    config: ChatAgentConfig
    audit: AuditLogger
    store: RunStore
    git_sandbox: Optional[GitBranchSandbox] = None
    undo_journal: Optional[UndoJournal] = None
    git_transaction_sink: Optional[GitTransactionSink] = None
    telemetry_sink: Optional[Any] = None
    task_spec: Optional[str] = None
    initial_observations: Optional[list[dict[str, Any]]] = None
    initial_context_extra: Optional[dict[str, Any]] = None
    plan_contract: Optional[Any] = None


class CommandExecutor(ABC):
    """Interface for executing agent commands."""

    @abstractmethod
    def execute(self, context: ExecutionContext) -> RunResult:
        """Execute the agent task with the given context."""
        # Abstract method: implementation provided by subclasses


def extract_tenant_id_from_argv() -> str:
    import sys

    for i, arg in enumerate(sys.argv):
        if arg == '--tenant-id':
            if i + 1 < len(sys.argv):
                return sys.argv[i + 1]
        elif arg.startswith('--tenant-id='):
            return arg.split('=', 1)[1]
    return 'default'


class AgentExecutionFactory:
    """Factory for constructing agent execution components.

    This factory encapsulates the complex construction logic for creating
    the various components needed to run an agent task, keeping CLI handlers
    clean and focused on argument parsing and user interaction.
    """

    def __init__(self, root: Path | str, tenant_id: Optional[str] = None):
        self.root = Path(root).resolve()
        if tenant_id is None:
            tenant_id = extract_tenant_id_from_argv()
        self.tenant_id = tenant_id

    def create_run_store(self, readonly: bool = False) -> RunStore:
        """Create a RunStore instance."""
        return RunStore(self.root, tenant_id=self.tenant_id, readonly=readonly)

    def create_audit_logger(
        self, store: RunStore, run_id: Optional[str] = None
    ) -> AuditLogger:
        """Create an AuditLogger instance."""
        if run_id:
            return store.audit_logger(run_id)
        return store.audit_logger()

    def create_git_sandbox(self, run_id: str = 'pending') -> GitBranchSandbox:
        """Create a GitBranchSandbox instance."""
        return GitBranchSandbox(self.root, run_id=run_id)

    def create_undo_journal(self, path: Optional[Path] = None) -> UndoJournal:
        """Create an UndoJournal instance."""
        return UndoJournal(self.root, path=path)

    def create_git_transaction_sink(
        self, git_sandbox: GitBranchSandbox
    ) -> GitTransactionSink:
        """Create a GitTransactionSink instance."""
        return GitTransactionSink(git_sandbox)

    def create_background_run_store(self, readonly: bool = False) -> BackgroundRunStore:
        """Create a BackgroundRunStore instance."""
        return BackgroundRunStore(
            self.root, tenant_id=self.tenant_id, readonly=readonly
        )

    @staticmethod
    def create_audit_logger_from_path(path: Path) -> AuditLogger:
        """Create an AuditLogger instance from a file path."""
        return AuditLogger(path=path)

    def create_chat_agent_config(
        self,
        max_iterations: int = 10,
        max_tool_calls: int = 10,
        max_estimated_cost_cents: int | None = 500,
        allow_destructive: bool = False,
        model: Optional[str] = None,
        permission_mode: PermissionMode = PermissionMode.PROMPT,
        approved_call_ids: frozenset[str] = frozenset(),
        approved_payload_digests: frozenset[str] = frozenset(),
        enable_subagent: bool = False,
        max_subagent_depth: int = 1,
        heartbeat_seconds: float = 0.0,
        approval_handler: Optional[ApprovalHandler] = None,
        budget_prompt_handler: Any = None,
        checkpoint_store: Any = None,
        stream: bool = False,
        on_chunk: Optional[Any] = None,
        stream_text_only: bool = True,
        code_analysis_config: Optional[CodeAnalysisConfig] = None,
        selected_skills: Optional[frozenset[str]] = None,
        skill_prompt_mode: str = 'eager',
        require_plan: bool = False,
        skip_plan_check: bool = False,
        validation_profile: Optional[str] = None,
    ) -> ChatAgentConfig:
        """Create a ChatAgentConfig instance."""
        return ChatAgentConfig.from_root(
            self.root,
            max_iterations=max_iterations,
            max_tool_calls=max_tool_calls,
            max_estimated_cost_cents=max_estimated_cost_cents,
            allow_destructive=allow_destructive,
            model=model,
            permission_mode=permission_mode,
            approved_call_ids=approved_call_ids,
            approved_payload_digests=approved_payload_digests,
            enable_subagent=enable_subagent,
            max_subagent_depth=max_subagent_depth,
            heartbeat_seconds=heartbeat_seconds,
            approval_handler=approval_handler,
            budget_prompt_handler=budget_prompt_handler,
            checkpoint_store=checkpoint_store,
            stream=stream,
            on_chunk=on_chunk,
            stream_text_only=stream_text_only,
            code_analysis_config=code_analysis_config,
            selected_skills=selected_skills,
            skill_prompt_mode=skill_prompt_mode,
            require_plan=require_plan,
            skip_plan_check=skip_plan_check,
            validation_profile=validation_profile,
        )

    def create_execution_context(
        self,
        task: str,
        adapter: Any,
        config: ChatAgentConfig,
        audit: AuditLogger,
        store: RunStore,
        git_sandbox: Optional[GitBranchSandbox] = None,
        undo_journal: Optional[UndoJournal] = None,
        git_transaction_sink: Optional[GitTransactionSink] = None,
        telemetry_sink: Optional[Any] = None,
        task_spec: Optional[str] = None,
        initial_observations: Optional[list[dict[str, Any]]] = None,
        initial_context_extra: Optional[dict[str, Any]] = None,
        plan_contract: Optional[Any] = None,
    ) -> ExecutionContext:
        """Create an ExecutionContext instance."""
        return ExecutionContext(
            task=task,
            root=self.root,
            adapter=adapter,
            config=config,
            audit=audit,
            store=store,
            git_sandbox=git_sandbox,
            undo_journal=undo_journal,
            git_transaction_sink=git_transaction_sink,
            telemetry_sink=telemetry_sink,
            task_spec=task_spec,
            initial_observations=initial_observations,
            initial_context_extra=initial_context_extra,
            plan_contract=plan_contract,
        )


class DefaultCommandExecutor(CommandExecutor):
    """Default implementation of CommandExecutor for running chat agents."""

    def execute(self, context: ExecutionContext) -> RunResult:
        """Execute the agent task using run_chat_agent."""
        # Add undo journal to audit if present
        if context.undo_journal is not None:
            context.audit.add_sink(context.undo_journal)

        # Add git transaction sink to audit if present
        if context.git_transaction_sink is not None:
            context.audit.add_sink(context.git_transaction_sink)

        # Add telemetry sink to audit if present
        if context.telemetry_sink is not None:
            context.audit.add_sink(context.telemetry_sink.handle_event)

        # Execute the agent
        result = run_chat_agent(
            context.config,
            context.task,
            adapter=context.adapter,
            audit=context.audit,
            task_spec=context.task_spec,
            initial_observations=context.initial_observations,
            initial_context_extra=context.initial_context_extra,
        )

        # Save undo journal if it has entries
        if context.undo_journal is not None and context.undo_journal.has_entries:
            context.undo_journal.save_to(context.store.undo_path(result.run_id))

        # Log the result
        context.store.logger_for_result(result, context.audit)

        return result
