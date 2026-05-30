"""Interactive chat REPL handler for teaagent.

This module provides a state-preserving interactive REPL command loop
that allows users to interact with the agent without restarting the process.
"""

from __future__ import annotations

import argparse
import json
import re
import readline
import shlex
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.context import ContextCompactor
from teaagent.llm import available_providers, create_llm_adapter
from teaagent.policy import parse_permission_mode


def handle_memory_failures(root: Path) -> None:
    """Handle /memory failures command to list all failure cards.

    Args:
        root: The workspace root directory
    """
    try:
        from datetime import datetime

        from teaagent.memory.failure_card import FailureCardStorage

        storage = FailureCardStorage(root)
        cards = storage.list_all()

        if not cards:
            print('[TeaAgent] No failure cards recorded.')
            return

        print(f'[TeaAgent] Failure Cards ({len(cards)} total):')
        for i, card in enumerate(cards, 1):
            timestamp_str = datetime.fromtimestamp(card.timestamp).strftime(
                '%Y-%m-%d %H:%M:%S'
            )
            print(
                f'  [{i}] Run #{card.run_id} - {card.error_type} at {card.file_path}:{card.line_number if card.line_number else "?"} ({timestamp_str})'
            )
            print(f'      Task: {card.task_description}')
            print(f'      Error: {card.error_message}')
            print()
    except Exception as exc:
        print(f'[TeaAgent] Error retrieving failure cards: {exc}')


def handle_pin(
    root: Path, command: str, watcher_callback: Callable[[], None] | None = None
) -> None:
    """Handle /pin command to add a file to the watch list.

    Args:
        root: The workspace root directory
        command: The full command string
        watcher_callback: Optional callback to restart the file watcher
    """
    try:
        from teaagent.memory.pinned_file import PinnedFileStorage

        parts = command.split()
        if len(parts) < 2:
            print('[TeaAgent] Usage: /pin <file>')
            return

        file_path = parts[1]
        storage = PinnedFileStorage(root)

        if storage.add(file_path):
            print(f'[TeaAgent] 📌 Pinned: {file_path}')
            # Restart file watcher to include new file
            if watcher_callback:
                watcher_callback()
        else:
            # Check if file exists
            full_path = root / file_path
            if not full_path.exists():
                print(f'[TeaAgent] ❌ Error: File not found: {file_path}')
            else:
                print(f'[TeaAgent] ❌ Error: File is already pinned: {file_path}')
    except Exception as exc:
        print(f'[TeaAgent] Error pinning file: {exc}')


def handle_unpin(
    root: Path, command: str, watcher_callback: Callable[[], None] | None = None
) -> None:
    """Handle /unpin command to remove a file from the watch list.

    Args:
        root: The workspace root directory
        command: The full command string
        watcher_callback: Optional callback to restart the file watcher
    """
    try:
        from teaagent.memory.pinned_file import PinnedFileStorage

        parts = command.split()
        if len(parts) < 2:
            print('[TeaAgent] Usage: /unpin <file>')
            return

        file_path = parts[1]
        storage = PinnedFileStorage(root)

        if storage.remove(file_path):
            print(f'[TeaAgent] 📌 Unpinned: {file_path}')
            # Restart file watcher to update watched files
            if watcher_callback:
                watcher_callback()
        else:
            print(f'[TeaAgent] ❌ Error: File is not pinned: {file_path}')
    except Exception as exc:
        print(f'[TeaAgent] Error unpinning file: {exc}')


def handle_pinned(root: Path) -> None:
    """Handle /pinned command to list all pinned files.

    Args:
        root: The workspace root directory
    """
    try:
        from datetime import datetime

        from teaagent.memory.pinned_file import PinnedFileStorage

        storage = PinnedFileStorage(root)
        pinned_files = storage.list_all()

        if not pinned_files:
            print('[TeaAgent] No files are currently pinned.')
            return

        print(f'[TeaAgent] Pinned Files ({len(pinned_files)}):')
        for i, pf in enumerate(pinned_files, 1):
            modified_str = datetime.fromtimestamp(pf.last_modified).strftime(
                '%Y-%m-%d %H:%M:%S'
            )
            print(f'  [{i}] {pf.file_path} - last modified: {modified_str}')
    except Exception as exc:
        print(f'[TeaAgent] Error listing pinned files: {exc}')


