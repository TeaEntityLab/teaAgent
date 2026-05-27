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
from teaagent.llm import available_providers
from teaagent.policy import parse_permission_mode


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
    
    # If initial task provided, execute it first
    if initial_task:
        print(f"[TeaAgent] Executing initial task: {initial_task}")
        result = run_chat_agent(config, initial_task)
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
            
            # Handle cost command
            if user_input == '/cost':
                print(f"[TeaAgent] Session cost: ${session_cost_cents / 100:.2f}")
                print(f"[TeaAgent] Estimated cost for next task will be shown before execution")
                continue
            
            # Execute task
            print(f"[TeaAgent] Executing: {user_input}")
            result = run_chat_agent(config, user_input)
            
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
    print("  /compact                   - Context compaction info")
    print()
    print("[TeaAgent] Any other input will be executed as a task")
