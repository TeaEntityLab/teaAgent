from __future__ import annotations

# test-type: contract
import io
import json
import tempfile
from pathlib import Path

from teaagent import handle_mcp_request, serve_mcp_stdio
from teaagent.workspace_tools import build_workspace_tool_registry
from test_support import mcp_test_governance


def test_initialize_returns_protocol_and_capabilities() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = build_workspace_tool_registry(tmp)

        response = handle_mcp_request(
            registry,
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'},
            governance=mcp_test_governance(tmp),
        )

        assert response['id'] == 1
        assert 'protocolVersion' in response['result']
        assert response['result']['serverInfo']['name'] == 'teaagent'


def test_tools_list_returns_workspace_tools() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = build_workspace_tool_registry(tmp)

        response = handle_mcp_request(
            registry,
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
            governance=mcp_test_governance(tmp),
        )

        tools = response['result']['tools']
        names = {tool['name'] for tool in tools}
        assert 'workspace_read_file' in names
        assert 'inputSchema' in tools[0]


def test_tools_call_executes_read_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / 'hello.txt').write_text('hi', encoding='utf-8')
        registry = build_workspace_tool_registry(tmp)

        response = handle_mcp_request(
            registry,
            {
                'jsonrpc': '2.0',
                'id': 3,
                'method': 'tools/call',
                'params': {
                    'name': 'workspace_read_file',
                    'arguments': {'path': 'hello.txt'},
                },
            },
            governance=mcp_test_governance(tmp),
        )

        payload = response['result']
        assert not payload['isError']
        text = json.loads(payload['content'][0]['text'])
        assert text['content'] == 'hi'


def test_tools_call_returns_is_error_for_validation_failure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = build_workspace_tool_registry(tmp)

        response = handle_mcp_request(
            registry,
            {
                'jsonrpc': '2.0',
                'id': 4,
                'method': 'tools/call',
                'params': {'name': 'workspace_read_file', 'arguments': {}},
            },
            governance=mcp_test_governance(tmp),
        )

        assert response['result']['isError']


def test_unknown_method_returns_method_not_found() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = build_workspace_tool_registry(tmp)

        response = handle_mcp_request(
            registry,
            {'jsonrpc': '2.0', 'id': 5, 'method': 'ping'},
            governance=mcp_test_governance(tmp),
        )

        assert response['error']['code'] == -32601


def test_serve_mcp_stdio_round_trip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / 'hello.txt').write_text('hi', encoding='utf-8')
        registry = build_workspace_tool_registry(tmp)
        stdin = io.StringIO(
            '\n'.join(
                [
                    json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}),
                    json.dumps(
                        {
                            'jsonrpc': '2.0',
                            'id': 2,
                            'method': 'tools/call',
                            'params': {
                                'name': 'workspace_read_file',
                                'arguments': {'path': 'hello.txt'},
                            },
                        }
                    ),
                    '',
                ]
            )
        )
        stdout = io.StringIO()

        exit_code = serve_mcp_stdio(
            registry,
            governance=mcp_test_governance(tmp),
            stdin=stdin,
            stdout=stdout,
        )

        lines = [line for line in stdout.getvalue().splitlines() if line]
        assert exit_code == 0
        assert len(lines) == 2
        init_response = json.loads(lines[0])
        call_response = json.loads(lines[1])
        assert init_response['id'] == 1
        assert not call_response['result']['isError']


def _write_call(request_id: int, path: str) -> dict:
    return {
        'jsonrpc': '2.0',
        'id': request_id,
        'method': 'tools/call',
        'params': {
            'name': 'workspace_write_file',
            'arguments': {'path': path, 'content': 'y'},
        },
    }


def _events(governance) -> list[dict]:
    return [
        json.loads(line)
        for line in Path(governance.audit.path).read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]


def test_destructive_call_without_approval_is_denied_and_audited(tmp_path) -> None:
    """AGENTS.md Tool Governance: prompt/read-only never run an unapproved write."""
    registry = build_workspace_tool_registry(str(tmp_path))
    for mode in ('prompt', 'read-only'):
        governance = mcp_test_governance(tmp_path, mode)

        response = handle_mcp_request(
            registry, _write_call(1, 'blocked.txt'), governance=governance
        )

        assert response['error']['code'] == -32001
        assert not (tmp_path / 'blocked.txt').exists()
        blocked = [
            e for e in _events(governance) if e['event_type'] == 'tool_call_blocked'
        ]
        assert [e['payload']['tool_name'] for e in blocked] == ['workspace_write_file']
        assert blocked[0]['payload']['arguments']['content'] == '[redacted]'


def test_preset_grant_allows_only_matching_destructive_call(tmp_path) -> None:
    from teaagent.ergonomics.approval_store import ApprovalPresetStore

    ApprovalPresetStore(tmp_path).grant(
        'workspace_write_file', path_globs=['ok/**'], scope='session'
    )
    registry = build_workspace_tool_registry(str(tmp_path))
    governance = mcp_test_governance(tmp_path)
    (tmp_path / 'ok').mkdir()

    allowed = handle_mcp_request(
        registry, _write_call(1, 'ok/a.txt'), governance=governance
    )
    denied = handle_mcp_request(
        registry, _write_call(2, 'other.txt'), governance=governance
    )

    assert allowed['result']['isError'] is False
    assert (tmp_path / 'ok' / 'a.txt').read_text(encoding='utf-8') == 'y'
    assert denied['error']['code'] == -32001
    assert not (tmp_path / 'other.txt').exists()


def test_allow_mode_executes_and_records_full_call_lifecycle(tmp_path) -> None:
    from teaagent.audit_chain import verify_audit_chain

    registry = build_workspace_tool_registry(str(tmp_path))
    governance = mcp_test_governance(tmp_path, 'allow')

    response = handle_mcp_request(
        registry, _write_call(1, 'done.txt'), governance=governance
    )
    governance.close()

    assert response['result']['isError'] is False
    assert (tmp_path / 'done.txt').read_text(encoding='utf-8') == 'y'
    assert [e['event_type'] for e in _events(governance)] == [
        'run_started',
        'tool_call_requested',
        'tool_call_started',
        'tool_call_completed',
        'run_completed',
    ]
    assert verify_audit_chain(Path(governance.audit.path)).valid


def test_mcp_serve_refuses_plan_dependent_workspace_write_mode(
    tmp_path, capsys
) -> None:
    """workspace-write relies on a bound plan; MCP has none, so fail closed."""
    from teaagent.cli import main

    rc = main(
        [
            'mcp',
            'serve',
            '--root',
            str(tmp_path),
            '--permission-mode',
            'workspace-write',
        ]
    )

    assert rc == 2
    assert 'workspace-write' in capsys.readouterr().err
    assert not (tmp_path / '.teaagent' / 'runs').exists()