def handle_memory_clear(root: Path, command: str) -> None:
    """Handle /memory clear command to clear failure cards.

    Args:
        root: The workspace root directory
        command: The full command string
    """
    try:
        from teaagent.memory.failure_card import FailureCardStorage

        storage = FailureCardStorage(root)

        # Check if specific ID provided
        parts = command.split()
        if len(parts) == 3:
            # Clear specific card by index
            try:
                index = int(parts[2]) - 1  # Convert to 0-based
                cards = storage.list_all()
                if 0 <= index < len(cards):
                    card_id = cards[index].id
                    if storage.clear_by_id(card_id):
                        print(
                            f'[TeaAgent] Cleared failure card #{index + 1} (Run #{cards[index].run_id})'
                        )
                    else:
                        print(f'[TeaAgent] Failed to clear failure card #{index + 1}')
                else:
                    print(f'[TeaAgent] Invalid index: {index + 1}')
            except ValueError:
                print('[TeaAgent] Invalid index. Use: /memory clear <number>')
        else:
            # Clear all cards
            cards = storage.list_all()
            storage.clear_all()
            print(f'[TeaAgent] Cleared {len(cards)} failure cards')
    except Exception as exc:
        print(f'[TeaAgent] Error clearing failure cards: {exc}')


def get_failure_warnings(task: str, root: Path) -> str:
    """Retrieve and format failure warnings for a task.

    Args:
        task: The task description
        root: The workspace root directory

    Returns:
        Formatted warning string to inject into the prompt
    """
    try:
        from teaagent.memory.failure_card import FailureCardStorage

        # Extract file paths from task
        file_refs = re.findall(r'@([^\s]+)', task)

        # Find matching failure cards
        storage = FailureCardStorage(root)
        matching_cards = storage.find_matching(
            file_paths=file_refs,
            task_description=task,
            limit=3,
        )

        if not matching_cards:
            return ''

        # Format warnings
        warnings = []
        for card in matching_cards:
            warning = f"⚠️ Note: In Run #{card.run_id}, attempting '{card.task_description}' failed with {card.error_type}: {card.error_message}"
            if card.file_path:
                warning += f' at {card.file_path}'
            if card.line_number:
                warning += f':{card.line_number}'
            warning += '. Consider alternative approaches.'
            warnings.append(warning)

        return '\n\n' + '\n'.join(warnings) + '\n'
    except Exception:
        # Don't let failure warnings break the chat system
        return ''


