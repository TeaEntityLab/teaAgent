"""Main chat REPL loop and session management."""

from __future__ import annotations

import json
import readline
import subprocess
import sys
import uuid
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from teaagent.chat_agent import ChatAgentConfig
from teaagent.chat_session_controller import ChatSessionController, SessionState
from teaagent.cli.execution import AgentExecutionFactory
from teaagent.context import ContextCompactor
from teaagent.llm import available_providers, create_llm_adapter
from teaagent.memory.file_watcher import FileWatcher
from teaagent.memory.pinned_file import PinnedFileStorage
from teaagent.run_store import RunStore  # noqa: F401 — re-export for test patches
from teaagent.run_undo import UndoJournal  # noqa: F401 — re-export for test patches

from .chat_commands import (
    get_failure_warnings,
    handle_compact,
    handle_memory_clear,
    handle_memory_failures,
    handle_pin,
    handle_pinned,
    handle_unpin,
)
from .chat_completion import complete_file_path, complete_symbol


def suspend_to_background(
    config: ChatAgentConfig, session_context: dict, targeted_files: set[Path]
) -> str:
    """Suspend current REPL session and convert to background task.

    Args:
        config: Current chat agent configuration
        session_context: Current session context and observations
        targeted_files: Current targeted file set

    Returns:
        run_id of the created background task, or empty string on failure
    """
    import subprocess

    root = config.root.resolve()

    print('[TeaAgent] Suspending session as a checkpoint...')

    # Generate unique run_id
    run_id = str(uuid.uuid4())[:8]

    # Create suspension checkpoint
    tea_dir = root / '.teaagent'
    tea_dir.mkdir(parents=True, exist_ok=True)

    # Save session state with ACP compliance
    suspension_data = {
        'run_id': run_id,
        'timestamp': __import__('time').time(),
        'acp_version': '1.0.0',  # ACP protocol version for state compatibility
        'mode': 'suspended_from_repl',  # Track origin mode
        'config': {
            'model': config.model,
            'permission_mode': config.permission_mode.value
            if config.permission_mode
            else None,
            'max_iterations': config.max_iterations,
            'max_tool_calls': config.max_tool_calls,
            'max_estimated_cost_cents': config.max_estimated_cost_cents,
        },
        'session_context': {
            'observations_count': len(session_context.get('observations', [])),
            'compaction_count': session_context.get('compaction_count', 0),
            'observations': session_context.get('observations', [])[-10:]
            if session_context.get('observations')
            else [],  # Keep last 10 for context
        },
        'targeted_files': [
            str(f.resolve().relative_to(root.resolve()))
            for f in targeted_files
            if f.resolve().is_relative_to(root.resolve())
        ],
    }

    suspension_file = tea_dir / f'suspension-{run_id}.json'
    try:
        suspension_file.write_text(
            json.dumps(suspension_data, indent=2), encoding='utf-8'
        )
    except Exception as exc:
        print(f'[TeaAgent] Error saving suspension state: {exc}')
        return ''

    # Check if workspace is dirty and warn user
    branch_created = False
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=root,
            capture_output=True,
            text=True,
        )

        if result.stdout.strip():
            print('[TeaAgent] Warning: Workspace has uncommitted changes.')
            print('[TeaAgent] Session is suspended on current branch.')
            print('[TeaAgent] Uncommitted changes remain in working directory.')
            branch_created = False
    except FileNotFoundError:
        print('[TeaAgent] Git not found, skipping workspace check')
    except Exception as exc:
        print(f'[TeaAgent] Warning: Could not check workspace status: {exc}')

    # Emit audit event for suspension
    try:
        factory = AgentExecutionFactory(root)
        store = factory.create_run_store()
        audit = store.audit_logger()
        audit.record(
            event_type='session_suspended',
            run_id=run_id,
            mode='suspended_from_repl',
            observations_count=len(session_context.get('observations', [])),
            targeted_files_count=len(targeted_files),
            branch_created=branch_created,
        )
    except Exception as exc:
        print(f'[TeaAgent] Warning: Could not emit suspension audit event: {exc}')

    # Write a run_started event so agent_resume_command can find this run
    try:
        resume_store = factory.create_run_store()
        resume_audit = resume_store.audit_logger(run_id=run_id)
        observations = session_context.get('observations', [])
        last_task = '(resumed from REPL suspension)'
        if observations:
            last_obs = observations[-1]
            if isinstance(last_obs, dict) and 'task' in last_obs:
                last_task = last_obs['task']
        resume_audit.record(
            event_type='run_started',
            run_id=run_id,
            task=last_task,
            suspended_from='repl',
        )
    except Exception as exc:
        print(f'[TeaAgent] Warning: Could not write resume event: {exc}')

    print('[TeaAgent] Session suspended successfully!')
    print(f'[TeaAgent] Run ID: {run_id}')
    print(f'[TeaAgent] To review: teaagent agent interactive-review {run_id}')
    print('[TeaAgent] Note: This is a suspension checkpoint, not background execution.')

    return run_id


