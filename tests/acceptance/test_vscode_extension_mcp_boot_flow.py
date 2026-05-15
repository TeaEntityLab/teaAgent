"""AC-NEW-17: VSCode extension MCP boot flow.

As an IDE user, I want the VSCode extension to expose a command that starts
TeaAgent MCP server with HTTP transport, so IDE workflows can attach to a
workspace-local MCP endpoint.

Acceptance criteria:
- Extension manifest contributes `teaagent.startMcpServer` command.
- Extension source registers the command and invokes `teaagent mcp serve --http`.
- Extension permission mode config aligns with CLI permission modes.
"""

from __future__ import annotations

import json
from pathlib import Path


def test_vscode_manifest_and_command_wiring_for_mcp_boot() -> None:
    root = Path(__file__).resolve().parents[2]
    package_json = root / 'vscode' / 'package.json'
    extension_ts = root / 'vscode' / 'src' / 'extension.ts'

    manifest = json.loads(package_json.read_text(encoding='utf-8'))
    command_ids = {
        cmd.get('command')
        for cmd in manifest.get('contributes', {}).get('commands', [])
        if isinstance(cmd, dict)
    }
    assert 'teaagent.startMcpServer' in command_ids

    source = extension_ts.read_text(encoding='utf-8')
    assert "registerCommand('teaagent.startMcpServer'" in source
    assert "['mcp', 'serve', '--http'" in source


def test_vscode_permission_mode_enum_matches_cli_modes() -> None:
    root = Path(__file__).resolve().parents[2]
    package_json = root / 'vscode' / 'package.json'
    manifest = json.loads(package_json.read_text(encoding='utf-8'))

    mode_prop = (
        manifest.get('contributes', {})
        .get('configuration', {})
        .get('properties', {})
        .get('teaagent.defaultPermissionMode', {})
    )
    values = set(mode_prop.get('enum', []))
    assert values == {
        'read-only',
        'workspace-write',
        'prompt',
        'allow',
        'danger-full-access',
    }