def execute_shell_command(command: str, root: Path) -> None:
    """Execute a shell command safely and display output.

    Args:
        command: The shell command to execute
        root: The workspace root directory
    """
    # Security check: block destructive commands using proper parsing
    DANGEROUS_EXECUTABLES = frozenset({
        'rm', 'rmdir', 'mkfs', 'dd', 'format', 'fdisk', 'shred', 'wipe'
    })
    
    # Parse command safely first
    try:
        # Use shlex to properly parse the command while preserving quoted arguments
        args = shlex.split(command)
        if not args:
            print('[TeaAgent] Error: Empty command')
            return
    except ValueError as exc:
        print(f'[TeaAgent] Error: Invalid command syntax: {exc}')
        return
    
    # Check if the executable is dangerous
    executable = args[0].lower()
    if executable in DANGEROUS_EXECUTABLES:
        print(
            '[TeaAgent] Error: Destructive command not allowed in shell escape. Use full terminal.'
        )
        return
    
    # Additional checks for specific dangerous patterns
    if executable == 'chmod' and '777' in args:
        print('[TeaAgent] Error: chmod 777 not allowed in shell escape.')
        return
    
    if executable == 'chown' and '-R' in args:
        print('[TeaAgent] Error: chown -R not allowed in shell escape.')
        return
        print(f'[TeaAgent] Error: Invalid command syntax: {exc}')
        return

    # Execute the command
    try:
        print(f'[TeaAgent] Executing: {command}')
        result = subprocess.run(
            args,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,  # Prevent hanging commands
        )

        # Display output
        if result.stdout:
            print(result.stdout, end='')
        if result.stderr:
            print(result.stderr, end='', file=sys.stderr)

        # Show exit code if non-zero
        if result.returncode != 0:
            print(f'[TeaAgent] Command exited with code {result.returncode}')
        else:
            print('[TeaAgent] Command completed successfully')

    except subprocess.TimeoutExpired:
        print('[TeaAgent] Error: Command timed out after 30 seconds')
    except FileNotFoundError:
        print(f'[TeaAgent] Error: Command not found: {args[0]}')
    except Exception as exc:
        print(f'[TeaAgent] Error executing command: {exc}')


def complete_file_path(text: str, root: Path) -> list[str]:
    """Complete file paths starting with @.

    Args:
        text: The text to complete (including @ prefix)
        root: The workspace root directory

    Returns:
        List of completion suggestions
    """
    if not text.startswith('@'):
        return []

    # Remove @ prefix and get partial path
    partial_path = text[1:]

    # Determine the directory to search
    if '/' in partial_path:
        # Has directory component
        dir_part = partial_path.rsplit('/', 1)[0]
        file_part = partial_path.rsplit('/', 1)[1] if '/' in partial_path else ''
        search_dir = root / dir_part
    else:
        # Just filename in root
        dir_part = ''
        file_part = partial_path
        search_dir = root

    # Ensure search directory exists and is within root
    try:
        search_dir = search_dir.resolve()
        if not search_dir.exists() or not search_dir.is_dir():
            return []
        if not search_dir.is_relative_to(root.resolve()):
            return []
    except Exception:
        return []

    # Get matching files and directories
    completions = []
    try:
        for item in search_dir.iterdir():
            # Skip hidden files/directories (except .teaagent)
            if item.name.startswith('.') and item.name != '.teaagent':
                continue

            # Check if matches partial
            if item.name.lower().startswith(file_part.lower()):
                # Build completion path
                if dir_part:
                    completion = f'@{dir_part}/{item.name}'
                else:
                    completion = f'@{item.name}'

                # Add trailing slash for directories
                if item.is_dir():
                    completion += '/'

                completions.append(completion)
    except Exception:
        pass

    return sorted(completions)