def print_chat_help() -> None:
    """Print chat REPL help."""
    print('[TeaAgent] Chat Commands:')
    print('  /exit, /quit, q, quit, exit  - Exit chat mode')
    print('  /help, /?, help, ?         - Show this help')
    print('  /cost                      - Show session cost')
    print('  /compact                   - Compact session context to save tokens')
    print('  /clear                     - Clear conversation history')
    print('  /diff                      - Show git diff for current session')
    print(
        '  /background, /handoff       - Create a suspension checkpoint (not background execution)'
    )
    print('  /context                   - Show targeted context files')
    print('  /add <path>                - Add file/directory to context')
    print('  /drop <path>               - Remove file/directory from context')
    print('  /provider <name>           - Switch LLM provider')
    print('  /model <name>              - Switch model')
    print('  /effort <low|normal|high|unlimited>  - Set effort throttling level')
    print('  /budget                    - Show budget status')
    print('  /checkpoint                - Create manual git checkpoint')
    print(
        '  /undo                      - Undo last agent edit (journal-first; fallback to checkpoint)'
    )
    print(
        '  !<command>                 - DISABLED: Use full terminal for shell commands'
    )
    print()
    print('[TeaAgent] Memory & Context Commands:')
    print('  /memory failures           - List all failure cards')
    print('  /memory clear              - Clear all failure cards')
    print('  /memory clear <n>          - Clear specific failure card by number')
    print('  /pin <file>                - Pin file for live context sync')
    print('  /unpin <file>              - Unpin file from live context sync')
    print('  /pinned                    - List all pinned files')
    print()
    print('[TeaAgent] Any other input will be executed as a task')


