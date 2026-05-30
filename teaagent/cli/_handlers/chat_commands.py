"""Chat REPL command handlers for memory, pinning, and shell operations."""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from teaagent.memory.failure_card import FailureCardStorage
from teaagent.memory.pinned_file import PinnedFileStorage


def handle_memory_failures(root: Path) -> None:
    """Handle /memory failures command to list all failure cards.

    Args:
        root: The workspace root directory
    """
    try:
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
    # Security check: block destructive commands
    destructive_patterns = [
        'rm -rf /',
        'rm -rf /*',
        'mkfs',
        'dd if=',
        '> /dev/sd',
        '> /dev/hd',
        'format',
        'del /f /q',
    ]
    
    command_lower = command.lower()
    for pattern in destructive_patterns:
        if pattern in command_lower:
            print(f'[TeaAgent] Error: Destructive command blocked for safety: {command}')
            return

    try:
        # Parse command safely
        import shlex
        args = shlex.split(command)
        
        # Execute with timeout
        result = subprocess.run(
            args,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        # Display output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
            
    except subprocess.TimeoutExpired:
        print('[TeaAgent] Error: Command timed out after 30 seconds')
    except FileNotFoundError:
        print(f'[TeaAgent] Error: Command not found: {args[0]}')
    except Exception as exc:
        print(f'[TeaAgent] Error executing command: {exc}')