def complete_symbol(text: str, root: Path) -> list[str]:
    """Complete symbol names (classes, functions) starting with @.

    Args:
        text: The text to complete (including @ prefix)
        root: The workspace root directory

    Returns:
        List of completion suggestions
    """
    if not text.startswith('@'):
        return []

    # Remove @ prefix and get partial symbol name
    partial_symbol = text[1:]

    # Try to use code ontology if available
    try:
        from teaagent.code_ontology import CodeOntologyBuilder

        # Build ontology for the workspace
        builder = CodeOntologyBuilder(root)
        builder.build_from_directory()
        ontology = builder

        # Get all nodes (symbols)
        completions = []
        for node in ontology.nodes:
            # Check if symbol name matches partial
            if node.name.lower().startswith(partial_symbol.lower()):
                # Format: @symbol_name (in file_path)
                completion = f'@{node.name}'
                completions.append(completion)

        return sorted(set(completions))
    except Exception:
        # Fallback: simple file-based symbol search
        return []


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

    print('[TeaAgent] Suspending session to background mode...')

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
        'audit_trail': {
            'suspension_time': __import__('time').time(),
            'original_mode': 'repl',
            'transition_type': 'keyboard_to_robot',
        },
    }

    suspension_file = tea_dir / f'suspension-{run_id}.json'
    try:
        suspension_file.write_text(
            json.dumps(suspension_data, indent=2), encoding='utf-8'
        )
    except Exception as exc:
        print(f'[TeaAgent] Error saving suspension state: {exc}')
        return ''

    # Create Git sandbox branch if workspace is dirty
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=root,
            capture_output=True,
            text=True,
        )

        if result.stdout.strip():
            print(
                '[TeaAgent] Workspace has uncommitted changes, creating sandbox branch...'
            )
            branch_name = f'suspended-{run_id}'

            # Check if branch already exists
            check_result = subprocess.run(
                ['git', 'branch', '--list', branch_name],
                cwd=root,
                capture_output=True,
                text=True,
            )

            if check_result.stdout.strip():
                # Branch exists, use timestamp to make unique
                import time as time_module

                branch_name = f'suspended-{run_id}-{int(time_module.time())}'

            subprocess.run(
                ['git', 'checkout', '-b', branch_name], cwd=root, capture_output=True
            )
            suspension_data['sandbox_branch'] = branch_name
            suspension_data['audit_trail']['sandbox_branch'] = branch_name
            suspension_file.write_text(
                json.dumps(suspension_data, indent=2), encoding='utf-8'
            )
            print(f'[TeaAgent] Created sandbox branch: {branch_name}')
    except FileNotFoundError:
        print('[TeaAgent] Git not found, skipping sandbox branch creation')
    except Exception as exc:
        print(f'[TeaAgent] Warning: Could not create sandbox branch: {exc}')

    print('[TeaAgent] Session suspended successfully!')
    print(f'[TeaAgent] Run ID: {run_id}')
    print(f'[TeaAgent] To attach: teaagent attach {run_id} --follow')
    print(f'[TeaAgent] To resume: teaagent resume {run_id}')
    print(f'[TeaAgent] To review: teaagent agent interactive-review {run_id}')
    print('[TeaAgent] Note: Background execution requires manual setup')

    return run_id


def chat_command(args: argparse.Namespace) -> int:
    """Run the interactive chat REPL (delegates to TUI with --chat-mode)."""
    from teaagent.tui import run_tui

    provider: str | None = getattr(args, 'provider', None) or None
    model: str | None = getattr(args, 'model', None) or None
    allow_destructive = getattr(args, 'allow_destructive', False)
    permission_mode_str: str = getattr(args, 'permission_mode', 'prompt') or 'prompt'
    max_iterations = getattr(args, 'max_iterations', 10)
    max_tool_calls = getattr(args, 'max_tool_calls', 10)
    max_estimated_cost_cents = getattr(args, 'max_estimated_cost_cents', 0)
    enable_subagent = getattr(args, 'subagent', False)
    max_subagent_depth = getattr(args, 'max_subagent_depth', 1)
    heartbeat_seconds = getattr(args, 'heartbeat', 0.0)
    stream = getattr(args, 'stream', False)
    enable_git_tools = getattr(args, 'enable_git_tools', False)
    skill_search_dirs = getattr(args, 'skill_search_dirs', None)
    memory_limit_arg = getattr(args, 'memory_limit', None)
    memory_limit = memory_limit_arg if memory_limit_arg is not None else 5

    try:
        return run_tui(
            database=':memory:',
            provider=provider,
            model=model,
            root=args.root if hasattr(args, 'root') else '.',
            allow_destructive=allow_destructive,
            permission_mode=parse_permission_mode(permission_mode_str),
            chat=True,
            input_fn=None,
            run_setup=False,
            setup_write_env=False,
            stream=stream,
            subagent=enable_subagent,
            max_iterations=max_iterations,
            max_tool_calls=max_tool_calls,
            max_subagent_depth=max_subagent_depth,
            heartbeat_seconds=heartbeat_seconds,
            enable_git_tools=enable_git_tools,
            skill_search_dirs=skill_search_dirs,
            memory_limit=memory_limit,
            max_estimated_cost_cents=max_estimated_cost_cents,
        )
    except KeyboardInterrupt:
        print('\n[TeaAgent] Chat interrupted by user')
        return 130
    except Exception as exc:
        print(f'[TeaAgent] Error: {exc}', file=sys.stderr)
        return 1


