"""SURF-002 / SURF-011: multi-surface command parity registry.

VS Code commands must invoke the same CLI argv fragments documented here.
"""

from __future__ import annotations

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
