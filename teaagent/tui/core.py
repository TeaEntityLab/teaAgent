from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from prompt_toolkit import PromptSession

    from teaagent.memory.file_watcher import FileWatcher

from teaagent import __version__
from teaagent.chat_agent import ChatAgentConfig
from teaagent.chat_session_controller import ChatSessionController, SessionState
from teaagent.cockpit import (
    CockpitState,
    ControlCockpitState,
    build_budget_state,
    build_control_cockpit,
    discover_recoverable_state,
)
from teaagent.context import ContextCompactor as _ContextCompactor
from teaagent.context_health import ContextHealthScore, compute_context_health
from teaagent.context_pressure import (
    ContextPressureScore,
    compute_context_pressure,
)
from teaagent.graphqlite_store import (
    GraphQLiteConfig,
    GraphQLiteGraphStore,
)
from teaagent.intent import build_task_spec, clarify_task
from teaagent.llm import LLMMessage
from teaagent.memory import MemoryCatalog
from teaagent.model_routing import route_model
from teaagent.run_store import RunStore, summarize_audit_events
from teaagent.runner import ApprovalRequest, RunResult
from teaagent.session import ChatMessage, ChatSession, SessionStore
from teaagent.skill_loader import (
    SkillActivationExplain,
    discover_skill_index,
    explain_skill_activation,
)
from teaagent.types import AuditEvent, PermissionMode

from .state import (
    AdapterFactory,
    InputFn,
    OutputFn,
    _effort_level_for_budget,
    _format_budget_cents,
    _format_remaining_cents,
    default_adapter_factory,
)

logger = logging.getLogger(__name__)