def run_chat_repl(config: ChatAgentConfig, initial_task: Optional[str] = None) -> int:
    """Run the interactive chat REPL loop."""
    print('[TeaAgent] Chat mode initialized')
    print(f'[TeaAgent] Provider: {config.model or "default"}')
    print(f'[TeaAgent] Permission mode: {config.permission_mode.value}')
    print('[TeaAgent] Type your task or /exit to quit')
    print()

    # Session cost accumulator
    session_cost_cents = 0.0

    # Context compactor for session management
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

    def tab_completer(text: str, state: int) -> Optional[str]:
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
    runtime_max_cost_cents = config.max_estimated_cost_cents or 1000

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
    max_cost_budget_cents = config.max_estimated_cost_cents or 1000  # Default $10

    # File watcher for live context synchronization
    file_watcher = None
    watcher_running = False

    def on_file_changed(file_path: str, event_type: str) -> None:
        """Callback for file watcher events.

        Args:
            file_path: Path to the changed file
            event_type: Type of event ('modified' or 'deleted')
        """
        nonlocal session_context, targeted_files

        try:
            from datetime import datetime

            from teaagent.memory.pinned_file import PinnedFileStorage

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
            import sys

            print(
                f'[TeaAgent] Warning: Error handling file change: {exc}',
                file=sys.stderr,
            )

    def start_file_watcher() -> None:
        """Start the file watcher if there are pinned files."""
        nonlocal file_watcher, watcher_running

        try:
            from teaagent.memory.file_watcher import FileWatcher
            from teaagent.memory.pinned_file import PinnedFileStorage

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
            import sys

            print(
                f'[TeaAgent] Warning: Failed to start file watcher: {exc}',
                file=sys.stderr,
            )

    def stop_file_watcher() -> None:
        """Stop the file watcher."""
        nonlocal file_watcher, watcher_running

        if file_watcher and watcher_running:
            try:
                file_watcher.stop()
                watcher_running = False
            except Exception:
                pass

    def create_checkpoint() -> bool:
        """Create a git stash checkpoint to protect pre-session changes."""
        nonlocal checkpoint_created, checkpoint_ref
        import subprocess

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
        nonlocal checkpoint_created, checkpoint_ref
        import subprocess

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
                # Revert all working directory changes first
                subprocess.run(
                    ['git', 'checkout', '--', '.'],
                    cwd=config.root,
                    capture_output=True,
                    text=True,
                )

                # Then pop the stash
                subprocess.run(
                    ['git', 'stash', 'pop'],
                    cwd=config.root,
                    capture_output=True,
                    text=True,
                )
                print(f'[TeaAgent] Restored checkpoint: {checkpoint_ref}')
            else:
                print(
                    '[TeaAgent] No checkpoint stash found (clean workspace or checkpoint not created)'
                )
                return False

            return True
        except FileNotFoundError:
            print('[TeaAgent] Git not found in PATH')
            return False
        except Exception as exc:
            print(f'[TeaAgent] Error restoring checkpoint: {exc}')
            return False

    def add_targeted_file(path_str: str) -> bool:
        """Add a file or directory to the targeted context."""
        try:
            path = (config.root / path_str).resolve()
            if not path.exists():
                print(f'[TeaAgent] Error: Path does not exist: {path}')
                return False
            # Use is_relative_to for robust path validation that handles symlinks
            if not path.is_relative_to(config.root.resolve()):
                print(f'[TeaAgent] Error: Path escapes workspace root: {path}')
                return False
            targeted_files.add(path)
            print(f'[TeaAgent] Added to context: {path}')
            return True
        except Exception as exc:
            print(f'[TeaAgent] Error adding path: {exc}')
            return False

    def drop_targeted_file(path_str: str) -> bool:
        """Remove a file or directory from the targeted context."""
        try:
            path = (config.root / path_str).resolve()
            if path in targeted_files:
                targeted_files.remove(path)
                print(f'[TeaAgent] Removed from context: {path}')
                return True
            else:
                print(f'[TeaAgent] Path not in context: {path}')
                return False
        except Exception as exc:
            print(f'[TeaAgent] Error removing path: {exc}')
            return False

    def show_targeted_context() -> None:
        """Display currently targeted files and context info."""
        if not targeted_files:
            print('[TeaAgent] No files currently targeted (full workspace context)')
        else:
            print(f'[TeaAgent] Targeted files ({len(targeted_files)}):')
            for path in sorted(targeted_files):
                print(f'  - {path.relative_to(config.root)}')

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
            print(f'[TeaAgent] Budget limit: ${max_cost_budget_cents / 100:.2f}')
            return True
        except Exception as exc:
            print(f'[TeaAgent] Error setting effort level: {exc}')
            return False

    def show_effort_status() -> None:
        """Display current effort throttling status."""
        print(f'[TeaAgent] Effort level: {effort_level}')
        print(f'[TeaAgent] Budget limit: ${max_cost_budget_cents / 100:.2f}')
        print(f'[TeaAgent] Session cost: ${session_cost_cents / 100:.2f}')
        print(
            f'[TeaAgent] Remaining budget: ${(max_cost_budget_cents - session_cost_cents) / 100:.2f}'
        )

    # Automatic checkpoint creation disabled for data safety
    # Users should explicitly create checkpoints when needed to avoid hiding changes
    # create_checkpoint()

    # Start file watcher if there are pinned files
    start_file_watcher()

    # If initial task provided, execute it first
    if initial_task:
        print(f'[TeaAgent] Executing initial task: {initial_task}')
        # Inject failure warnings
        task_with_warnings = initial_task + get_failure_warnings(
            initial_task, config.root
        )
        # Create updated config with runtime values
        from dataclasses import replace

        updated_config = replace(
            config,
            model=runtime_model,
            max_estimated_cost_cents=runtime_max_cost_cents,
        )
        result = run_chat_agent(
            task=task_with_warnings, adapter=adapter, config=updated_config
        )
        if result.status != 'completed':
            return 1
        # Placeholder cost tracking for initial task
        session_cost_cents += 10
        session_context['observations'].append(
            {
                'task': initial_task,
                'result': result,
                'cost_cents': 10,
            }
        )
        print()

    # REPL loop
    while True:
        try:
            # Build prompt with pinned file indicator
            try:
                from teaagent.memory.pinned_file import PinnedFileStorage

                storage = PinnedFileStorage(config.root)
                pinned_count = len(storage.list_all())
                prompt = (
                    f'teaagent📌{pinned_count}> ' if pinned_count > 0 else 'teaagent> '
                )
            except Exception:
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
                print('[TeaAgent] Compacting session context...')
                compaction_result = compactor.compact(session_context)
                print('[TeaAgent] Compaction complete:')
                print(f'  - Tokens saved: ~{compaction_result.tokens_saved}')
                print(
                    f'  - Compression ratio: {compaction_result.compression_ratio:.2%}'
                )
                print(
                    f'  - Total compactions: {session_context.get("compaction_count", 0)}'
                )
                print(
                    f'  - Observations retained: {len(session_context.get("observations", []))}'
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
                        '[TeaAgent] Interactive session converted to background task.'
                    )
                    print('[TeaAgent] You can now safely exit the REPL.')
                    print(
                        f"[TeaAgent] Use 'teaagent attach {run_id} --follow' to monitor progress."
                    )
                else:
                    print(
                        '[TeaAgent] Suspension failed. Continuing in interactive mode.'
                    )
                continue

            # Handle cost command
            if user_input == '/cost':
                print(f'[TeaAgent] Session cost: ${session_cost_cents / 100:.2f}')
                print(
                    '[TeaAgent] Estimated cost for next task will be shown before execution'
                )
                continue

            # Handle diff command
            if user_input == '/diff':
                print('[TeaAgent] Showing git diff for current session...')
                import subprocess

                try:
                    proc_result = subprocess.run(
                        ['git', 'diff', '--color=always'],
                        cwd=config.root,
                        capture_output=True,
                        text=True,
                    )
                    if proc_result.stdout:
                        print(proc_result.stdout)
                    else:
                        print('[TeaAgent] No changes detected in working directory')
                except FileNotFoundError:
                    print('[TeaAgent] Git not found in PATH')
                except Exception as exc:
                    print(f'[TeaAgent] Error running git diff: {exc}')
                continue

            # Handle context command
            if user_input == '/context':
                show_targeted_context()
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

            # Handle add command
            if user_input.startswith('/add '):
                path_arg = user_input[5:].strip()
                if path_arg:
                    add_targeted_file(path_arg)
                else:
                    print('[TeaAgent] Usage: /add <path>')
                continue

            # Handle drop command
            if user_input.startswith('/drop '):
                path_arg = user_input[6:].strip()
                if path_arg:
                    drop_targeted_file(path_arg)
                else:
                    print('[TeaAgent] Usage: /drop <path>')
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
                print('[TeaAgent] Undoing last change using checkpoint...')
                if restore_checkpoint():
                    print('[TeaAgent] Undo completed successfully')
                else:
                    print('[TeaAgent] Undo failed - falling back to git checkout')
                    import subprocess

                    try:
                        proc_result = subprocess.run(
                            ['git', 'checkout', '--', '.'],
                            cwd=config.root,
                            capture_output=True,
                            text=True,
                        )
                        if proc_result.returncode == 0:
                            print('[TeaAgent] Fallback undo completed')
                        else:
                            print(f'[TeaAgent] Error: {proc_result.stderr}')
                    except Exception as exc:
                        print(f'[TeaAgent] Error in fallback undo: {exc}')
                continue

            # Execute task
            print(f'[TeaAgent] Executing: {user_input}')
            # Inject failure warnings
            task_with_warnings = user_input + get_failure_warnings(
                user_input, config.root
            )
            # Create updated config with runtime values
            from dataclasses import replace

            updated_config = replace(
                config,
                model=runtime_model,
                max_estimated_cost_cents=runtime_max_cost_cents,
            )
            result = run_chat_agent(
                task=task_with_warnings, adapter=adapter, config=updated_config
            )

            if result != 0:
                print(f'[TeaAgent] Task failed with exit code {result}')
            else:
                # In a full implementation, we would track actual cost here
                # For now, we'll increment a placeholder
                session_cost_cents += 10  # Placeholder: 10 cents per task

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


def print_chat_help() -> None:
    """Print chat REPL help."""
    print('[TeaAgent] Chat Commands:')
    print('  /exit, /quit, q, quit, exit  - Exit chat mode')
    print('  /help, /?, help, ?         - Show this help')
    print('  /cost                      - Show session cost')
    print('  /compact                   - Compact session context to save tokens')
    print('  /clear                     - Clear conversation history')
    print('  /diff                      - Show git diff for current session')
    print('  /background, /handoff       - Suspend session to background mode')
    print('  /context                   - Show targeted context files')
    print('  /add <path>                - Add file/directory to context')
    print('  /drop <path>               - Remove file/directory from context')
    print('  /provider <name>           - Switch LLM provider')
    print('  /model <name>              - Switch model')
    print('  /effort <low|normal|high>  - Set effort throttling level')
    print('  /budget                    - Show budget status')
    print('  /checkpoint                - Create manual git checkpoint')
    print('  /undo                      - Undo all changes (using checkpoint)')
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