def run_chat_repl(  # noqa: C901
    config: ChatAgentConfig,
    initial_task: str | None = None,
) -> int:
    """Run the interactive chat REPL (legacy path).

    Deprecated: production chat now routes through ChatSessionController
    via run_tui(chat=True). This function is retained only for test
    compatibility and will be removed in a future release.

    Args:
        config: Chat agent configuration
        initial_task: Optional initial task to execute before entering REPL

    Returns:
        Exit code
    """
    import warnings

    warnings.warn(
        'run_chat_repl is deprecated; use run_tui(chat=True) via ChatSessionController',
        DeprecationWarning,
        stacklevel=2,
    )

    # Context compaction for long sessions
    compactor = ContextCompactor(
        recent_observations=3,
        threshold_low=0.75,
        threshold_high=0.92,
        enable_semantic_compression=True,
    )

    # Session context for compaction
    session_context: dict[str, Any] = {
        'observations': [],
        'compaction_count': 0,
    }

    # Surgical context targeting - active file set
    targeted_files = set[Path]()

    # Auto-stash checkpoint for safe undo
    checkpoint_created = False
    checkpoint_ref = None

    # Hot-swappable model configuration
    current_provider = (
        config.model.split('/')[0] if config.model and '/' in config.model else None
    )
    current_model = config.model

    # Tab completion setup
    completer_matches: list[str] = []

    def tab_completer(text: str, state: int) -> str | None:
        """Tab completion handler for readline."""
        nonlocal completer_matches
        if state == 0:
            # First call - generate completions
            if text.startswith('@'):
                # File/symbol completion
                completions = complete_file_path(text, config.root)
                if not completions:
                    completions = complete_symbol(text, config.root)
                completer_matches = completions
            else:
                # Default to no completion
                completer_matches = []

        try:
            return completer_matches[state]
        except (IndexError, AttributeError):
            return None

    # Enable tab completion if in TTY mode
    if sys.stdin.isatty():
        readline.set_completer(tab_completer)
        readline.parse_and_bind('tab: complete')
        readline.set_completer_delims(' \t\n')  # Don't break on @

    # Runtime configuration for hot-swapping (avoids frozen dataclass issue)
    runtime_model = config.model
    runtime_max_cost_cents = config.max_estimated_cost_cents

    # Create initial adapter (will be recreated on model swap)
    provider = (
        config.model.split('/')[0] if config.model and '/' in config.model else 'gpt'
    )
    model = (
        config.model.split('/', 1)[1] if config.model and '/' in config.model else None
    )
    adapter = create_llm_adapter(provider, model=model)

    # Effort throttling configuration
    effort_level = 'normal'  # low, normal, high
    max_cost_budget_cents = config.max_estimated_cost_cents
    session_cost_cents: float = 0

    def _format_budget(cents: int | None) -> str:
        if cents is None:
            return 'unlimited'
        return f'${cents / 100:.2f}'

    def _format_remaining(cents: int | None, spent: float) -> str:
        if cents is None:
            return 'unlimited'
        return f'${max(cents - spent, 0) / 100:.2f}'

    # File watcher for live context synchronization
    file_watcher = None
    watcher_running = False

    def on_file_changed(file_path: str, event_type: str) -> None:
        """Callback for file watcher events.

        Args:
            file_path: Path to the changed file
            event_type: Type of event ('modified' or 'deleted')
        """

        try:
            storage = PinnedFileStorage(config.root)

            if event_type == 'deleted':
                # File was deleted, unpin it and show warning
                storage.remove(file_path)
                print(f'[TeaAgent] ⚠️ File deleted and unpinned: {file_path}')
                # Update watcher
                if file_watcher:
                    pinned_files = storage.list_all()
                    file_watcher.update_watched_files(
                        {pf.file_path for pf in pinned_files}
                    )
            elif event_type == 'modified':
                # File was modified, update context
                storage.update_last_modified(file_path)
                modified_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(
                    f'[TeaAgent] 📌 Context auto-refreshed: {file_path} (modified at {modified_str})'
                )

                # Update targeted files if this file is in the context
                full_path = config.root / file_path
                if full_path in targeted_files:
                    # Re-read the file to update context
                    # In a full implementation, this would update the session context
                    pass
        except Exception as exc:
            # Don't let file watcher errors break the chat system
            print(
                f'[TeaAgent] Warning: Error handling file change: {exc}',
                file=sys.stderr,
            )

    def start_file_watcher() -> None:
        """Start the file watcher if there are pinned files."""
        nonlocal file_watcher, watcher_running

        try:
            storage = PinnedFileStorage(config.root)
            pinned_files = storage.list_all()

            if pinned_files and not watcher_running:
                file_watcher = FileWatcher(
                    root=config.root,
                    callback=on_file_changed,
                    debounce_ms=500,
                )
                file_watcher.update_watched_files({pf.file_path for pf in pinned_files})
                file_watcher.start()
                watcher_running = True
                print(
                    f'[TeaAgent] Watching {len(pinned_files)} pinned files for changes...'
                )
        except Exception as exc:
            print(
                f'[TeaAgent] Warning: Failed to start file watcher: {exc}',
                file=sys.stderr,
            )

    def stop_file_watcher() -> None:
        """Stop the file watcher."""
        nonlocal watcher_running

        if file_watcher and watcher_running:
            try:
                file_watcher.stop()
                watcher_running = False
            except (OSError, RuntimeError) as exc:
                # Log but don't crash - watcher cleanup is best-effort
                import logging

                logging.getLogger(__name__).warning('File watcher stop error: %s', exc)

    def create_checkpoint() -> bool:
        """Create a git stash checkpoint to protect pre-session changes."""
        nonlocal checkpoint_created, checkpoint_ref

        try:
            # Create a timestamped checkpoint
            timestamp = __import__('time').time()
            checkpoint_ref = f'teaagent-checkpoint-{int(timestamp)}'

            # Stash current changes with checkpoint reference
            result = subprocess.run(
                ['git', 'stash', 'push', '-m', checkpoint_ref],
                cwd=config.root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                checkpoint_created = True
                print(f'[TeaAgent] Created checkpoint: {checkpoint_ref}')
                return True
            else:
                # If stash fails (no changes to stash), that's okay
                if 'No local changes to save' in result.stdout:
                    checkpoint_created = True
                    print('[TeaAgent] No changes to stash (clean workspace)')
                    return True
                print(
                    f'[TeaAgent] Warning: Could not create checkpoint: {result.stderr}'
                )
                return False
        except FileNotFoundError:
            print('[TeaAgent] Git not found in PATH')
            return False
        except Exception as exc:
            print(f'[TeaAgent] Error creating checkpoint: {exc}')
            return False

    def restore_checkpoint() -> bool:
        """Restore the git checkpoint to undo changes."""
        nonlocal checkpoint_created

        try:
            if not checkpoint_created:
                print('[TeaAgent] No checkpoint to restore')
                return False

            # First check if the stash exists before destructive operations
            result = subprocess.run(
                ['git', 'stash', 'list'],
                cwd=config.root,
                capture_output=True,
                text=True,
            )

            stash_exists = checkpoint_ref and checkpoint_ref in result.stdout

            if stash_exists:
                # Pop the stash
                subprocess.run(
                    ['git', 'stash', 'pop'],
                    cwd=config.root,
                    capture_output=True,
                )
                checkpoint_created = False
                print(f'[TeaAgent] Restored checkpoint: {checkpoint_ref}')
                return True
            else:
                print('[TeaAgent] Checkpoint not found in stash')
                return False
        except FileNotFoundError:
            print('[TeaAgent] Git not found in PATH')
            return False
        except Exception as exc:
            print(f'[TeaAgent] Error restoring checkpoint: {exc}')
            return False

    def swap_provider(provider_name: str) -> bool:
        """Hot-swap the LLM provider during the session."""
        nonlocal current_provider, current_model, runtime_model, adapter
        try:
            if provider_name not in available_providers():
                print(f"[TeaAgent] Error: Unknown provider '{provider_name}'")
                print(
                    f'[TeaAgent] Available providers: {", ".join(available_providers())}'
                )
                return False

            current_provider = provider_name
            # Rebuild the model string with new provider
            if current_model and '/' in current_model:
                current_model = f'{provider_name}/{current_model.split("/", 1)[1]}'
            else:
                current_model = provider_name

            runtime_model = current_model

            # Recreate adapter with new provider
            model_part = (
                current_model.split('/', 1)[1] if '/' in current_model else None
            )
            adapter = create_llm_adapter(provider_name, model=model_part)

            print(f'[TeaAgent] Provider switched to: {provider_name}')
            print(f'[TeaAgent] Current model: {current_model}')
            return True
        except Exception as exc:
            print(f'[TeaAgent] Error switching provider: {exc}')
            return False

    def swap_model(model_name: str) -> bool:
        """Hot-swap the model during the session."""
        nonlocal current_model, runtime_model, adapter
        try:
            if current_provider:
                new_model = f'{current_provider}/{model_name}'
            else:
                new_model = model_name

            current_model = new_model
            runtime_model = current_model

            # Recreate adapter with new model
            provider = current_provider or 'gpt'
            adapter = create_llm_adapter(provider, model=model_name)

            print(f'[TeaAgent] Model switched to: {current_model}')
            return True
        except Exception as exc:
            print(f'[TeaAgent] Error switching model: {exc}')
            return False

    def set_effort_level(level: str) -> bool:
        """Set the effort throttling level for the session."""
        nonlocal effort_level, max_cost_budget_cents, runtime_max_cost_cents
        try:
            level = level.lower()
            if level not in ('low', 'normal', 'high'):
                print(
                    "[TeaAgent] Error: Effort level must be 'low', 'normal', or 'high'"
                )
                return False

            effort_level = level

            # Adjust budget based on effort level
            if level == 'low':
                max_cost_budget_cents = 200  # $2 budget
                runtime_max_cost_cents = 200
            elif level == 'normal':
                max_cost_budget_cents = 1000  # $10 budget
                runtime_max_cost_cents = 1000
            elif level == 'high':
                max_cost_budget_cents = 5000  # $50 budget
                runtime_max_cost_cents = 5000

            print(f'[TeaAgent] Effort level set to: {level}')
            print(f'[TeaAgent] Budget limit: {_format_budget(max_cost_budget_cents)}')
            return True
        except Exception as exc:
            print(f'[TeaAgent] Error setting effort level: {exc}')
            return False

    def show_effort_status() -> None:
        """Display current effort throttling status."""
        print(f'[TeaAgent] Effort level: {effort_level}')
        print(f'[TeaAgent] Budget limit: {_format_budget(max_cost_budget_cents)}')
        print(f'[TeaAgent] Session cost: ${session_cost_cents / 100:.2f}')
        print(
            f'[TeaAgent] Remaining budget: {_format_remaining(max_cost_budget_cents, session_cost_cents)}'
        )

    # Automatic checkpoint creation disabled for data safety
    # Users should explicitly create checkpoints when needed to avoid hiding changes
    # create_checkpoint()

    # Start file watcher if there are pinned files
    start_file_watcher()

    # Create shared session controller (CG-05)
    session_state = SessionState(
        session_cost_cents=session_cost_cents,
        observations=session_context.get('observations', []),
        compaction_count=session_context.get('compaction_count', 0),
        targeted_files=targeted_files,
    )
    controller = ChatSessionController(
        root=config.root,
        output_fn=print,
        session_state=session_state,
    )

    # If initial task provided, execute it first
    if initial_task:
        print(f'[TeaAgent] Executing initial task: {initial_task}')
        # Inject failure warnings
        task_with_warnings = initial_task + get_failure_warnings(
            initial_task, config.root
        )
        # Create updated config with runtime values
        updated_config = replace(
            config,
            model=runtime_model,
            max_estimated_cost_cents=runtime_max_cost_cents,
        )

        # Set up audit and undo journal
        factory = AgentExecutionFactory(config.root)
        store = factory.create_run_store()
        audit = factory.create_audit_logger(store)
        undo_journal = factory.create_undo_journal()
        audit.add_sink(undo_journal)

        # Use controller for consistent behavior (CG-05)
        result = controller.execute_task(
            task=task_with_warnings,
            config=updated_config,
            adapter=adapter,
            audit=audit,
            undo_journal=undo_journal,
        )

        if result.run_result.status != 'completed':
            return 1

        # Sync back to session_context for compatibility
        session_cost_cents = int(session_state.session_cost_cents)
        session_context['observations'] = session_state.observations
        print()

    # REPL loop
    while True:
        try:
            # Build prompt with pinned file indicator
            try:
                storage = PinnedFileStorage(config.root)
                pinned_count = len(storage.list_all())
                prompt = (
                    f'teaagent📌{pinned_count}> ' if pinned_count > 0 else 'teaagent> '
                )
            except Exception as exc:
                import logging

                logging.getLogger(__name__).debug('Pinned file count error: %s', exc)
                prompt = 'teaagent> '

            # Read user input
            user_input = input(prompt).strip()

            if not user_input:
                continue

            # Handle shell escape hatch - DISABLED for security
            # Shell escape bypasses approval/audit governance. Use full terminal instead.
            if user_input.startswith('!'):
                print(
                    '[TeaAgent] Error: Shell escape is disabled for security. Use the full terminal to execute shell commands.'
                )
                continue

            # Handle exit commands
            if user_input in ('/exit', '/quit', 'q', 'quit', 'exit'):
                print('[TeaAgent] Goodbye!')
                return 0

            # Handle help
            if user_input in ('/help', '/?', 'help', '?'):
                print_chat_help()
                continue

            # Handle compact command
            if user_input == '/compact':
                compact_result = handle_compact(compactor, session_context)
                print('[TeaAgent] Compaction complete:')
                print(f'  - Tokens saved: ~{compact_result["tokens_saved"]}')
                print(
                    f'  - Compression ratio: {compact_result["compression_ratio"]:.2%}'
                )
                print(f'  - Total compactions: {compact_result["compaction_count"]}')
                print(
                    f'  - Observations: {compact_result["pre_count"]} → {compact_result["post_count"]}'
                )
                continue

            # Handle clear command
            if user_input == '/clear':
                print('[TeaAgent] Clearing conversation history...')
                session_context['observations'] = []
                session_context['compaction_count'] = 0
                targeted_files.clear()
                print('[TeaAgent] Conversation history cleared. Starting fresh.')
                continue

            # Handle checkpoint command
            if user_input == '/checkpoint':
                print('[TeaAgent] Creating manual checkpoint...')
                if create_checkpoint():
                    print('[TeaAgent] Checkpoint created successfully')
                else:
                    print('[TeaAgent] Checkpoint creation failed')
                continue

            # Handle background command
            if user_input in ('/background', '/handoff'):
                run_id = suspend_to_background(config, session_context, targeted_files)
                if run_id:
                    print(
                        '[TeaAgent] Interactive session converted to a suspension checkpoint.'
                    )
                    print('[TeaAgent] You can now safely exit the REPL.')
                    print(
                        f'[TeaAgent] Use teaagent agent interactive-review {run_id} to inspect changes.'
                    )
                else:
                    print('[TeaAgent] Failed to suspend session')
                continue

            # Handle cost command
            if user_input == '/cost':
                print(f'[TeaAgent] Session cost: ${session_cost_cents / 100:.2f}')
                print(
                    f'[TeaAgent] Budget limit: {_format_budget(max_cost_budget_cents)}'
                )
                print(
                    f'[TeaAgent] Remaining: {_format_remaining(max_cost_budget_cents, session_cost_cents)}'
                )
                continue

            # Handle diff command
            if user_input == '/diff':
                try:
                    proc = subprocess.run(
                        ['git', 'diff'],
                        cwd=config.root,
                        capture_output=True,
                        text=True,
                    )
                    if proc.stdout:
                        print(proc.stdout)
                    else:
                        print('[TeaAgent] No changes to show')
                except FileNotFoundError:
                    print('[TeaAgent] Git not found')
                except Exception as exc:
                    print(f'[TeaAgent] Error showing diff: {exc}')
                continue

            # Handle context command
            if user_input == '/context':
                if targeted_files:
                    print('[TeaAgent] Targeted context files:')
                    for f in sorted(targeted_files):
                        print(f'  - {f}')
                else:
                    print('[TeaAgent] No files currently targeted')
                continue

            # Handle add command
            if user_input.startswith('/add '):
                path = user_input[5:].strip()
                full_path = config.root / path
                if full_path.exists():
                    targeted_files.add(full_path)
                    print(f'[TeaAgent] Added to context: {path}')
                else:
                    print(f'[TeaAgent] Error: Path not found: {path}')
                continue

            # Handle drop command
            if user_input.startswith('/drop '):
                path = user_input[6:].strip()
                full_path = config.root / path
                if full_path in targeted_files:
                    targeted_files.remove(full_path)
                    print(f'[TeaAgent] Removed from context: {path}')
                else:
                    print(f'[TeaAgent] Error: Path not in context: {path}')
                continue

            # Handle memory failures command
            if user_input == '/memory failures':
                handle_memory_failures(config.root)
                continue

            # Handle memory clear command
            if user_input.startswith('/memory clear'):
                handle_memory_clear(config.root, user_input)
                continue

            # Handle pin command
            if user_input.startswith('/pin '):
                handle_pin(config.root, user_input, start_file_watcher)
                continue

            # Handle unpin command
            if user_input.startswith('/unpin '):
                handle_unpin(config.root, user_input, start_file_watcher)
                continue

            # Handle pinned command
            if user_input == '/pinned':
                handle_pinned(config.root)
                continue

            # Handle provider command
            if user_input.startswith('/provider '):
                provider_arg = user_input[10:].strip()
                if provider_arg:
                    swap_provider(provider_arg)
                else:
                    print('[TeaAgent] Usage: /provider <name>')
                    print(
                        f'[TeaAgent] Available providers: {", ".join(available_providers())}'
                    )
                continue

            # Handle model command
            if user_input.startswith('/model '):
                model_arg = user_input[7:].strip()
                if model_arg:
                    swap_model(model_arg)
                else:
                    print('[TeaAgent] Usage: /model <name>')
                    print(f'[TeaAgent] Current model: {current_model}')
                continue

            # Handle effort command
            if user_input.startswith('/effort '):
                effort_arg = user_input[8:].strip()
                if effort_arg:
                    set_effort_level(effort_arg)
                else:
                    print('[TeaAgent] Usage: /effort <low|normal|high>')
                    show_effort_status()
                continue

            # Handle budget command (alias for effort status)
            if user_input == '/budget':
                show_effort_status()
                continue

            # Handle undo command
            if user_input == '/undo':
                print('[TeaAgent] Undoing last change...')
                if controller.undo_last_run():
                    print('[TeaAgent] Undo completed successfully')
                else:
                    # If no journal, try checkpoint as fallback
                    if restore_checkpoint():
                        print('[TeaAgent] Undo completed via checkpoint')
                    else:
                        print('[TeaAgent] Nothing to undo')
                continue

            # Execute task
            print(f'[TeaAgent] Executing: {user_input}')
            # Inject failure warnings
            task_with_warnings = user_input + get_failure_warnings(
                user_input, config.root
            )
            # Create updated config with runtime values
            updated_config = replace(
                config,
                model=runtime_model,
                max_estimated_cost_cents=runtime_max_cost_cents,
            )

            # Set up audit and undo journal for this task
            factory = AgentExecutionFactory(config.root)
            store = factory.create_run_store()
            audit = factory.create_audit_logger(store)
            undo_journal = factory.create_undo_journal()
            audit.add_sink(undo_journal)

            # Use controller for consistent behavior (CG-05)
            result = controller.execute_task(
                task=task_with_warnings,
                config=updated_config,
                adapter=adapter,
                audit=audit,
                undo_journal=undo_journal,
            )

            # Sync back to session_context for compatibility
            session_cost_cents = int(session_state.session_cost_cents)
            session_context['observations'] = session_state.observations

            print()

        except EOFError:
            print('\n[TeaAgent] Goodbye!')
            stop_file_watcher()
            return 0
        except KeyboardInterrupt:
            print(
                '\n[TeaAgent] Interrupted. Type /exit to quit or continue with next task'
            )
            continue
