"""``teaagent approval preset`` command.

Extracted from ``approval.py`` (A-P2-2 god-module split). Re-exported from
``approval.py`` so the public surface is unchanged.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from teaagent.ergonomics.approval_store import ApprovalPresetStore

from .approval import _wrap_approval_store_errors, print_json


def approval_preset_command(args: argparse.Namespace) -> int:
    def _preset() -> int:
        store = ApprovalPresetStore(args.root)
        preset_name = args.name

        # Define preset templates
        presets: dict[str, dict[str, Any]] = {
            'dev-safe': {
                'description': 'Allow workspace writes, pytest, git diff/status; deny secrets/** and deploy commands',
                'grants': [
                    {
                        'tool_name': 'workspace_write_file',
                        'scope': 'session',
                        'path_globs': ['src/**', 'tests/**', '*.py', '*.md', '*.txt'],
                        'permission_mode': 'workspace-write',
                    },
                    {
                        'tool_name': 'workspace_run_shell_mutate',
                        'scope': 'session',
                        'command_prefixes': ['pytest ', 'git diff', 'git status'],
                    },
                    {
                        'tool_name': 'workspace_run_shell_mutate',
                        'scope': 'deny',
                        'command_prefixes': ['deploy', 'prod', 'production'],
                    },
                    {
                        'tool_name': 'workspace_write_file',
                        'scope': 'deny',
                        'path_globs': ['secrets/**', '.env*', '*.key', '*.pem'],
                    },
                ],
            },
            'ci-safe': {
                'description': 'Read-only mode for CI environments',
                'grants': [
                    {
                        'tool_name': 'workspace_read_file',
                        'scope': 'always',
                    },
                    {
                        'tool_name': 'workspace_run_shell_mutate',
                        'scope': 'session',
                        'command_prefixes': ['git diff', 'git status', 'cat ', 'ls '],
                    },
                ],
            },
            'strict': {
                'description': 'Deny all destructive tools, require explicit approval',
                'grants': [
                    {
                        'tool_name': 'workspace_write_file',
                        'scope': 'deny',
                    },
                    {
                        'tool_name': 'workspace_run_shell_mutate',
                        'scope': 'deny',
                    },
                ],
            },
        }

        if preset_name not in presets:
            print_json({'status': 'error', 'message': f'Unknown preset: {preset_name}'})
            return 1

        preset = presets[preset_name]

        # Check for duplicate grants to avoid bloat
        existing_grants = store.list_grants()
        existing_signatures = {
            (
                g.tool_name,
                g.scope,
                g.permission_mode,
                tuple(sorted(g.path_globs)),
                tuple(sorted(g.command_prefixes)),
            )
            for g in existing_grants
        }

        applied = []
        skipped = []
        for grant_config in preset['grants']:
            # Compute signature for deduplication
            signature = (
                grant_config['tool_name'],
                grant_config['scope'],
                grant_config.get('permission_mode'),
                tuple(sorted(grant_config.get('path_globs', []))),
                tuple(sorted(grant_config.get('command_prefixes', []))),
            )
            if signature in existing_signatures:
                skipped.append(grant_config)
                continue

            # Deny scope requires explicit patterns to prevent implicit global denials
            if grant_config['scope'] == 'deny':
                path_globs = grant_config.get('path_globs') or None
                command_prefixes = grant_config.get('command_prefixes') or None
                if not path_globs and not command_prefixes:
                    print(
                        f'[warning] Skipping deny grant for {grant_config["tool_name"]}: '
                        f'deny scope requires at least one path_glob or command_prefix',
                        file=sys.stderr,
                    )
                    skipped.append(grant_config)
                    continue
                grant = store.deny(
                    grant_config['tool_name'],
                    path_globs=path_globs,
                    command_prefixes=command_prefixes,
                )
            else:
                # For non-deny scopes, session allows None, others require patterns
                if grant_config['scope'] == 'session':
                    path_globs = grant_config.get('path_globs') or None
                    command_prefixes = grant_config.get('command_prefixes') or None
                else:
                    path_globs = grant_config.get('path_globs') or None
                    command_prefixes = grant_config.get('command_prefixes') or None
                    if not path_globs and not command_prefixes:
                        print(
                            f'[warning] Skipping grant for {grant_config["tool_name"]}: '
                            f'scope={grant_config["scope"]} requires at least one path_glob or command_prefix',
                            file=sys.stderr,
                        )
                        skipped.append(grant_config)
                        continue
                grant = store.grant(
                    grant_config['tool_name'],
                    scope=grant_config['scope'],
                    permission_mode=grant_config.get('permission_mode'),
                    path_globs=path_globs,
                    command_prefixes=command_prefixes,
                )
            applied.append(grant.to_dict())
            existing_signatures.add(signature)

        print_json(
            {
                'status': 'applied',
                'preset': preset_name,
                'description': preset['description'],
                'grants_applied': applied,
                'grants_skipped': skipped,
            }
        )
        return 0

    return _wrap_approval_store_errors(_preset)
