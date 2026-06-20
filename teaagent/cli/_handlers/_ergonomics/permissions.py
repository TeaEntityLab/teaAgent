from __future__ import annotations

import argparse
from typing import Any

from teaagent.cli._handlers._misc import print_json
from teaagent.types import PermissionMode

_PERMISSION_MODE_GUIDE: dict[str, dict[str, str]] = {
    'read-only': {
        'summary': 'Blocks all destructive tools. Safe for exploration and analysis.',
        'when_to_use': 'Code reviews, architecture questions, preflight checks, daily briefs, exploring unfamiliar code.',
        'allows': 'File reads, shell inspect (read-only commands like ls, git log).',
        'blocks': 'File writes (write_file, apply_patch, hash-edit), shell mutation (install, rm, git push).',
        'risk': 'low',
        'rollback': 'not needed (no mutations)',
        'tip': 'Start here for any task that does not require editing files.',
    },
    'workspace-write': {
        'summary': 'Allows file writes but blocks shell mutation. Safe for editing tasks.',
        'when_to_use': 'Patching files, writing docs, updating tests — any task that only needs file I/O.',
        'allows': 'File reads, file writes (write_file, apply_patch, hash-edit), shell inspect.',
        'blocks': 'Shell mutation (install, rm, git push, docker).',
        'risk': 'medium',
        'rollback': 'yes (UndoJournal.restore())',
        'tip': 'Use for editing tasks that do not need to run shell commands with side effects.',
    },
    'prompt': {
        'summary': 'Destructive tools pause for human-in-the-loop approval or require an approval token.',
        'when_to_use': 'Day-to-day autonomous work where you want to approve each destructive action.',
        'allows': 'File reads, file writes (after approval), shell inspect, shell mutate (after approval).',
        'blocks': 'Nothing permanently — every destructive tool can proceed after approval.',
        'risk': 'medium',
        'rollback': 'with approval (UndoJournal.restore())',
        'tip': 'The default mode. Best balance of safety and autonomy for daily use.',
    },
    'allow': {
        'summary': 'Allows all destructive tools for the session. No per-call approval required.',
        'when_to_use': 'Trusted automation, CI/CD pipelines, batch scripts where you have validated the task.',
        'allows': 'File reads, file writes, shell inspect, shell mutate (all without approval).',
        'blocks': 'Nothing.',
        'risk': 'high',
        'rollback': 'yes (UndoJournal.restore())',
        'tip': 'Only use in automated environments where you fully trust the input task.',
    },
    'danger-full-access': {
        'summary': 'Full access with no restrictions. Reserve for trusted automation only.',
        'when_to_use': 'Emergency recovery scripts, fully isolated automation, internal tooling with validated inputs.',
        'allows': 'Everything — file reads/writes, shell inspect/mutate, no approval gates.',
        'blocks': 'Nothing.',
        'risk': 'high',
        'rollback': 'yes (UndoJournal.restore())',
        'tip': 'Identical to "allow" in capability but signals extreme caution. Audit events are tagged for monitoring.',
    },
}


def permission_explain_command(args: argparse.Namespace) -> int:
    """Print the permission mode decision guide."""
    mode_names = [m.value for m in PermissionMode]
    selected = args.mode

    if selected:
        if selected not in mode_names:
            print_json(
                {
                    'error': f"Unknown mode '{selected}'. Choose from: {', '.join(mode_names)}"
                }
            )
            return 1
        modes_to_show = [selected]
    else:
        modes_to_show = mode_names

    result: dict[str, Any] = {'permission_modes': {}}
    for name in modes_to_show:
        result['permission_modes'][name] = _PERMISSION_MODE_GUIDE[name]

    print_json(result)
    return 0