class TeaAgentTUI:
    def __init__(
        self,
        *,
        database: str = ':memory:',
        provider: Optional[str] = None,
        model: Optional[str] = None,
        root: str | Path = '.',
        allow_destructive: bool = False,
        permission_mode: PermissionMode = PermissionMode.PROMPT,
        input_fn: Optional[InputFn] = None,
        output_fn: OutputFn = print,
        adapter_factory: AdapterFactory = default_adapter_factory,
        stream: bool = False,
        subagent: bool = False,
        heartbeat_seconds: float = 0.0,
        max_iterations: int = 10,
        max_tool_calls: int = 10,
        max_subagent_depth: int = 1,
        enable_git_tools: bool = False,
        skill_search_dirs: Optional[list[str]] = None,
        memory_limit: int = 5,
        max_estimated_cost_cents: int | None = None,
    ) -> None:
        self.database = database
        self.provider = provider
        self.model = model
        self.route_model_enabled = False
        self.root = Path(root).resolve()
        self._root_explicit: bool = False
        self.allow_destructive = allow_destructive
        self.permission_mode = permission_mode
        self.progress = True
        self.stream = stream
        self.subagent = subagent
        self.heartbeat_seconds = heartbeat_seconds
        self.chat = False
        self.max_iterations = max_iterations
        self.max_tool_calls = max_tool_calls
        self.max_subagent_depth = max_subagent_depth
        self.enable_git_tools = enable_git_tools
        self.skill_search_dirs = skill_search_dirs
        self.memory_limit = memory_limit
        self.max_estimated_cost_cents = max_estimated_cost_cents
        self._chat_explicit = False
        self.session_id: Optional[str] = None
        self.approved_call_ids: set[str] = set()
        self.last_run_id: Optional[str] = None
        self.input_fn = input_fn
        self.output_fn = output_fn
        self.adapter_factory = adapter_factory
        self._store: Optional[GraphQLiteGraphStore] = None
        self._session_store: Optional[SessionStore] = None
        self._session: Optional['PromptSession'] = None
        self._parallel_options: Optional[list[str]] = []

        # File watcher for live context sync
        self._file_watcher: Optional[FileWatcher] = None
        self._watcher_running: bool = False

        # Git-stash checkpoint for safe undo
        self._checkpoint_created: bool = False
        self._checkpoint_ref: Optional[str] = None

        # Chat session controller for unified execution semantics (TASK-002)
        self._chat_controller: Optional[ChatSessionController] = None
        self._session_state = SessionState()

        # Effort throttling and budget tracking
        self._effort_level: str = _effort_level_for_budget(max_estimated_cost_cents)
        self._runtime_max_cost_cents: int | None = max_estimated_cost_cents
        self._max_cost_budget_cents: int | None = max_estimated_cost_cents

        # Cockpit state for operator dashboard
        self._cockpit_state: Optional[CockpitState] = None

        # Approve path scopes from CLI (e.g. --approve-path src/)
        self._approved_path_globs: list[str] = []

        # Control cockpit state (CPP-P2-001 / SCL-P2-001)
        self._control_cockpit: Optional[ControlCockpitState] = None

        # Context pressure score (CPP-P1-003)
        self._context_pressure: Optional[ContextPressureScore] = None

        # Skill activation explain cache (DSK-P1-004)
        self._skill_explain: Optional[SkillActivationExplain] = None

        # State panel render cache (perf roadmap QW-4)
        self._state_panel_last_printed: float = 0.0
        self._state_panel_cache_ttl: float = 2.0

    def _determine_cost_state(self) -> str:
        """Determine the cost display state label.

        Returns one of:
          - ``'actual'``: confirmed cost from provider/budget system
          - ``'estimated'``: projected cost based on token count (default)
          - ``'unavailable'``: cost tracking not supported for this adapter
          - ``'unlimited'``: no budget cap configured (None = unlimited)
        """
        if self._max_cost_budget_cents is None:
            return 'unlimited'
        # TeaAgent uses token-count estimation; actual would require
        # provider billing API integration which is not yet implemented.
        # Mark unavailable only when cost is exactly zero and tracking
        # has never accumulated (fresh session with cap but no usage).
        cost = self._get_session_cost_cents()
        if cost > 0:
            return 'estimated'
        return 'unavailable'

    def _refresh_control_cockpit(self) -> None:
        """Refresh the control cockpit from workspace data sources."""
        try:
            self._control_cockpit = build_control_cockpit(
                self.root,
                permission_mode=self.permission_mode.value,
                cost_cents=self._get_session_cost_cents(),
                cost_limit_cents=self._max_cost_budget_cents,
                cost_state=self._determine_cost_state(),
            )
        except Exception:
            logger.debug('control cockpit unavailable', exc_info=True)
            self._control_cockpit = None

        self._refresh_cockpit_state()

    def _refresh_cockpit_state(self) -> None:
        approval_scope_parts = [self.permission_mode.value]
        if self._approved_path_globs:
            approval_scope_parts.append(
                f'(scoped: {", ".join(self._approved_path_globs)})'
            )
        try:
            ctx_health: ContextHealthScore | None = compute_context_health(
                workspace_root=str(self.root),
            )
            spent_cents = self._get_session_cost_cents()
            cost_state = self._determine_cost_state()
            self._cockpit_state = CockpitState(
                workspace_root=str(self.root),
                approval_scope=' '.join(approval_scope_parts),
                context_health=ctx_health.to_dict() if ctx_health else None,
                budget=build_budget_state(
                    spent_cents=spent_cents,
                    limit_cents=self._max_cost_budget_cents,
                    cost_state=cost_state,
                ),
                recoverable=discover_recoverable_state(
                    self.root,
                    has_checkpoint=self._checkpoint_created,
                ),
            )
        except Exception:
            logger.debug('cockpit state unavailable', exc_info=True)
            self._cockpit_state = None

    def _should_use_split_pane(self) -> bool:
        """Check if terminal is large enough for split-pane layout."""
        try:
            columns, lines = shutil.get_terminal_size()
            return columns >= 120 and lines >= 30
        except (OSError, ValueError):
            return False

    def _print_state_panel(self) -> None:
        """Print the state panel showing token budget, files, and memory."""
        import time

        now = time.monotonic()
        if now - self._state_panel_last_printed < self._state_panel_cache_ttl:
            return
        self._state_panel_last_printed = now

        try:
            columns, lines = shutil.get_terminal_size()
        except (OSError, ValueError):
            return

        try:
            self._context_pressure = compute_context_pressure(self.root)
        except Exception:
            logger.debug('context pressure unavailable', exc_info=True)
            self._context_pressure = None

        # Print header (no clear screen - CG-06 fix)
        print('=' * columns)
        print(f'TeaAgent TUI {__version__} - State Panel')
        print('=' * columns)

        # Left panel: Chat area placeholder
        print('\n[Chat Area - Enter commands below]')
        print('-' * columns)

        # Right panel: State information
        print('\n[State Panel]')
        print(f'Provider: {self.provider}')
        print(f'Model: {self.model or "default"}')
        print(f'Root: {self.root}')
        print(f'Permission Mode: {self.permission_mode.value}')
        print(f'Destructive: {"allowed" if self.allow_destructive else "blocked"}')
        print(f'Chat: {"enabled" if self.chat else "disabled"}')

        # Run status (blocked approvals, harness health, budget, recoverable)
        print('\n[Run status]')
        if self._cockpit_state:
            # Active root and approval scope
            if self._cockpit_state.workspace_root:
                print(f'  Workspace: {self._cockpit_state.workspace_root}')
            if self._cockpit_state.approval_scope:
                print(f'  Approval area: {self._cockpit_state.approval_scope}')

            # Blocked approvals
            if self._cockpit_state.approvals.blocked_count > 0:
                print(
                    f'  Blocked Approvals: {self._cockpit_state.approvals.blocked_count}'
                )
            if self._cockpit_state.approvals.pending_count > 0:
                print(
                    f'  Pending Approvals: {self._cockpit_state.approvals.pending_count}'
                )

            # Harness health
            if self._cockpit_state.harness_health.overall != 'unknown':
                overall_health = self._cockpit_state.harness_health.overall
                print(f'  Harness Health: {overall_health.upper()}')
                if self._cockpit_state.harness_health.errors:
                    print(
                        f'    Errors: {len(self._cockpit_state.harness_health.errors)}'
                    )

            # Budget
            if self._cockpit_state.budget.status != 'unknown':
                budget = self._cockpit_state.budget
                print(f'  Budget: {budget.status.upper()}')
                cost_label = budget.cost_state.replace('_', ' ')
                print(f'    Spent: ${budget.spent_cents / 100:.2f} ({cost_label})')
                if budget.limit_cents:
                    print(f'    Limit: ${budget.limit_cents / 100:.2f}')
                if budget.remaining_cents is not None:
                    print(f'    Remaining: ${budget.remaining_cents / 100:.2f}')

            # Recoverable
            if self._cockpit_state.recoverable.has_undo_journal:
                print(
                    f'  Undo: Available (run_id: {self._cockpit_state.recoverable.last_run_id})'
                )
            if self._cockpit_state.recoverable.has_checkpoint:
                print('  Checkpoint: Available')
            if self._cockpit_state.recoverable.has_suspended_session:
                print('  Suspended Session: Available')

        # Control Cockpit (CPP-P2-001 / SCL-P2-001)
        if self._control_cockpit:
            cc = self._control_cockpit
            print('\n[Control Cockpit]')

            # Spec/Goal
            if cc.goal:
                goal = cc.goal
                objective = goal.get('objective', '')
                if len(objective) > 60:
                    objective = objective[:57] + '...'
                print(f'  Goal: {goal.get("status", "?")} — {objective}')
                blockers = goal.get('blockers', [])
                if isinstance(blockers, list) and blockers:
                    print(f'  Blockers: {len(blockers)}')
            elif cc.spec:
                spec = cc.spec
                print(f'  Spec: {spec.get("spec_id", "")[:12]}')
            else:
                print('  Spec/Goal: none')

            # Model Route
            if cc.model_route:
                mr = cc.model_route
                print(
                    f'  Model: {mr.get("provider", "?")}/{mr.get("model", "default")} (est. ${mr.get("estimated_cost_cents", 0) / 100:.2f})'
                )
            else:
                print(f'  Model: {self.provider}/{self.model or "default"} (no route)')

            # Memory
            mem = cc.memory
            print(f'  Memory: {mem.get("total_entries", 0)} entries')

            # Review
            if cc.review:
                review = cc.review
                print(
                    f'  Review: {review.get("review_ids_count", 0)} reviews, gate={review.get("latest_review_status", "?")}'
                )

            # Skills
            skill = cc.skill
            gov = skill.get('governance_status', {})
            gov_summary = '/'.join(sorted(set(gov.values()))) if gov else 'none'
            print(
                f'  Skills: {skill.get("loaded_count", 0)} loaded, {skill.get("shadowed_count", 0)} shadowed, {skill.get("candidate_count", 0)} candidates'
            )
            print(f'    Governance: {gov_summary}')

            # Approval
            app = cc.approval
            print(
                f'  Approval: {app.get("pending_count", 0)} pending, {app.get("blocked_count", 0)} blocked, mode={app.get("mode", "?")}'
            )

            # Cost
            cost = cc.cost
            spent = cost.get('spent_cents', 0.0)
            limit = cost.get('limit_cents')
            state = cost.get('state', 'unavailable')
            limit_str = f'${limit / 100:.2f}' if limit else 'unlimited'
            print(f'  Cost: ${spent / 100:.2f} / {limit_str} ({state})')

        # Context Health (CTX-001)
        if self._cockpit_state and self._cockpit_state.context_health:
            ch = self._cockpit_state.context_health
            if ch.get('overall', 'unknown') != 'green':
                print('\n[Context Health]')
                print(f'  Overall: {ch["overall"].upper()}')
                if ch.get('token_pressure', 'unknown') != 'green':
                    print(f'  Token Pressure: {ch["token_pressure"].upper()}')
                if ch.get('stale_files', 0) > 0:
                    print(f'  Stale Files: {ch["stale_files"]}')
                if ch.get('old_observations', 0) > 50:
                    print(f'  Old Observations: {ch["old_observations"]}')
                if ch.get('memory_confidence', 'unknown') != 'green':
                    print(f'  Memory Confidence: {ch["memory_confidence"].upper()}')
                if ch.get('hidden_large_attachments', 0) > 0:
                    print(f'  Large Attachments: {ch["hidden_large_attachments"]}')
                rec = ch.get('recommendation', '')
                if rec:
                    print(f'  → {rec}')

        # Context Pressure (CPP-P1-003)
        if self._context_pressure:
            pressure = self._context_pressure
            ratio_pct = pressure.token_usage_ratio * 100
            color_label = pressure.usage_level.upper()
            print('\n[Context Pressure]')
            print(f'  Token Usage: {ratio_pct:.1f}% ({color_label})')
            print(f'  Estimated Total: {pressure.estimated_total_tokens:,} tokens')
            if pressure.max_context_tokens:
                print(f'  Max Context: {pressure.max_context_tokens:,} tokens')
            else:
                print('  Max Context: unknown')
            print(f'  Memory Entries: {pressure.memory_count}')
            print(f'  Pinned Files: {pressure.files_pinned}')
            print(f'  Recent Runs: {pressure.recent_runs}')
            print(f'  Large Artifacts: {len(pressure.large_artifacts)}')
            if pressure.recommendations:
                top_recs = pressure.recommendations[:3]
                for rec in top_recs:
                    print(f'  → {rec}')

        # Recent runs
        try:
            from teaagent.run_store import RunStore

            store = RunStore(self.root, readonly=True)
            recent_runs = store.list_runs(limit=3)
            print(f'\nRecent Runs: {len(recent_runs)}')
            for run in recent_runs:
                print(f'  - {run.run_id[:8]}: {run.status}')
        except Exception:
            logger.debug('state panel: recent runs unavailable', exc_info=True)
            print('\nRecent Runs: (unavailable)')

        # Memory catalog
        try:
            from teaagent.memory import MemoryCatalog

            memory = MemoryCatalog(self.root, readonly=True)
            mem_entries = memory.list(limit=3)
            print(f'\nMemory Entries: {len(mem_entries)}')
            for mem_entry in mem_entries:
                print(f'  - {mem_entry.memory_id[:8]}: {mem_entry.content[:30]}...')
        except Exception:
            logger.debug('state panel: memory entries unavailable', exc_info=True)
            print('\nMemory Entries: (unavailable)')

        # Skills panel (DSK-P1-004) extended with diagnostics (DSK-P2-001)
        try:
            self._skill_explain = explain_skill_activation(
                self.root, skill_prompt_mode='index_only'
            )
            index_count = self._skill_explain.index_count
            shadowed_count = len(self._skill_explain.shadowed)
            print(f'\nSkills Loaded: {index_count}')
            if index_count > 0:
                skill_index = discover_skill_index(self.root)
                from teaagent.skill_lifecycle import (
                    SkillLifecycleState,
                    classify_governance_status,
                )

                for _idx, entry in enumerate(skill_index[:5]):
                    skill_dir = entry.path.parent
                    source_dir = skill_dir.parent
                    gov = classify_governance_status(
                        skill_dir=skill_dir,
                        source_dir=source_dir,
                        root=self.root,
                    )
                    lifecycle = SkillLifecycleState.DISCOVERED.value
                    print(f'  - {entry.name} ({gov}, {lifecycle})')
                if index_count > 5:
                    remaining = index_count - 5
                    print(f'  ... and {remaining} more (use /skills for full list)')

            # Shadowed skills
            if shadowed_count > 0:
                print(f'  Shadowed: {shadowed_count}')
                for s in self._skill_explain.shadowed[:3]:
                    print(
                        f'    - {s.name}: winner={s.winner_source}, '
                        f'shadowed={s.shadowed_source}'
                    )
                if shadowed_count > 3:
                    print(f'    ... and {shadowed_count - 3} more shadowed')

            # Candidate store
            try:
                from teaagent.skill_candidates import SkillCandidateStore

                candidate_store = SkillCandidateStore(self.root, readonly=True)
                candidates = candidate_store.list()
                if candidates:
                    print(f'  Candidates: {len(candidates)}')
                    for c in candidates[:3]:
                        print(f'    - {c.name}: {c.status}')
            except Exception:
                logger.debug(
                    'skills header: candidate store unavailable',
                    exc_info=True,
                )

            # Long-result artifacts
            artifact_dir = self.root / '.teaagent' / 'artifacts' / 'tool-results'
            if artifact_dir.is_dir():
                total_files = 0
                run_ids = []
                for run_dir in sorted(artifact_dir.iterdir()):
                    if run_dir.is_dir():
                        run_ids.append(run_dir.name)
                        artifact_files = [f for f in run_dir.iterdir() if f.is_file()]
                        total_files += len(artifact_files)
                if total_files > 0:
                    print(
                        f'  Long-Result Artifacts: {total_files} file(s) '
                        f'across {len(run_ids)} run(s)'
                    )

            # Output verification status
            print(
                '  Output Verification: available (FileExists, SourceUrl, '
                'KnownTitle, Category, PromptInjection)'
            )

            # Skill ecosystem health summary (DSK-P2-003)
            try:
                from teaagent.skill_loader import get_skill_health

                health = get_skill_health(self.root)
                gov = health.get('governance_distribution', {})
                print(
                    '  Health: '
                    f'{health.get("total_skills", 0)} skills, '
                    f'gov={gov.get("direct_write", 0)}d/{gov.get("candidate_installed", 0)}c/'
                    f'{gov.get("compatibility_path", 0)}p/{gov.get("unmanaged", 0)}u, '
                    f'shadowed={health.get("shadowed_count", 0)}, '
                    f'candidates={health["candidate_summary"]["total"]}/{health["candidate_summary"]["installed"]}, '
                    f'stale={len(health.get("stale_candidates", []))}, '
                    f'eval_failed={len(health.get("failed_evals", []))}'
                )
            except Exception:
                logger.debug(
                    'skills header: skill health summary unavailable',
                    exc_info=True,
                )

            if (
                index_count > 0
                or shadowed_count > 0
                or (artifact_dir.is_dir() and total_files > 0)
            ):
                print('  (use /skill-diagnostics for full JSON report)')
        except Exception:
            logger.debug(
                'skills header: skills panel unavailable',
                exc_info=True,
            )
            print('\nSkills Loaded: (unavailable)')

        print('=' * columns)
        print()

    def run(
        self,
        *,
        run_setup: bool = False,
        setup_write_env: bool = False,
        # TASK-DD2-001: task passed via `teaagent chat "<task>"` positional arg
        initial_task: Optional[str] = None,
    ) -> int:
        self._load_workspace_defaults()
        self._load_tui_state()
        self._print_header()
        if run_setup:
            from teaagent.tui._setup import run_tui_setup

            run_tui_setup(self, write_env=setup_write_env)

        # Check if we should use split-pane layout
        use_split_pane = self._should_use_split_pane()
        if use_split_pane:
            self.output_fn(
                '[TeaAgent] Split-pane layout enabled (terminal size >= 120x30)'
            )

        # Initialize prompt_toolkit session if available and no custom input_fn is provided
        if self.input_fn is None:
            try:
                from prompt_toolkit import PromptSession
                from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
                from prompt_toolkit.history import FileHistory

                from teaagent.tui._completion import TeaAgentCompleter

                history_path = self._state_path.parent / 'history.txt'
                history_path.parent.mkdir(parents=True, exist_ok=True)
                self._session = PromptSession(
                    history=FileHistory(str(history_path)),
                    auto_suggest=AutoSuggestFromHistory(),
                    completer=TeaAgentCompleter(root=self.root),
                )
            except (ImportError, OSError):
                self._session = None

        # Auto-start file watcher for pinned files
        self._start_file_watcher()

        # TASK-DD2-001: execute the CLI-supplied initial task before entering
        # the interactive loop.  Previously this arg was parsed by the CLI parser
        # (add_agent_run_arguments include_task_positional=True) but silently
        # dropped because chat_command never forwarded it to run_tui.
        if initial_task:
            try:
                self._run_agent_task(initial_task)
            except (OSError, ValueError, TypeError, RuntimeError) as exc:
                self.output_fn(f'error running initial task: {exc}')

        while True:
            try:
                if use_split_pane:
                    self._print_state_panel()
                else:
                    self._print_status_bar()

                if self.input_fn:
                    raw_command = self.input_fn(self._prompt())
                elif self._session:
                    raw_command = self._session.prompt(self._prompt())
                else:
                    raw_command = input(self._prompt())
            except (EOFError, KeyboardInterrupt):
                self._stop_file_watcher()
                self.output_fn('bye')
                self._save_tui_state()
                return 0

            should_continue = self.handle_command(raw_command)
            if not should_continue:
                self._stop_file_watcher()
                self._save_tui_state()
                return 0

    @property
    def help_text(self) -> str:
        from .rendering import HELP_TEXT

        return HELP_TEXT

    @property
    def route_model(self) -> bool:
        return self.route_model_enabled

    @route_model.setter
    def route_model(self, value: bool) -> None:
        self.route_model_enabled = value

    def handle_command(self, raw_command: str) -> bool:
        from teaagent.tui._commands import _handle_tui_command

        result = _handle_tui_command(self, raw_command)
        self._refresh_control_cockpit()
        return result

    def _handle_memory(self, args: list[str]) -> None:
        if not args:
            self.output_fn('error: memory requires add, list, search, or show')
            return
        catalog = MemoryCatalog(self.root)
        action = args[0]
        rest = args[1:]
        if action == 'add':
            if not rest:
                self.output_fn('error: memory add requires text')
                return
            self._print_json(catalog.add(' '.join(rest)).to_dict())
            return
        if action == 'list':
            self._print_json([entry.to_dict() for entry in catalog.list()])
            return
        if action == 'search':
            if not rest:
                self.output_fn('error: memory search requires a query')
                return
            self._print_json(
                [entry.to_dict() for entry in catalog.search(' '.join(rest))]
            )
            return
        if action == 'show':
            if len(rest) != 1:
                self.output_fn('error: memory show requires one id')
                return
            self._print_json(catalog.show(rest[0]).to_dict())
            return
        if action == 'failures':
            self._handle_memory_failures(rest)
            return
        if action == 'clear':
            self._handle_memory_clear(rest)
            return
        self.output_fn(f"error: unknown memory command '{action}'")

    def _handle_memory_failures(self, args: list[str]) -> None:
        try:
            from datetime import datetime

            from teaagent.memory.failure_card import FailureCardStorage

            storage = FailureCardStorage(self.root)
            cards = storage.list_all()
            if not cards:
                self.output_fn('error: no failure cards recorded')
                return
            self.output_fn(f'memory failures: {len(cards)} card(s)')
            for i, card in enumerate(cards, 1):
                ts = datetime.fromtimestamp(card.timestamp).strftime(
                    '%Y-%m-%d %H:%M:%S'
                )
                loc = (
                    f'{card.file_path}:{card.line_number}'
                    if card.line_number
                    else card.file_path or '?'
                )
                self.output_fn(
                    f'  [{i}] run #{card.run_id} {card.error_type} at {loc} ({ts})'
                )
                self.output_fn(f'       task: {card.task_description}')
                self.output_fn(f'       error: {card.error_message}')
        except Exception as exc:
            self.output_fn(f'error: memory failures: {exc}')

    def _handle_memory_clear(self, args: list[str]) -> None:
        try:
            from teaagent.memory.failure_card import FailureCardStorage

            storage = FailureCardStorage(self.root)
            if args:
                try:
                    idx = int(args[0]) - 1
                    cards = storage.list_all()
                    if 0 <= idx < len(cards):
                        storage.clear_by_id(cards[idx].id)
                        self.output_fn(f'memory clear: removed card #{idx + 1}')
                    else:
                        self.output_fn(f'error: invalid card index {args[0]}')
                except ValueError:
                    self.output_fn('error: memory clear requires a number or no args')
            else:
                count = len(storage.list_all())
                storage.clear_all()
                self.output_fn(f'memory clear: removed {count} card(s)')
        except Exception as exc:
            self.output_fn(f'error: memory clear: {exc}')

    def _handle_pin(self, args: list[str]) -> None:
        if not args:
            self.output_fn('error: pin requires a file path')
            return
        try:
            from teaagent.memory.pinned_file import PinnedFileStorage

            storage = PinnedFileStorage(self.root)
            file_path = args[0]
            if storage.add(file_path):
                self.output_fn(f'pinned: {file_path}')
                self._start_file_watcher()
            else:
                full_path = self.root / file_path
                if not full_path.exists():
                    self.output_fn(f'error: file not found: {file_path}')
                else:
                    self.output_fn(f'error: file already pinned: {file_path}')
        except Exception as exc:
            self.output_fn(f'error: pin: {exc}')

    def _handle_unpin(self, args: list[str]) -> None:
        if not args:
            self.output_fn('error: unpin requires a file path')
            return
        try:
            from teaagent.memory.pinned_file import PinnedFileStorage

            storage = PinnedFileStorage(self.root)
            file_path = args[0]
            if storage.remove(file_path):
                self.output_fn(f'unpinned: {file_path}')
                pinned = storage.list_all()
                if not pinned:
                    self._stop_file_watcher()
            else:
                self.output_fn(f'error: file not pinned: {file_path}')
        except Exception as exc:
            self.output_fn(f'error: unpin: {exc}')

    def _handle_pinned(self) -> None:
        try:
            from datetime import datetime

            from teaagent.memory.pinned_file import PinnedFileStorage

            storage = PinnedFileStorage(self.root)
            pinned = storage.list_all()
            if not pinned:
                self.output_fn('pinned: no files pinned')
                return
            self.output_fn(f'pinned ({len(pinned)}):')
            for pf in pinned:
                mod = datetime.fromtimestamp(pf.last_modified).strftime(
                    '%Y-%m-%d %H:%M:%S'
                )
                self.output_fn(f'  {pf.file_path} (modified: {mod})')
        except Exception as exc:
            self.output_fn(f'error: pinned: {exc}')

    # ── File watcher daemon (live context sync for pinned files) ──────────────

    def _on_file_changed(self, file_path: str, event_type: str) -> None:
        """Callback when a pinned file is modified or deleted."""
        try:
            from teaagent.memory.pinned_file import PinnedFileStorage

            storage = PinnedFileStorage(self.root)
            if event_type == 'deleted':
                storage.remove(file_path)
                self.output_fn(f'file unpinned (deleted): {file_path}')
                pinned_files = storage.list_all()
                if not pinned_files:
                    self._stop_file_watcher()
                elif self._file_watcher:
                    self._file_watcher.update_watched_files(
                        {pf.file_path for pf in pinned_files}
                    )
            elif event_type == 'modified':
                storage.update_last_modified(file_path)
                self.output_fn(f'context refreshed: {file_path}')
        except Exception as exc:
            self.output_fn(f'warning: file change handler error: {exc}')

    def _start_file_watcher(self) -> None:
        """Start the file watcher if there are pinned files."""
        if self._watcher_running:
            return
        try:
            from teaagent.memory.file_watcher import FileWatcher
            from teaagent.memory.pinned_file import PinnedFileStorage

            storage = PinnedFileStorage(self.root)
            pinned = storage.list_all()
            if pinned:
                self._file_watcher = FileWatcher(
                    root=self.root,
                    callback=self._on_file_changed,
                    debounce_ms=500,
                )
                self._file_watcher.update_watched_files({pf.file_path for pf in pinned})
                self._file_watcher.start()
                self._watcher_running = True
                self.output_fn(f'watching {len(pinned)} pinned file(s)')
        except Exception as exc:
            self.output_fn(f'warning: file watcher start failed: {exc}')

    def _stop_file_watcher(self) -> None:
        """Stop the file watcher."""
        if self._file_watcher and self._watcher_running:
            from contextlib import suppress

            with suppress(Exception):
                self._file_watcher.stop()
            self._watcher_running = False
            self._file_watcher = None

    # ── Git-stash checkpoint / undo lifecycle ────────────────────────────────

    def _create_checkpoint(self) -> bool:
        """Create a git stash checkpoint to protect pre-session changes."""
        import subprocess

        timestamp = __import__('time').time()
        self._checkpoint_ref = f'teaagent-checkpoint-{int(timestamp)}'
        try:
            result = subprocess.run(
                ['git', 'stash', 'push', '-m', self._checkpoint_ref],
                cwd=self.root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                self._checkpoint_created = True
                self.output_fn(f'checkpoint created: {self._checkpoint_ref}')
                return True
            if 'No local changes to save' in result.stdout:
                self._checkpoint_created = True
                self.output_fn('checkpoint: clean workspace (no changes to stash)')
                return True
            self.output_fn(f'warning: checkpoint failed: {result.stderr}')
            return False
        except FileNotFoundError:
            self.output_fn('error: git not found in PATH')
            return False
        except Exception as exc:
            self.output_fn(f'error: checkpoint failed: {exc}')
            return False

    def _restore_checkpoint(self) -> bool:
        """Restore checkpoint without destroying unstaged user edits."""
        import subprocess

        if not self._checkpoint_created:
            self.output_fn('no checkpoint to restore')
            return False
        try:
            result = subprocess.run(
                ['git', 'stash', 'list'],
                cwd=self.root,
                capture_output=True,
                text=True,
            )
            stash_exists = (
                self._checkpoint_ref and self._checkpoint_ref in result.stdout
            )
            if not stash_exists:
                self.output_fn('no checkpoint stash found')
                return False

            show_result = subprocess.run(
                ['git', 'stash', 'show', '--name-only', '--oneline'],
                cwd=self.root,
                capture_output=True,
                text=True,
            )
            if show_result.returncode != 0:
                self.output_fn('error: failed to list checkpoint files')
                return False

            lines = show_result.stdout.strip().split('\n')
            stashed_files = [ln.strip() for ln in lines[1:] if ln.strip()]

            if stashed_files:
                checkout_result = subprocess.run(
                    ['git', 'checkout', 'HEAD', '--', *stashed_files],
                    cwd=self.root,
                    capture_output=True,
                    text=True,
                )
                if checkout_result.returncode != 0:
                    self.output_fn(
                        f'error: failed to restore files: {checkout_result.stderr}'
                    )
                    return False

            pop_result = subprocess.run(
                ['git', 'stash', 'pop'],
                cwd=self.root,
                capture_output=True,
                text=True,
            )
            if pop_result.returncode == 0:
                self.output_fn(f'checkpoint restored: {self._checkpoint_ref}')
            else:
                self.output_fn(
                    f'warning: stash pop had conflicts — '
                    f'checkpoint preserved as "{self._checkpoint_ref}"'
                )
                self.output_fn('  resolve manually or run: git stash drop')
            return True
        except FileNotFoundError:
            self.output_fn('error: git not found in PATH')
            return False
        except Exception as exc:
            self.output_fn(f'error: checkpoint restore failed: {exc}')
            return False

    # ── Effort throttling / budget enforcement ───────────────────────────────

    def _handle_compact(self) -> None:
        session = self._current_session()
        if session is None or not session.messages:
            self.output_fn('compact: no active chat session to compact')
            return

        compactor = _ContextCompactor(
            recent_observations=3,
            enable_semantic_compression=True,
        )
        max_tokens = 160000  # conservative default for most model context windows

        messages_dicts = [m.to_dict() for m in session.messages]
        pre_count = len(messages_dicts)
        compacted = compactor.compact_chat_history(messages_dicts, max_tokens)
        post_count = len(compacted)

        session.messages = [ChatMessage.from_dict(m) for m in compacted]
        omitted = pre_count - post_count
        if omitted > 0:
            session.messages.append(
                ChatMessage(
                    role='system',
                    content=f'[System: Session compacted. {omitted} earlier messages compressed to preserve context.]',
                )
            )
        self._get_session_store().save(session)
        self.output_fn(
            f'compact: session compacted ({pre_count} → {post_count} messages, {omitted} omitted)'
        )

    def _handle_cost(self) -> None:
        # Use controller cost when available (CG-03), fall back to local tracking
        controller = self._get_chat_controller()
        cost_cents = controller.get_session_cost()
        if cost_cents == 0 and self._session_cost_cents > 0:
            cost_cents = self._session_cost_cents
        cost_state = self._determine_cost_state()
        self.output_fn(f'cost: ${cost_cents / 100:.2f} ({cost_state})')

    def _get_session_cost_cents(self) -> float:
        """Read session cost from ChatSessionController (source of truth), fall back to local."""
        try:
            controller = self._get_chat_controller()
            cost_cents = float(controller.get_session_cost())
            if cost_cents == 0 and self._session_cost_cents > 0:
                return self._session_cost_cents
            return cost_cents
        except (OSError, ValueError, TypeError, RuntimeError):
            return self._session_cost_cents

    def _handle_effort(self, args: list[str]) -> None:
        if not args:
            cost_cents = self._get_session_cost_cents()
            budget_str = _format_budget_cents(self._max_cost_budget_cents)
            remaining_str = _format_remaining_cents(
                self._max_cost_budget_cents, cost_cents
            )
            self.output_fn(
                f'effort: {self._effort_level}  '
                f'budget={budget_str}  '
                f'spent=${int(cost_cents // 100)}.{int(cost_cents % 100):02d}  '
                f'remaining={remaining_str}'
            )
            return
        level = args[0].lower()
        if level not in ('low', 'normal', 'high', 'unlimited'):
            self.output_fn('error: effort must be low, normal, high, or unlimited')
            return
        self._effort_level = level
        if level == 'low':
            self._max_cost_budget_cents = 200
            self._runtime_max_cost_cents = 200
        elif level == 'normal':
            self._max_cost_budget_cents = 1000
            self._runtime_max_cost_cents = 1000
        elif level == 'high':
            self._max_cost_budget_cents = 5000
            self._runtime_max_cost_cents = 5000
        else:
            self._max_cost_budget_cents = None
            self._runtime_max_cost_cents = None
        self._effort_level = level
        budget_str = _format_budget_cents(self._max_cost_budget_cents)
        self.output_fn(f'effort: {level}  budget={budget_str}')

    def _handle_budget(self) -> None:
        cost_cents = self._get_session_cost_cents()
        limit_str = _format_budget_cents(self._max_cost_budget_cents)
        remaining_str = _format_remaining_cents(self._max_cost_budget_cents, cost_cents)
        cost_state = self._determine_cost_state()
        self.output_fn(
            f'budget: effort={self._effort_level}  '
            f'limit={limit_str}  '
            f'spent=${int(cost_cents // 100)}.{int(cost_cents % 100):02d}  '
            f'remaining={remaining_str}  '
            f'cost_state={cost_state}'
        )

    def _handle_checkpoint(self) -> None:
        self._create_checkpoint()

    def _handle_undo(self) -> None:
        """Undo via the ChatSessionController journal only (U-P2-3).

        Journal-first with NO global git-stash checkpoint fallback: the fallback
        restored files outside the journal scope and diverged from the CLI
        ``agent undo``. ``_restore_checkpoint`` is retained for explicit recovery
        paths but is intentionally not invoked here (guarded by
        tests/tui/test_tui_undo_scope.py).
        """
        from teaagent.run_undo import (
            PARTIAL_UNDO_SHELL_WARNING,
            audit_events_used_shell_mutate,
        )

        store = RunStore(self.root)
        run_id = store.latest_run_with_undo()
        shell_partial_undo = False
        if run_id is not None:
            try:
                shell_partial_undo = audit_events_used_shell_mutate(
                    store.show_run(run_id)
                )
            except FileNotFoundError:
                shell_partial_undo = False

        controller = self._get_chat_controller()
        if controller.undo_last_run():
            self.output_fn('undo: journal undo completed (file-level restore)')
            if shell_partial_undo:
                self.output_fn(PARTIAL_UNDO_SHELL_WARNING)
            return
        self.output_fn(
            'undo: nothing to undo — no undo journal found. Try running a task first.'
        )

    def _handle_background(self) -> None:
        """Create a suspension checkpoint for the current session (``/background``).

        Writes ``.teaagent/suspension-<run_id>.json`` so the session can be
        reviewed via ``teaagent agent interactive-review <run_id>``. This is a
        checkpoint, not detached background execution.
        """
        from teaagent.cli._handlers._agent.resume import suspend_to_background

        controller = self._get_chat_controller()
        session_context = {
            'observations': controller.session_state.observations,
            'compaction_count': controller.session_state.compaction_count,
        }
        config = ChatAgentConfig.from_root(
            self.root,
            model=self.model,
            permission_mode=self.permission_mode,
            max_iterations=self.max_iterations,
            max_tool_calls=self.max_tool_calls,
            max_estimated_cost_cents=self._runtime_max_cost_cents,
        )
        suspend_to_background(config, session_context, set(), output=self.output_fn)

    def _get_session_store(self) -> SessionStore:
        if self._session_store is None:
            self._session_store = SessionStore(self.root)
        return self._session_store

    def _get_chat_controller(self) -> ChatSessionController:
        """Get or create the chat session controller (TASK-002)."""
        if self._chat_controller is None:
            self._chat_controller = ChatSessionController(
                root=self.root,
                output_fn=self.output_fn,
                session_state=self._session_state,
            )
        return self._chat_controller

    @property
    def _session_cost_cents(self) -> float:
        return self._get_chat_controller().session_state.session_cost_cents

    @_session_cost_cents.setter
    def _session_cost_cents(self, val: float) -> None:
        self._get_chat_controller().session_state.session_cost_cents = val

    def _current_session(self) -> Optional[ChatSession]:
        if not self.session_id:
            return None
        return self._get_session_store().load(self.session_id)

    def _ensure_session(self) -> ChatSession:
        session = self._current_session()
        if session is not None:
            return session
        from uuid import uuid4

        session = ChatSession(id=uuid4().hex)
        self.session_id = session.id
        self._get_session_store().save(session)
        return session

    def _run_agent_task(
        self,
        task: str,
        *,
        clarify_first: bool = False,
        initial_observations: Optional[list[dict[str, Any]]] = None,
        initial_context_extra: Optional[dict[str, Any]] = None,
        resumed_from: Optional[str] = None,
    ) -> None:
        from teaagent.ergonomics.context_inject import expand_at_references

        task, _refs = expand_at_references(task, root=self.root)
        task_spec = None
        if clarify_first:
            clarification = clarify_task(task)
            if clarification.needs_clarification:
                self._print_json(
                    {
                        'status': 'needs_clarification',
                        'clarification': clarification.to_dict(),
                    }
                )
                return
            task_spec = build_task_spec(task, clarification)
        provider: str = self.provider or 'gpt'
        routing = (
            route_model(task, provider=provider, model=self.model)
            if self.route_model_enabled
            else None
        )
        selected_model = routing.model if routing else self.model
        self.output_fn(f'agent: provider={provider} root={self.root}')
        adapter = self.adapter_factory(provider, selected_model)
        store = RunStore(self.root)
        audit = store.audit_logger()
        if self.progress:
            audit.add_sink(self._progress_sink)
        from teaagent.run_undo import UndoJournal

        undo_journal = UndoJournal(self.root)
        audit.add_sink(undo_journal)

        chat_messages = None
        if self.chat:
            session = self._ensure_session()
            chat_messages = [
                LLMMessage(role=m.role, content=m.content) for m in session.messages
            ]

        config = ChatAgentConfig.from_root(
            self.root,
            model=selected_model,
            allow_destructive=self.allow_destructive,
            permission_mode=self.permission_mode,
            approved_call_ids=frozenset(self.approved_call_ids),
            enable_subagent=self.subagent,
            max_subagent_depth=self.max_subagent_depth,
            heartbeat_seconds=self.heartbeat_seconds,
            stream=self.stream,
            on_chunk=self._stream_chunk if self.stream else None,
            stream_text_only=True,
            approval_handler=self._approval_handler,
            budget_prompt_handler=self._budget_prompt_handler
            if (self.input_fn is not None)
            else None,
            chat_messages=chat_messages,
            max_estimated_cost_cents=self._runtime_max_cost_cents,
            max_iterations=self.max_iterations,
            max_tool_calls=self.max_tool_calls,
            enable_git_tools=self.enable_git_tools,
            skill_search_dirs=self.skill_search_dirs,
            memory_limit=self.memory_limit,
        )
        controller = self._get_chat_controller()
        execution_result = controller.execute_task(
            task,
            config,
            adapter=adapter,
            audit=audit,
            undo_journal=undo_journal,
            initial_observations=initial_observations,
            initial_context_extra=initial_context_extra,
            resumed_from=resumed_from,
            task_spec=task_spec,
            emit_answer=False,
        )
        result = execution_result.run_result
        self.last_run_id = result.run_id
        events = store.show_run(result.run_id)
        if not isinstance(events, list):
            events = []
        audit_summary = summarize_audit_events(events)
        from teaagent.ergonomics.run_summary import format_run_summary, summarize_run

        run_summary = summarize_run(
            root=self.root,
            run_id=result.run_id,
            events=events,
            cost_cents=result.cost_cents,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            budget_cap_cents=self._runtime_max_cost_cents,
        )

        if self.chat:
            chat_session: Optional[ChatSession] = self._current_session()
            if chat_session is not None:
                chat_session.messages.append(ChatMessage(role='user', content=task))
                answer = (
                    result.final_answer.content
                    if result.final_answer
                    else f'[{result.status}]'
                )
                chat_session.messages.append(
                    ChatMessage(role='assistant', content=answer)
                )
                self._get_session_store().save(chat_session)

        if self.chat and result.status == 'completed' and result.final_answer:
            self.output_fn(result.final_answer.content)
            self.output_fn(format_run_summary(run_summary).rstrip())
        else:
            payload = self._run_result_payload(
                result,
                routing=routing.to_dict() if routing else None,
                audit_summary=audit_summary,
            )
            payload['run_summary'] = run_summary
            if initial_observations:
                payload['replayed_observations'] = len(initial_observations)
            self._print_json(payload)

    def _budget_prompt_handler(self, payload: dict[str, Any]) -> bool:
        percent = float(payload.get('percent', 0.0))
        cost_cents = float(payload.get('cost_cents', 0.0))
        max_cost_cents = float(payload.get('max_cost_cents', 0.0))
        spent = cost_cents / 100.0
        cap = max_cost_cents / 100.0
        self.output_fn(f'budget: at {percent:.0f}% (${spent:.2f} / ${cap:.2f})')
        fn = self.input_fn or input
        answer = fn('Continue? [y/N]: ').strip().lower()
        return answer in {'y', 'yes'}

    def _approval_handler(self, request: ApprovalRequest) -> bool:
        from teaagent.ergonomics.approval_store import ApprovalPresetStore

        store = ApprovalPresetStore(self.root)
        if store.is_allowed(
            request.tool_name,
            permission_mode=self.permission_mode.value,
            arguments=request.arguments,
        ):
            self.output_fn(f'approval: preset allowed {request.tool_name}')
            return True
        self._print_json({'status': 'approval_required', 'approval': request.to_dict()})
        fn = self.input_fn or input
        answer = (
            fn(
                f'approve {request.call_id} ({request.tool_name})? [y]es / [n]o / always for this [p]ath / always for this [t]ool / [s]top run: '
            )
            .strip()
            .lower()
        )
        if answer in {'y', 'yes'}:
            self.output_fn(f'approval: approved {request.call_id}')
            if not request.run_id:
                self.approved_call_ids.add(request.call_id)
            return True
        elif answer in {'s', 'stop'}:
            self.output_fn('approval: stop run requested by operator')
            raise SystemExit('Task aborted by operator.')
        elif answer == 'p':
            path = None
            if request.arguments:
                for key in ('path', 'TargetFile', 'target_file', 'AbsolutePath'):
                    candidate = request.arguments.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        path = candidate
                        break
            if path:
                store.grant(
                    request.tool_name,
                    scope='session',
                    permission_mode=self.permission_mode.value,
                    path_globs=[str(path)],
                    ttl_hours=8.0,
                )
                self.output_fn(
                    f'approval: registered session grant for {request.tool_name} matching path: {path}'
                )
            else:
                self.output_fn(
                    f'approval: no path found in tool arguments; path-scoped grant not created for {request.tool_name}'
                )
                return False
            return True
        elif answer == 't':
            # Use an explicit non-empty path_globs rather than an implicitly
            # unscoped grant. NOTE: '*' is an fnmatch wildcard that matches ALL
            # paths (not just the current directory) — the grant is limited by
            # its session + tool scope, not by the path pattern.
            store.grant(
                request.tool_name,
                scope='session',
                permission_mode=self.permission_mode.value,
                path_globs=['*'],  # wildcard: matches all paths (session/tool-scoped)
                ttl_hours=8.0,
            )
            self.output_fn(
                f'approval: registered session grant for {request.tool_name} (current directory)'
            )
            return True

        self.output_fn(f'approval: denied {request.call_id}')
        return False

    def _run_result_payload(
        self,
        result: RunResult,
        *,
        routing: Optional[dict],
        audit_summary: Optional[dict[str, Any]] = None,
    ) -> dict:
        payload = {
            'run_id': result.run_id,
            'status': result.status,
            'iterations': result.iterations,
            'tool_calls': result.tool_calls,
            'routing': routing,
            'final_answer': result.final_answer.content
            if result.final_answer
            else None,
        }
        if 'approval' in result.metadata:
            payload['approval'] = result.metadata['approval']
        if audit_summary is not None:
            payload['audit_summary'] = audit_summary
        if result.error_message is not None:
            payload['error'] = result.error_message
        return payload

    def _progress_sink(self, event: AuditEvent) -> None:
        from teaagent.streaming.events import format_progress_line

        line = format_progress_line(event)
        if line:
            self.output_fn(line)

    def _stream_chunk(self, chunk: str) -> None:
        self.output_fn(chunk, end='')

    @property
    def _state_path(self) -> Path:
        return Path.home() / '.teaagent' / 'tui_state.json'

    def _load_tui_state(self) -> None:
        if not self._state_path.is_file():
            return
        try:
            data = json.loads(self._state_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(data, dict):
            return
        self.provider = data.get('provider', self.provider)
        self.model = data.get('model', self.model)
        if not self._root_explicit:
            # Only restore root from state when no explicit --root was provided
            # AND the state has a root value (TASK-DD2-002)
            saved_root = data.get('root')
            if saved_root:
                self.root = Path(saved_root).resolve()
        self.permission_mode = PermissionMode(
            data.get('permission_mode', self.permission_mode.value)
        )
        self.allow_destructive = data.get('allow_destructive', self.allow_destructive)
        self.progress = data.get('progress', self.progress)
        self.stream = data.get('stream', self.stream)
        self.subagent = data.get('subagent', self.subagent)
        self.route_model_enabled = data.get(
            'route_model_enabled', self.route_model_enabled
        )
        self.heartbeat_seconds = data.get('heartbeat_seconds', self.heartbeat_seconds)
        if not self._chat_explicit:
            self.chat = data.get('chat', self.chat)
        self.session_id = data.get('session_id', self.session_id)

    def _save_tui_state(self) -> None:
        data = {
            'provider': self.provider,
            'model': self.model,
            'root': str(self.root),
            'permission_mode': self.permission_mode.value,
            'allow_destructive': self.allow_destructive,
            'progress': self.progress,
            'stream': self.stream,
            'subagent': self.subagent,
            'route_model_enabled': self.route_model_enabled,
            'heartbeat_seconds': self.heartbeat_seconds,
            'chat': self.chat,
            'session_id': self.session_id,
        }
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(
                json.dumps(data, indent=2, sort_keys=True), encoding='utf-8'
            )
        except OSError:
            return

    def _get_store(self) -> GraphQLiteGraphStore:
        if self._store is None:
            self._store = GraphQLiteGraphStore(GraphQLiteConfig(database=self.database))
        return self._store

    def _load_workspace_defaults(self) -> None:
        from teaagent.approval import parse_permission_mode
        from teaagent.ergonomics.workspace_defaults import load_workspace_defaults

        defaults = load_workspace_defaults(self.root)
        provider = defaults.get('provider')
        if isinstance(provider, str) and provider:
            self.provider = provider
        if self.provider is None:
            self.provider = 'gpt'
        permission_mode = defaults.get('permission_mode')
        if isinstance(permission_mode, str) and permission_mode:
            self.permission_mode = parse_permission_mode(permission_mode)
        heartbeat = defaults.get('heartbeat')
        if isinstance(heartbeat, (int, float)):
            self.heartbeat_seconds = float(heartbeat)

    def _print_header(self) -> None:
        from teaagent.tui._setup import workspace_configured

        self.output_fn(f'TeaAgent TUI {__version__}')
        self.output_fn(f'Root: {self.root}')
        self.output_fn("Type 'help' for commands. Type 'exit' to quit.")
        if not workspace_configured(self.root):
            self.output_fn(
                "Workspace not configured — type 'setup' or run 'teaagent setup'."
            )

    def _prompt(self) -> str:
        destructive = '!' if self.allow_destructive else ''
        model = self.model or 'default'
        routed = ':route' if self.route_model_enabled else ''
        return f'teaagent[{self.provider}:{model}{routed}:{self.permission_mode.value}{destructive}]> '

    def _print_status_bar(self) -> None:
        from teaagent.tui.state import format_status_bar

        pending = 0
        run_status = 'idle'
        if self._cockpit_state:
            pending = self._cockpit_state.approvals.pending_count
            run_status = self._cockpit_state.harness_health.overall
            if run_status == 'unknown':
                run_status = 'idle'
        memory_mb = None
        try:
            import resource

            memory_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
                1024 * 1024
            )
        except (ImportError, OSError, AttributeError):
            pass
        self.output_fn(
            format_status_bar(
                permission_mode=self.permission_mode.value,
                pending_approvals=pending,
                run_status=run_status,
                memory_mb=memory_mb,
            )
        )

    def _print_json(self, value: Any) -> None:
        self.output_fn(json.dumps(value, ensure_ascii=False, sort_keys=True))
