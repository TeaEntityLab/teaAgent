"""SURF-002: VS Code commands invoke the same CLI argv as the daily workflow."""

from __future__ import annotations

import json
from pathlib import Path

# command id -> substrings that must appear in extension.ts near that registration
IDE_COMMAND_CLI_PARITY: dict[str, list[str]] = {
    'teaagent.agentRun': ["'agent', 'run'"],
    'teaagent.agentDaily': ["'agent', 'daily'"],
    'teaagent.agentStatus': ["'agent', 'status'"],
    'teaagent.agentResume': ["'agent', 'resume'"],
    'teaagent.agentAttach': ["'agent', 'attach'"],
    'teaagent.agentPreflight': ["'agent', 'preflight'"],
    'teaagent.doctor': ["'doctor', 'all'"],
    'teaagent.startMcpServer': ["'mcp', 'serve', '--http'"],
    'teaagent.openTUI': ["+ ' tui'"],
}


def test_vscode_manifest_declares_daily_workflow_commands() -> None:
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads(
        (root / 'vscode' / 'package.json').read_text(encoding='utf-8')
    )
    command_ids = {
        cmd.get('command')
        for cmd in manifest.get('contributes', {}).get('commands', [])
        if isinstance(cmd, dict)
    }
    for command_id in IDE_COMMAND_CLI_PARITY:
        assert command_id in command_ids, f'missing manifest command {command_id}'


def _command_registration_block(
    source: str, command_id: str, *, window_lines: int = 40
) -> str:
    lines = source.splitlines()
    for idx, line in enumerate(lines):
        if f"registerCommand('{command_id}'" in line:
            return '\n'.join(lines[idx : idx + window_lines])
    raise AssertionError(f'missing registerCommand for {command_id}')


def test_vscode_extension_wires_commands_to_cli_argv() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / 'vscode' / 'src' / 'extension.ts').read_text(encoding='utf-8')

    for command_id, argv_fragments in IDE_COMMAND_CLI_PARITY.items():
        block = _command_registration_block(source, command_id)
        for fragment in argv_fragments:
            assert fragment in block, f'{command_id} missing CLI fragment {fragment!r}'
