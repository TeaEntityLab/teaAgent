"""SURF-002 / SURF-011: multi-surface command parity registry.

VS Code commands must invoke the same CLI argv fragments documented here.
"""

from __future__ import annotations

from typing import Any

SURFACE_EXPLAIN_SCHEMA_VERSION = '1'

# command id -> substrings that must appear in vscode/src/extension.ts registration
IDE_COMMAND_CLI_PARITY: dict[str, list[str]] = {
    'teaagent.agentRun': ["'agent', 'run'"],
    'teaagent.agentDaily': ["'agent', 'daily'"],
    'teaagent.agentPlan': ["'agent', 'plan'"],
    'teaagent.agentStatus': ["'agent', 'status'"],
    'teaagent.agentEvidence': ["'agent', 'status'", "'--evidence'"],
    'teaagent.agentResume': ["'agent', 'resume'"],
    'teaagent.agentAttach': ["'agent', 'attach'"],
    'teaagent.agentUndo': ["'agent', 'undo'"],
    'teaagent.agentPreflight': ["'agent', 'preflight'"],
    'teaagent.agentApprovalPending': ["'approval', 'pending'"],
    'teaagent.agentApprovalApprove': ["'approval', 'approve'"],
    'teaagent.doctor': ["'doctor', 'all'"],
    'teaagent.startMcpServer': ["'mcp', 'serve', '--http'"],
    'teaagent.openTUI': ["+ ' tui'"],
}

# SURF-002 daily-workflow commands that must exist in the VS Code manifest
SURF002_REQUIRED_COMMANDS: frozenset[str] = frozenset(
    {
        'teaagent.agentDaily',
        'teaagent.agentPreflight',
        'teaagent.agentPlan',
        'teaagent.agentRun',
        'teaagent.agentStatus',
        'teaagent.agentEvidence',
        'teaagent.agentApprovalPending',
        'teaagent.agentApprovalApprove',
        'teaagent.agentUndo',
        'teaagent.agentResume',
        'teaagent.agentAttach',
    }
)

# Known gaps for SURF-011 capability explain (not yet mirrored in IDE)
IDE_SURFACE_GAPS: dict[str, str] = {
    'agent_runs_list': 'Use CLI `agent runs list` or TUI `runs`',
    'agent_runs_trace': 'Use CLI `agent runs trace`',
    'dashboard_cockpit': 'No web dashboard surface yet (SURF-003)',
    'gateway_intake': 'No Slack/Telegram intake surface yet (SURF-006)',
}

IDE_COMMAND_CLI_EQUIVALENTS: dict[str, str] = {
    'teaagent.agentRun': 'teaagent agent run <provider> <task>',
    'teaagent.agentDaily': 'teaagent agent daily [provider] [task]',
    'teaagent.agentPlan': 'teaagent agent plan <provider> <task>',
    'teaagent.agentPreflight': 'teaagent agent preflight <provider> <task>',
    'teaagent.agentStatus': 'teaagent agent status <run_id>',
    'teaagent.agentEvidence': 'teaagent agent status <run_id> --evidence --human',
    'teaagent.agentResume': 'teaagent agent resume <run_id>',
    'teaagent.agentAttach': 'teaagent agent attach <run_id> --follow',
    'teaagent.agentUndo': 'teaagent agent undo [--last | <run_id>]',
    'teaagent.agentApprovalPending': 'teaagent approval pending --human',
    'teaagent.agentApprovalApprove': 'teaagent approval approve --selector N --resume',
    'teaagent.doctor': 'teaagent doctor all',
    'teaagent.startMcpServer': 'teaagent mcp serve --http',
    'teaagent.openTUI': 'teaagent tui',
}

CLI_SURFACE_COMMANDS: list[str] = [
    'agent daily',
    'agent preflight',
    'agent plan',
    'agent run',
    'agent status',
    'agent status <run_id> --evidence',
    'agent resume',
    'agent attach',
    'agent undo',
    'approval pending',
    'approval approve',
    'surfaces explain',
]

TUI_SURFACE_COMMANDS: list[str] = [
    'daily',
    'preflight <task>',
    'plan <task>',
    'status <run_id>',
    'resume <run_id>',
    'undo',
    'runs',
    'approvals',
    'approve',
    'receipt',
    'background',
]

TUI_SURFACE_GAPS: dict[str, str] = {
    'agent_attach_follow': 'Use CLI `agent attach <run_id> --follow` or IDE attach',
    'approval_selector': 'Use CLI `approval approve --selector N` for numbered pending list',
}

DASHBOARD_SURFACE_GAPS: dict[str, str] = {
    'all_commands': 'No web dashboard surface yet (SURF-003)',
}


def build_surface_explain() -> dict[str, Any]:
    """Build the SURF-011 capability explain payload."""
    ide_supported = [
        {
            'command_id': command_id,
            'cli_equivalent': IDE_COMMAND_CLI_EQUIVALENTS.get(command_id, 'unknown'),
        }
        for command_id in sorted(IDE_COMMAND_CLI_PARITY)
    ]
    return {
        'schema_version': SURFACE_EXPLAIN_SCHEMA_VERSION,
        'surfaces': {
            'cli': {
                'supported': CLI_SURFACE_COMMANDS,
                'gaps': {},
            },
            'tui': {
                'supported': TUI_SURFACE_COMMANDS,
                'gaps': TUI_SURFACE_GAPS,
            },
            'ide': {
                'supported': ide_supported,
                'gaps': IDE_SURFACE_GAPS,
                'surf002_required': sorted(SURF002_REQUIRED_COMMANDS),
            },
            'dashboard': {
                'supported': [],
                'gaps': DASHBOARD_SURFACE_GAPS,
            },
        },
    }


def format_surface_explain_human(payload: dict[str, Any]) -> str:
    """Render capability explain output for terminal users."""
    lines = ['TeaAgent surface capabilities', '']
    for surface, info in payload.get('surfaces', {}).items():
        lines.append(f'## {surface}')
        supported = info.get('supported', [])
        if supported:
            if surface == 'ide':
                for entry in supported:
                    if isinstance(entry, dict):
                        lines.append(
                            f'  - {entry.get("command_id")}: {entry.get("cli_equivalent")}'
                        )
            else:
                for command in supported:
                    lines.append(f'  - {command}')
        else:
            lines.append('  - (none yet)')
        gaps = info.get('gaps') or {}
        if gaps:
            lines.append('  gaps:')
            for gap_id, note in gaps.items():
                lines.append(f'    - {gap_id}: {note}')
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'
