"""Interactive chat REPL handler for teaagent.

This module provides a state-preserving interactive REPL command loop
that allows users to interact with the agent without restarting the process.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.config_loader import ConfigResolver
from teaagent.context import ContextCompactor
from teaagent.llm import available_providers, create_llm_adapter
from teaagent.policy import parse_permission_mode
import subprocess
import shlex
import sys
import os
import glob
import readline


def execute_shell_command(command: str, root: Path) -> None:
    """Execute a shell command safely and display output.
    
    Args:
        command: The shell command to execute
        root: The workspace root directory
    """
    # Security check: block destructive commands
    destructive_patterns = [
        'rm -rf /',
        'rm -rf ~/',
        'rm -rf .*',
        'mkfs',
        'dd if=',
        ':(){:|:&};:',  # fork bomb
        'chmod 777 /',
        'chown -R',
    ]
    
    command_lower = command.lower()
    for pattern in destructive_patterns:
        if pattern in command_lower:
            print(f"[TeaAgent] Error: Destructive command not allowed in shell escape. Use full terminal.")
            return
    
    # Parse command safely
    try:
        # Use shlex to properly parse the command while preserving quoted arguments
        args = shlex.split(command)
        if not args:
            print("[TeaAgent] Error: Empty command")
            return
    except ValueError as exc:
        print(f"[TeaAgent] Error: Invalid command syntax: {exc}")
        return
    
    # Execute the command
    try:
        print(f"[TeaAgent] Executing: {command}")
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
            print(f"[TeaAgent] Command exited with code {result.returncode}")
        else:
            print(f"[TeaAgent] Command completed successfully")
            
    except subprocess.TimeoutExpired:
        print("[TeaAgent] Error: Command timed out after 30 seconds")
    except FileNotFoundError:
        print(f"[TeaAgent] Error: Command not found: {args[0]}")
    except Exception as exc:
        print(f"[TeaAgent] Error executing command: {exc}")


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
                    completion = f"@{dir_part}/{item.name}"
                else:
                    completion = f"@{item.name}"
                
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
        ontology = builder.build()
        
        # Get all nodes (symbols)
        completions = []
        for node in ontology.nodes:
            # Check if symbol name matches partial
            if node.name.lower().startswith(partial_symbol.lower()):
                # Format: @symbol_name (in file_path)
                completion = f"@{node.name}"
                completions.append(completion)
        
        return sorted(set(completions))
    except Exception:
        # Fallback: simple file-based symbol search
        return []



def chat_command(args: argparse.Namespace) -> int:
    """Run the interactive chat REPL."""
    root = Path(args.root).resolve()
    
    # Override with CLI arguments (config loading happens in ChatAgentConfig.from_root)
    model = args.model
    permission_mode = parse_permission_mode(args.permission_mode) if args.permission_mode else None
    
    # Build chat agent config
    chat_config = ChatAgentConfig.from_root(
        root,
        model=model,
        permission_mode=permission_mode,
        max_iterations=args.max_iterations,
        max_tool_calls=args.max_tool_calls,
        max_estimated_cost_cents=args.max_estimated_cost_cents,
        allow_destructive=args.allow_destructive,
        memory_limit=args.memory_limit,
        enable_subagent=args.enable_subagent,
        max_subagent_depth=args.max_subagent_depth,
        heartbeat_seconds=args.heartbeat,
        stream=args.stream,
        enable_git_tools=args.enable_git_tools,
        skill_search_dirs=args.skill_search_dirs,
    )
    
    # Run the chat REPL
    try:
        return run_chat_repl(chat_config, args.task)
    except KeyboardInterrupt:
        print("\n[TeaAgent] Chat interrupted by user")
        return 130
    except Exception as exc:
        print(f"[TeaAgent] Error: {exc}", file=sys.stderr)
        return 1


def run_chat_repl(config: ChatAgentConfig, initial_task: Optional[str] = None) -> int:
    """Run the interactive chat REPL loop."""
    print(f"[TeaAgent] Chat mode initialized")
    print(f"[TeaAgent] Provider: {config.model or 'default'}")
    print(f"[TeaAgent] Permission mode: {config.permission_mode.value}")
    print(f"[TeaAgent] Type your task or /exit to quit")
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
    session_context = {
        'observations': [],
        'compaction_count': 0,
    }
    
    # Surgical context targeting - active file set
    targeted_files = set[Path]()
    
    # Auto-stash checkpoint for safe undo
    checkpoint_created = False
    checkpoint_ref = None
    
    # Hot-swappable model configuration
    current_provider = config.model.split('/')[0] if config.model and '/' in config.model else None
    current_model = config.model
    
    # Tab completion setup
    def tab_completer(text: str, state: int) -> Optional[str]:
        """Tab completion handler for readline."""
        if state == 0:
            # First call - generate completions
            if text.startswith('@'):
                # File/symbol completion
                completions = complete_file_path(text, config.root)
                if not completions:
                    completions = complete_symbol(text, config.root)
                tab_completer.matches = completions
            else:
                # Default to no completion
                tab_completer.matches = []
        
        try:
            return tab_completer.matches[state]
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
    provider = config.model.split('/')[0] if config.model and '/' in config.model else 'gpt'
    model = config.model.split('/', 1)[1] if config.model and '/' in config.model else None
    adapter = create_llm_adapter(provider, model=model)
    
    # Effort throttling configuration
    effort_level = "normal"  # low, normal, high
    max_cost_budget_cents = config.max_estimated_cost_cents or 1000  # Default $10
    
    def create_checkpoint() -> bool:
        """Create a git stash checkpoint to protect pre-session changes."""
        nonlocal checkpoint_created, checkpoint_ref
        import subprocess
        try:
            # Create a timestamped checkpoint
            timestamp = __import__('time').time()
            checkpoint_ref = f"teaagent-checkpoint-{int(timestamp)}"
            
            # Stash current changes with checkpoint reference
            result = subprocess.run(
                ['git', 'stash', 'push', '-m', checkpoint_ref],
                cwd=config.root,
                capture_output=True,
                text=True,
            )
            
            if result.returncode == 0:
                checkpoint_created = True
                print(f"[TeaAgent] Created checkpoint: {checkpoint_ref}")
                return True
            else:
                # If stash fails (no changes to stash), that's okay
                if "No local changes to save" in result.stdout:
                    checkpoint_created = True
                    print(f"[TeaAgent] No changes to stash (clean workspace)")
                    return True
                print(f"[TeaAgent] Warning: Could not create checkpoint: {result.stderr}")
                return False
        except FileNotFoundError:
            print("[TeaAgent] Git not found in PATH")
            return False
        except Exception as exc:
            print(f"[TeaAgent] Error creating checkpoint: {exc}")
            return False
    
    def restore_checkpoint() -> bool:
        """Restore the git checkpoint to undo changes."""
        nonlocal checkpoint_created, checkpoint_ref
        import subprocess
        try:
            if not checkpoint_created:
                print("[TeaAgent] No checkpoint to restore")
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
                print(f"[TeaAgent] Restored checkpoint: {checkpoint_ref}")
            else:
                print("[TeaAgent] No checkpoint stash found (clean workspace or checkpoint not created)")
                return False
            
            return True
        except FileNotFoundError:
            print("[TeaAgent] Git not found in PATH")
            return False
        except Exception as exc:
            print(f"[TeaAgent] Error restoring checkpoint: {exc}")
            return False
    
    def add_targeted_file(path_str: str) -> bool:
        """Add a file or directory to the targeted context."""
        try:
            path = (config.root / path_str).resolve()
            if not path.exists():
                print(f"[TeaAgent] Error: Path does not exist: {path}")
                return False
            # Use is_relative_to for robust path validation that handles symlinks
            if not path.is_relative_to(config.root.resolve()):
                print(f"[TeaAgent] Error: Path escapes workspace root: {path}")
                return False
            targeted_files.add(path)
            print(f"[TeaAgent] Added to context: {path}")
            return True
        except Exception as exc:
            print(f"[TeaAgent] Error adding path: {exc}")
            return False
    
    def drop_targeted_file(path_str: str) -> bool:
        """Remove a file or directory from the targeted context."""
        try:
            path = (config.root / path_str).resolve()
            if path in targeted_files:
                targeted_files.remove(path)
                print(f"[TeaAgent] Removed from context: {path}")
                return True
            else:
                print(f"[TeaAgent] Path not in context: {path}")
                return False
        except Exception as exc:
            print(f"[TeaAgent] Error removing path: {exc}")
            return False
    
    def show_targeted_context() -> None:
        """Display currently targeted files and context info."""
        if not targeted_files:
            print("[TeaAgent] No files currently targeted (full workspace context)")
        else:
            print(f"[TeaAgent] Targeted files ({len(targeted_files)}):")
            for path in sorted(targeted_files):
                print(f"  - {path.relative_to(config.root)}")
    
    def swap_provider(provider_name: str) -> bool:
        """Hot-swap the LLM provider during the session."""
        nonlocal current_provider, current_model, runtime_model, adapter
        try:
            if provider_name not in available_providers():
                print(f"[TeaAgent] Error: Unknown provider '{provider_name}'")
                print(f"[TeaAgent] Available providers: {', '.join(available_providers())}")
                return False
            
            current_provider = provider_name
            # Rebuild the model string with new provider
            if current_model and '/' in current_model:
                current_model = f"{provider_name}/{current_model.split('/', 1)[1]}"
            else:
                current_model = provider_name
            
            runtime_model = current_model
            
            # Recreate adapter with new provider
            model_part = current_model.split('/', 1)[1] if '/' in current_model else None
            adapter = create_llm_adapter(provider_name, model=model_part)
            
            print(f"[TeaAgent] Provider switched to: {provider_name}")
            print(f"[TeaAgent] Current model: {current_model}")
            return True
        except Exception as exc:
            print(f"[TeaAgent] Error switching provider: {exc}")
            return False
    
    def swap_model(model_name: str) -> bool:
        """Hot-swap the model during the session."""
        nonlocal current_model, runtime_model, adapter
        try:
            if current_provider:
                new_model = f"{current_provider}/{model_name}"
            else:
                new_model = model_name
            
            current_model = new_model
            runtime_model = current_model
            
            # Recreate adapter with new model
            provider = current_provider or 'gpt'
            adapter = create_llm_adapter(provider, model=model_name)
            
            print(f"[TeaAgent] Model switched to: {current_model}")
            return True
        except Exception as exc:
            print(f"[TeaAgent] Error switching model: {exc}")
            return False
    
    def set_effort_level(level: str) -> bool:
        """Set the effort throttling level for the session."""
        nonlocal effort_level, max_cost_budget_cents, runtime_max_cost_cents
        try:
            level = level.lower()
            if level not in ('low', 'normal', 'high'):
                print("[TeaAgent] Error: Effort level must be 'low', 'normal', or 'high'")
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
            
            print(f"[TeaAgent] Effort level set to: {level}")
            print(f"[TeaAgent] Budget limit: ${max_cost_budget_cents / 100:.2f}")
            return True
        except Exception as exc:
            print(f"[TeaAgent] Error setting effort level: {exc}")
            return False
    
    def show_effort_status() -> None:
        """Display current effort throttling status."""
        print(f"[TeaAgent] Effort level: {effort_level}")
        print(f"[TeaAgent] Budget limit: ${max_cost_budget_cents / 100:.2f}")
        print(f"[TeaAgent] Session cost: ${session_cost_cents / 100:.2f}")
        print(f"[TeaAgent] Remaining budget: ${(max_cost_budget_cents - session_cost_cents) / 100:.2f}")
    
    # Create initial checkpoint for safe undo
    create_checkpoint()
    
    # If initial task provided, execute it first
    if initial_task:
        print(f"[TeaAgent] Executing initial task: {initial_task}")
        # Create updated config with runtime values
        from dataclasses import replace
        updated_config = replace(
            config,
            model=runtime_model,
            max_estimated_cost_cents=runtime_max_cost_cents,
        )
        result = run_chat_agent(task=initial_task, adapter=adapter, config=updated_config)
        if result != 0:
            return result
        # Placeholder cost tracking for initial task
        session_cost_cents += 10
        session_context['observations'].append({
            'task': initial_task,
            'result': result,
            'cost_cents': 10,
        })
        print()
    
    # REPL loop
    while True:
        try:
            # Read user input
            user_input = input("teaagent> ").strip()
            
            if not user_input:
                continue
            
            # Handle shell escape hatch
            if user_input.startswith('!'):
                shell_command = user_input[1:].strip()
                if shell_command:
                    execute_shell_command(shell_command, config.root)
                else:
                    print("[TeaAgent] Usage: !<shell command>")
                continue
            
            # Handle exit commands
            if user_input in ('/exit', '/quit', 'q', 'quit', 'exit'):
                print("[TeaAgent] Goodbye!")
                return 0
            
            # Handle help
            if user_input in ('/help', '/?', 'help', '?'):
                print_chat_help()
                continue
            
            # Handle compact command
            if user_input == '/compact':
                print("[TeaAgent] Compacting session context...")
                compaction_result = compactor.compact(session_context)
                print(f"[TeaAgent] Compaction complete:")
                print(f"  - Tokens saved: ~{compaction_result.tokens_saved}")
                print(f"  - Compression ratio: {compaction_result.compression_ratio:.2%}")
                print(f"  - Total compactions: {session_context.get('compaction_count', 0)}")
                print(f"  - Observations retained: {len(session_context.get('observations', []))}")
                continue
            
            # Handle clear command
            if user_input == '/clear':
                print("[TeaAgent] Clearing conversation history...")
                session_context['observations'] = []
                session_context['compaction_count'] = 0
                targeted_files.clear()
                print("[TeaAgent] Conversation history cleared. Starting fresh.")
                continue
            
            # Handle cost command
            if user_input == '/cost':
                print(f"[TeaAgent] Session cost: ${session_cost_cents / 100:.2f}")
                print(f"[TeaAgent] Estimated cost for next task will be shown before execution")
                continue
            
            # Handle diff command
            if user_input == '/diff':
                print("[TeaAgent] Showing git diff for current session...")
                import subprocess
                try:
                    result = subprocess.run(
                        ['git', 'diff', '--color=always'],
                        cwd=config.root,
                        capture_output=True,
                        text=True,
                    )
                    if result.stdout:
                        print(result.stdout)
                    else:
                        print("[TeaAgent] No changes detected in working directory")
                except FileNotFoundError:
                    print("[TeaAgent] Git not found in PATH")
                except Exception as exc:
                    print(f"[TeaAgent] Error running git diff: {exc}")
                continue
            
            # Handle context command
            if user_input == '/context':
                show_targeted_context()
                continue
            
            # Handle add command
            if user_input.startswith('/add '):
                path_arg = user_input[5:].strip()
                if path_arg:
                    add_targeted_file(path_arg)
                else:
                    print("[TeaAgent] Usage: /add <path>")
                continue
            
            # Handle drop command
            if user_input.startswith('/drop '):
                path_arg = user_input[6:].strip()
                if path_arg:
                    drop_targeted_file(path_arg)
                else:
                    print("[TeaAgent] Usage: /drop <path>")
                continue
            
            # Handle provider command
            if user_input.startswith('/provider '):
                provider_arg = user_input[10:].strip()
                if provider_arg:
                    swap_provider(provider_arg)
                else:
                    print("[TeaAgent] Usage: /provider <name>")
                    print(f"[TeaAgent] Available providers: {', '.join(available_providers())}")
                continue
            
            # Handle model command
            if user_input.startswith('/model '):
                model_arg = user_input[7:].strip()
                if model_arg:
                    swap_model(model_arg)
                else:
                    print("[TeaAgent] Usage: /model <name>")
                    print(f"[TeaAgent] Current model: {current_model}")
                continue
            
            # Handle effort command
            if user_input.startswith('/effort '):
                effort_arg = user_input[8:].strip()
                if effort_arg:
                    set_effort_level(effort_arg)
                else:
                    print("[TeaAgent] Usage: /effort <low|normal|high>")
                    show_effort_status()
                continue
            
            # Handle budget command (alias for effort status)
            if user_input == '/budget':
                show_effort_status()
                continue
            
            # Handle undo command
            if user_input == '/undo':
                print("[TeaAgent] Undoing last change using checkpoint...")
                if restore_checkpoint():
                    print("[TeaAgent] Undo completed successfully")
                else:
                    print("[TeaAgent] Undo failed - falling back to git checkout")
                    import subprocess
                    try:
                        result = subprocess.run(
                            ['git', 'checkout', '--', '.'],
                            cwd=config.root,
                            capture_output=True,
                            text=True,
                        )
                        if result.returncode == 0:
                            print("[TeaAgent] Fallback undo completed")
                        else:
                            print(f"[TeaAgent] Error: {result.stderr}")
                    except Exception as exc:
                        print(f"[TeaAgent] Error in fallback undo: {exc}")
                continue
            
            # Execute task
            print(f"[TeaAgent] Executing: {user_input}")
            # Create updated config with runtime values
            from dataclasses import replace
            updated_config = replace(
                config,
                model=runtime_model,
                max_estimated_cost_cents=runtime_max_cost_cents,
            )
            result = run_chat_agent(task=user_input, adapter=adapter, config=updated_config)
            
            if result != 0:
                print(f"[TeaAgent] Task failed with exit code {result}")
            else:
                # In a full implementation, we would track actual cost here
                # For now, we'll increment a placeholder
                session_cost_cents += 10  # Placeholder: 10 cents per task
            
            print()
            
        except EOFError:
            print("\n[TeaAgent] Goodbye!")
            return 0
        except KeyboardInterrupt:
            print("\n[TeaAgent] Interrupted. Type /exit to quit or continue with next task")
            continue


def print_chat_help() -> None:
    """Print chat REPL help."""
    print("[TeaAgent] Chat Commands:")
    print("  /exit, /quit, q, quit, exit  - Exit chat mode")
    print("  /help, /?, help, ?         - Show this help")
    print("  /cost                      - Show session cost")
    print("  /compact                   - Compact session context to save tokens")
    print("  /clear                     - Clear conversation history")
    print("  /diff                      - Show git diff for current session")
    print("  /context                   - Show targeted context files")
    print("  /add <path>                - Add file/directory to context")
    print("  /drop <path>               - Remove file/directory from context")
    print("  /provider <name>           - Switch LLM provider")
    print("  /model <name>              - Switch model")
    print("  /effort <low|normal|high>  - Set effort throttling level")
    print("  /budget                    - Show budget status")
    print("  /undo                      - Undo all changes (using checkpoint)")
    print("  !<command>                 - Execute shell command (escape hatch)")
    print("  /context                   - Show currently targeted files")
    print("  /add <path>                - Add file/directory to targeted context")
    print("  /drop <path>               - Remove file/directory from context")
    print("  /provider <name>           - Switch LLM provider (anthropic, openai, etc.)")
    print("  /model <name>              - Switch model (claude-3-5-sonnet, gpt-4, etc.)")
    print("  /effort <low|normal|high>  - Set effort throttling level")
    print("  /budget                    - Show budget and effort status")
    print()
    print("[TeaAgent] Any other input will be executed as a task")
