"""Tests for acp_adapter, plugin_system, and plan_mode modules."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from teaagent.acp_adapter import (
    ACP_VERSION,
    ACPClient,
    ACPError,
    ACPIntegrationConfig,
    ACPRequest,
    ACPResponse,
    ACPServer,
    ACPToolCall,
    ACPToolResult,
    create_acp_server,
    create_acp_tool_definitions,
    run_acp_server,
)
from teaagent.plan_mode import (
    PlanMode,
    PlanModeConfig,
    PlanModeState,
    create_plan_mode_tools,
)
from teaagent.plugin_system import (
    AgentPlugin,
    CommandPlugin,
    Plugin,
    PluginManifest,
    PluginRegistry,
    PluginType,
    _load_manifest,
    discover_plugins,
    register_builtin_plugins,
)

# ---------------------------------------------------------------------------
# ACP Adapter Tests
# ---------------------------------------------------------------------------


def test_acp_request_default_values() -> None:
    req = ACPRequest()
    assert req.jsonrpc == '2.0'
    assert req.id is None
    assert req.method == ''
    assert req.params == {}


def test_acp_request_custom_values() -> None:
    req = ACPRequest(id='abc', method='initialize', params={'foo': 'bar'})
    assert req.id == 'abc'
    assert req.method == 'initialize'
    assert req.params == {'foo': 'bar'}


def test_acp_response_success() -> None:
    resp = ACPResponse(id='1', result={'ok': True})
    assert resp.jsonrpc == '2.0'
    assert resp.id == '1'
    assert resp.error is None


def test_acp_response_error() -> None:
    resp = ACPResponse(id='1', error={'code': -32601, 'message': 'not found'})
    assert resp.result is None
    assert resp.error['code'] == -32601


def test_acp_tool_call_defaults() -> None:
    call = ACPToolCall(tool_name='read_file', arguments={'path': 'foo.py'})
    assert call.tool_name == 'read_file'
    assert call.arguments == {'path': 'foo.py'}
    assert call.call_id


def test_acp_tool_call_custom_id() -> None:
    call = ACPToolCall(tool_name='x', arguments={}, call_id='custom-id')
    assert call.call_id == 'custom-id'


def test_acp_tool_result_success() -> None:
    result = ACPToolResult(call_id='1', result='done')
    assert result.error is None


def test_acp_tool_result_error() -> None:
    result = ACPToolResult(call_id='1', result=None, error='failed')
    assert result.error == 'failed'


class _FakeRegistry:
    def mcp_metadata(self):
        return [
            {'name': 'read_file', 'description': 'Read a file'},
            {'name': 'write_file', 'description': 'Write a file'},
        ]

    def get(self, name):
        tools = {
            'read_file': MagicMock(handler=lambda args: {'content': 'hello'}),
            'write_file': MagicMock(handler=lambda args: {'written': True}),
        }
        return tools.get(name)


class _FakeRunner:
    pass


@pytest.fixture
def acp_server():
    registry = _FakeRegistry()
    runner = _FakeRunner()
    server = ACPServer(registry, runner)
    return server


def test_acp_server_initialize(acp_server) -> None:
    result = acp_server.initialize({'clientVersion': '1.0'})
    assert result['serverVersion'] == ACP_VERSION
    assert result['capabilities']['tools']
    assert acp_server._initialized


def test_acp_server_initialize_default_version(acp_server) -> None:
    result = acp_server.initialize({})
    assert result['serverVersion'] == ACP_VERSION


def test_acp_server_list_tools_not_initialized(acp_server) -> None:
    with pytest.raises(ACPError):
        acp_server.list_tools()


def test_acp_server_list_tools(acp_server) -> None:
    acp_server.initialize({})
    tools = acp_server.list_tools()
    assert len(tools) == 2
    assert tools[0]['name'] == 'read_file'


def test_acp_server_call_tool_not_initialized(acp_server) -> None:
    with pytest.raises(ACPError):
        acp_server.call_tool({'name': 'read_file'})


def test_acp_server_call_tool_missing_name(acp_server) -> None:
    acp_server.initialize({})
    with pytest.raises(ACPError) as exc_info:
        acp_server.call_tool({})
    assert 'Tool name is required' in str(exc_info.value)


def test_acp_server_call_tool_not_found(acp_server) -> None:
    acp_server.initialize({})
    with pytest.raises(ACPError) as exc_info:
        acp_server.call_tool({'name': 'nonexistent'})
    assert 'Tool not found' in str(exc_info.value)


def test_acp_server_call_tool_success(acp_server) -> None:
    acp_server.initialize({})
    result = acp_server.call_tool({'name': 'read_file', 'arguments': {}})
    assert not result.get('isError')
    assert 'content' in result


def test_acp_server_call_tool_handler_error() -> None:
    bad_tool = MagicMock()
    bad_tool.handler.side_effect = RuntimeError('boom')
    registry = _FakeRegistry()
    registry.get = lambda name: bad_tool if name == 'bad' else None
    server = ACPServer(registry, _FakeRunner())
    server.initialize({})
    result = server.call_tool({'name': 'bad', 'arguments': {}})
    assert result['isError']


def test_acp_server_handle_request_initialize(acp_server) -> None:
    req = ACPRequest(id='1', method='initialize', params={})
    resp = acp_server.handle_request(req)
    assert resp.error is None
    assert resp.result['serverVersion'] == ACP_VERSION


def test_acp_server_handle_request_tools_list(acp_server) -> None:
    acp_server.initialize({})
    req = ACPRequest(id='2', method='tools/list')
    resp = acp_server.handle_request(req)
    assert resp.error is None
    assert len(resp.result) == 2


def test_acp_server_handle_request_tools_call(acp_server) -> None:
    acp_server.initialize({})
    req = ACPRequest(id='3', method='tools/call', params={'name': 'read_file'})
    resp = acp_server.handle_request(req)
    assert resp.error is None


def test_acp_server_handle_request_prompt_assemble(acp_server) -> None:
    acp_server.initialize({})
    req = ACPRequest(
        id='3b',
        method='prompt/assemble',
        params={
            'prompt': 'Review',
            'contextBlocks': [
                {'type': 'selection', 'label': 'a.py', 'content': 'code'}
            ],
        },
    )
    resp = acp_server.handle_request(req)
    assert resp.error is None
    assert 'selection' in resp.result['prompt']


def test_acp_server_progress_audit_sink_emits_session_update(acp_server) -> None:
    acp_server.initialize({})
    emitted: list[dict] = []
    acp_server.set_notification_sink(emitted.append, session_id='sess-1')
    sink = acp_server.progress_audit_sink('sess-1')
    from teaagent.types import AuditEvent

    sink(
        AuditEvent(
            event_type='tool_call_started',
            run_id='r1',
            payload={'tool_name': 'read_file', 'call_id': 'c1'},
        )
    )
    assert len(emitted) == 1
    assert emitted[0]['method'] == 'session/update'
    assert emitted[0]['params']['sessionId'] == 'sess-1'


def test_acp_server_handle_request_shutdown(acp_server) -> None:
    acp_server.initialize({})
    req = ACPRequest(id='4', method='shutdown')
    resp = acp_server.handle_request(req)
    assert resp.error is None
    assert resp.result is None
    assert not acp_server._initialized


def test_acp_server_handle_request_unknown_method(acp_server) -> None:
    req = ACPRequest(id='5', method='unknown/method')
    resp = acp_server.handle_request(req)
    assert resp.error is not None
    assert resp.error['code'] == -32601


def test_acp_server_handle_request_internal_error(acp_server) -> None:
    acp_server.initialize({})
    with patch.object(acp_server, 'list_tools', side_effect=RuntimeError('crash')):
        req = ACPRequest(id='6', method='tools/list')
        resp = acp_server.handle_request(req)
        assert resp.error['code'] == -32603


def test_acp_client_send_request() -> None:
    fake_stdin = StringIO('{"jsonrpc":"2.0","id":"1","result":{"ok":true}}\n')
    fake_stdout = StringIO()
    fake_proc = MagicMock()
    fake_proc.stdin = fake_stdout
    fake_proc.stdout = fake_stdin

    client = ACPClient(fake_proc)
    result = client.send_request('initialize', {'version': '1.0'})
    assert result == {'ok': True}
    output = fake_stdout.getvalue()
    assert 'initialize' in output


def test_create_acp_server_factory() -> None:
    server = create_acp_server(_FakeRegistry(), _FakeRunner())
    assert isinstance(server, ACPServer)


def test_run_acp_server_handles_valid_json() -> None:
    fake_stdin = StringIO(
        '{"jsonrpc":"2.0","id":"1","method":"initialize","params":{}}\n'
    )
    fake_stdout = StringIO()

    with (
        patch.object(sys, 'stdin', fake_stdin),
        patch.object(sys, 'stdout', fake_stdout),
    ):
        run_acp_server(_FakeRegistry(), _FakeRunner())

    output = fake_stdout.getvalue()
    assert 'result' in output


def test_run_acp_server_ignores_invalid_json() -> None:
    fake_stdin = StringIO('not json\n')
    fake_stdout = StringIO()

    with (
        patch.object(sys, 'stdin', fake_stdin),
        patch.object(sys, 'stdout', fake_stdout),
    ):
        run_acp_server(_FakeRegistry(), _FakeRunner())

    assert fake_stdout.getvalue() == ''


def test_run_acp_server_ignores_exception_lines() -> None:
    fake_stdin = StringIO(
        '{"jsonrpc":"2.0","id":"1","method":"tools/list","params":{}}\n'
    )
    fake_stdout = StringIO()

    with (
        patch.object(sys, 'stdin', fake_stdin),
        patch.object(sys, 'stdout', fake_stdout),
    ):
        run_acp_server(_FakeRegistry(), _FakeRunner())

    output = fake_stdout.getvalue()
    assert 'error' in output


def test_acp_integration_config_defaults() -> None:
    cfg = ACPIntegrationConfig()
    assert not cfg.enabled
    assert cfg.host == '127.0.0.1'
    assert cfg.port == 7331
    assert cfg.auto_start
    assert not cfg.log_requests


def test_acp_integration_config_custom() -> None:
    cfg = ACPIntegrationConfig(enabled=True, port=9999)
    assert cfg.enabled
    assert cfg.port == 9999


def test_create_acp_tool_definitions_returns_dict() -> None:
    defs = create_acp_tool_definitions()
    assert 'acp_status' in defs
    assert 'handler' in defs['acp_status']


def test_create_acp_tool_definitions_handler_returns_status() -> None:
    defs = create_acp_tool_definitions()
    result = defs['acp_status']['handler']({})
    assert result['status'] == 'available'
    assert result['protocol'] == ACP_VERSION


# ---------------------------------------------------------------------------
# Plugin System Tests
# ---------------------------------------------------------------------------


def test_plugin_type_values() -> None:
    assert PluginType.COMMAND.value == 'command'
    assert PluginType.AGENT.value == 'agent'
    assert PluginType.HOOK.value == 'hook'
    assert PluginType.MCP_SERVER.value == 'mcp_server'


def test_plugin_manifest_defaults() -> None:
    m = PluginManifest(
        name='test',
        version='1.0',
        plugin_type=PluginType.COMMAND,
        description='desc',
    )
    assert m.author == 'unknown'
    assert m.license == 'MIT'
    assert m.entry_point is None
    assert m.dependencies == ()


def test_plugin_manifest_full() -> None:
    m = PluginManifest(
        name='full',
        version='2.0',
        plugin_type=PluginType.AGENT,
        description='full plugin',
        author='me',
        license='Apache',
        entry_point='main.py',
        dependencies=('dep1', 'dep2'),
        config_schema={'type': 'object'},
    )
    assert m.author == 'me'
    assert m.entry_point == 'main.py'
    assert m.dependencies == ('dep1', 'dep2')


def test_plugin_dataclass() -> None:
    m = PluginManifest(
        name='p', version='1.0', plugin_type=PluginType.COMMAND, description='d'
    )
    p = Plugin(manifest=m, path=Path('/tmp/test'))
    assert p.manifest.name == 'p'
    assert p.module is None


def test_command_plugin_with_aliases() -> None:
    cmd = CommandPlugin(
        name='hello',
        description='greet',
        handler=lambda x: x,
        aliases=('hi', 'hey'),
    )
    assert cmd.aliases == ('hi', 'hey')


def test_agent_plugin_defaults() -> None:
    agent = AgentPlugin(name='coder', description='codes', system_prompt='code!')
    assert agent.model is None
    assert agent.tools == ()


@pytest.fixture
def plugin_registry():
    return PluginRegistry()


def test_plugin_registry_register_and_get_command(plugin_registry) -> None:
    cmd = CommandPlugin(name='hello', description='greet', handler=lambda x: x)
    plugin_registry.register_command(cmd)
    assert plugin_registry.get_command('hello') == cmd


def test_plugin_registry_command_aliases(plugin_registry) -> None:
    cmd = CommandPlugin(
        name='hello', description='greet', handler=lambda x: x, aliases=('hi',)
    )
    plugin_registry.register_command(cmd)
    assert plugin_registry.get_command('hi') == cmd


def test_plugin_registry_register_and_get_agent(plugin_registry) -> None:
    agent = AgentPlugin(name='reviewer', description='reviews', system_prompt='review!')
    plugin_registry.register_agent(agent)
    assert plugin_registry.get_agent('reviewer') == agent


def test_plugin_registry_list_commands(plugin_registry) -> None:
    cmd1 = CommandPlugin(name='a', description='a', handler=lambda x: x)
    cmd2 = CommandPlugin(name='b', description='b', handler=lambda x: x)
    plugin_registry.register_command(cmd1)
    plugin_registry.register_command(cmd2)
    commands = plugin_registry.list_commands()
    assert len(commands) == 2


def test_plugin_registry_list_agents(plugin_registry) -> None:
    agent = AgentPlugin(name='x', description='x', system_prompt='x')
    plugin_registry.register_agent(agent)
    agents = plugin_registry.list_agents()
    assert len(agents) == 1


def test_plugin_registry_get_unknown_command(plugin_registry) -> None:
    assert plugin_registry.get_command('nonexistent') is None


def test_plugin_registry_get_unknown_agent(plugin_registry) -> None:
    assert plugin_registry.get_agent('nonexistent') is None


def test_discover_plugins_empty_dir() -> None:
    with patch.object(Path, 'is_dir', return_value=False):
        plugins = discover_plugins(Path('/nonexistent'))
        assert plugins == []


def test_discover_plugins_invalid_manifest_skipped() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        plugin_dir = root / '.teaagent' / 'plugins'
        plugin_dir.mkdir(parents=True)
        bad_plugin = plugin_dir / 'bad'
        bad_plugin.mkdir()
        (bad_plugin / 'plugin.json').write_text('not json')

        plugins = discover_plugins(root)
        assert plugins == []


def test_discover_plugins_valid_plugin_discovered() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        plugin_dir = root / '.teaagent' / 'plugins'
        plugin_dir.mkdir(parents=True)
        good_plugin = plugin_dir / 'good'
        good_plugin.mkdir()
        manifest = {
            'name': 'good-plugin',
            'version': '1.0.0',
            'type': 'command',
            'description': 'A good plugin',
        }
        (good_plugin / 'plugin.json').write_text(json.dumps(manifest))

        plugins = discover_plugins(root)
        assert len(plugins) == 1
        assert plugins[0].manifest.name == 'good-plugin'


def test_discover_plugins_duplicate_name_skipped() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        plugin_dir = root / '.teaagent' / 'plugins'
        plugin_dir.mkdir(parents=True)
        manifest = {
            'name': 'dup-plugin',
            'version': '1.0.0',
            'type': 'agent',
            'description': 'A plugin',
        }
        (plugin_dir / 'a' / 'plugin.json').parent.mkdir(parents=True, exist_ok=True)
        (plugin_dir / 'a' / 'plugin.json').write_text(json.dumps(manifest))
        (plugin_dir / 'b' / 'plugin.json').parent.mkdir(parents=True, exist_ok=True)
        (plugin_dir / 'b' / 'plugin.json').write_text(json.dumps(manifest))

        plugins = discover_plugins(root)
        assert len(plugins) == 1


def test_discover_plugins_non_directory_entries_skipped() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        plugin_dir = root / '.teaagent' / 'plugins'
        plugin_dir.mkdir(parents=True)
        (plugin_dir / 'not_a_dir.txt').write_text('hello')

        plugins = discover_plugins(root)
        assert plugins == []


def test_load_manifest_minimal() -> None:
    import os
    import tempfile

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            tmp_path = f.name
            json.dump({'name': 'test', 'type': 'command'}, f)
            f.flush()
            manifest = _load_manifest(Path(f.name))
        assert manifest.name == 'test'
        assert manifest.version == '1.0.0'
        assert manifest.plugin_type == PluginType.COMMAND
    finally:
        # Verify cleanup
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
            assert not os.path.exists(tmp_path), (
                f'Temporary file {tmp_path} was not cleaned up'
            )


def test_load_manifest_full() -> None:
    import os
    import tempfile

    tmp_path = None
    try:
        data = {
            'name': 'full',
            'version': '2.0.0',
            'type': 'agent',
            'description': 'Full plugin',
            'author': 'test-author',
            'license': 'Apache-2.0',
            'entry_point': 'main.py',
            'dependencies': ['dep1'],
            'config_schema': {'type': 'object'},
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            tmp_path = f.name
            json.dump(data, f)
            f.flush()
            manifest = _load_manifest(Path(f.name))
        assert manifest.name == 'full'
        assert manifest.version == '2.0.0'
        assert manifest.author == 'test-author'
        assert manifest.entry_point == 'main.py'
        assert manifest.dependencies == ('dep1',)
    finally:
        # Verify cleanup
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
            assert not os.path.exists(tmp_path), (
                f'Temporary file {tmp_path} was not cleaned up'
            )


def test_register_builtin_plugins_registers_agents() -> None:
    registry = PluginRegistry()
    register_builtin_plugins(registry)
    agents = registry.list_agents()
    names = {a.name for a in agents}
    assert 'code-reviewer' in names
    assert 'tester' in names
    assert 'docs-writer' in names


def test_register_builtin_plugins_agent_has_tools() -> None:
    registry = PluginRegistry()
    register_builtin_plugins(registry)
    reviewer = registry.get_agent('code-reviewer')
    assert 'workspace_read_file' in reviewer.tools


# ---------------------------------------------------------------------------
# Plan Mode Tests
# ---------------------------------------------------------------------------


def test_plan_mode_state_values() -> None:
    assert PlanModeState.DISABLED.value == 'disabled'
    assert PlanModeState.ENABLED.value == 'enabled'
    assert PlanModeState.CONFIRMING.value == 'confirming'


def test_plan_mode_config_defaults() -> None:
    cfg = PlanModeConfig()
    assert cfg.allow_file_reads
    assert cfg.allow_search
    assert cfg.allow_lsp_navigation
    assert cfg.allow_web_search
    assert cfg.block_writes
    assert cfg.block_shell
    assert cfg.require_confirmation_before_exit


@pytest.fixture
def plan_mode():
    return PlanMode()


def test_plan_mode_initial_state(plan_mode) -> None:
    assert plan_mode.state == PlanModeState.DISABLED
    assert not plan_mode.is_enabled()
    assert plan_mode.reason is None


def test_plan_mode_enable(plan_mode) -> None:
    plan_mode.enable('testing')
    assert plan_mode.is_enabled()
    assert plan_mode.reason == 'testing'


def test_plan_mode_enable_default_reason(plan_mode) -> None:
    plan_mode.enable()
    assert plan_mode.reason == 'User requested plan mode'


def test_plan_mode_enable_clears_notes(plan_mode) -> None:
    plan_mode.enable()
    plan_mode.add_note('note1')
    plan_mode.enable()
    assert plan_mode.exploration_notes == []


def test_plan_mode_disable_without_notes(plan_mode) -> None:
    plan_mode.enable()
    plan_mode.disable()
    assert plan_mode.state == PlanModeState.DISABLED


def test_plan_mode_disable_with_notes_enters_confirming(plan_mode) -> None:
    plan_mode.enable()
    plan_mode.add_note('found something')
    plan_mode.disable()
    assert plan_mode.state == PlanModeState.CONFIRMING


def test_plan_mode_confirm_exit(plan_mode) -> None:
    plan_mode.enable()
    plan_mode.add_note('note')
    plan_mode.disable()
    plan_mode.confirm_exit()
    assert plan_mode.state == PlanModeState.DISABLED
    assert plan_mode.reason is None


def test_plan_mode_cancel_exit(plan_mode) -> None:
    plan_mode.enable()
    plan_mode.add_note('note')
    plan_mode.disable()
    plan_mode.cancel_exit()
    assert plan_mode.state == PlanModeState.ENABLED


def test_plan_mode_force_disable(plan_mode) -> None:
    plan_mode.enable('test')
    plan_mode._force_disable()
    assert plan_mode.state == PlanModeState.DISABLED
    assert plan_mode.reason is None


@pytest.fixture
def plan_mode_blocking():
    return PlanMode()


def test_plan_mode_allows_tools_when_disabled(plan_mode_blocking) -> None:
    allowed, reason = plan_mode_blocking.can_execute_tool('shell')
    assert allowed
    assert reason is None


def test_plan_mode_blocks_write_when_enabled(plan_mode_blocking) -> None:
    plan_mode_blocking.enable()
    allowed, reason = plan_mode_blocking.can_execute_tool('workspace_write_file')
    assert not allowed
    assert 'blocks file writes' in reason


def test_plan_mode_blocks_shell_when_enabled(plan_mode_blocking) -> None:
    plan_mode_blocking.enable()
    allowed, reason = plan_mode_blocking.can_execute_tool('shell')
    assert not allowed
    assert 'blocks shell' in reason


def test_plan_mode_allows_read_when_enabled(plan_mode_blocking) -> None:
    plan_mode_blocking.enable()
    allowed, reason = plan_mode_blocking.can_execute_tool('workspace_read_file')
    assert allowed
    assert reason is None


def test_plan_mode_allows_search_when_enabled(plan_mode_blocking) -> None:
    plan_mode_blocking.enable()
    allowed, reason = plan_mode_blocking.can_execute_tool('grep')
    assert allowed
    assert reason is None


def test_plan_mode_blocks_terminal_when_enabled(plan_mode_blocking) -> None:
    plan_mode_blocking.enable()
    allowed, reason = plan_mode_blocking.can_execute_tool('terminal')
    assert not allowed


def test_plan_mode_blocks_process_when_enabled(plan_mode_blocking) -> None:
    plan_mode_blocking.enable()
    allowed, reason = plan_mode_blocking.can_execute_tool('process')
    assert not allowed


def test_plan_mode_blocks_write_tools(plan_mode_blocking) -> None:
    plan_mode_blocking.enable()
    write_tools = [
        'workspace_write_file',
        'workspace_apply_patch',
        'workspace_edit_at_hash',
        'workspace_create_directory',
        'workspace_delete',
    ]
    for tool in write_tools:
        allowed, reason = plan_mode_blocking.can_execute_tool(tool)
        assert not allowed, f'{tool} should be blocked'


def test_plan_mode_add_note_when_enabled() -> None:
    plan = PlanMode()
    plan.enable()
    plan.add_note('note1')
    plan.add_note('note2')
    assert len(plan.exploration_notes) == 2


def test_plan_mode_add_note_when_disabled() -> None:
    plan = PlanMode()
    plan.add_note('ignored')
    assert len(plan.exploration_notes) == 0


def test_plan_mode_exploration_summary_empty() -> None:
    plan = PlanMode()
    plan.enable()
    assert plan.get_exploration_summary() == 'No exploration notes recorded.'


def test_plan_mode_exploration_summary_with_notes() -> None:
    plan = PlanMode()
    plan.enable()
    plan.add_note('first')
    plan.add_note('second')
    summary = plan.get_exploration_summary()
    assert '- first' in summary
    assert '- second' in summary


def test_create_plan_mode_tools_returns_definitions() -> None:
    defs = create_plan_mode_tools()
    assert 'enter_plan_mode' in defs
    assert 'exit_plan_mode' in defs


def test_create_plan_mode_tools_enter_plan_mode_handler() -> None:
    defs = create_plan_mode_tools()
    result = defs['enter_plan_mode']['handler']({'reason': 'testing'})
    assert result['status'] == 'enabled'
    assert result['reason'] == 'testing'


def test_create_plan_mode_tools_enter_plan_mode_default_reason() -> None:
    defs = create_plan_mode_tools()
    result = defs['enter_plan_mode']['handler']({})
    assert result['reason'] == 'Exploration mode enabled'


def test_create_plan_mode_tools_exit_plan_mode_handler() -> None:
    defs = create_plan_mode_tools()
    result = defs['exit_plan_mode']['handler']({'confirm': True})
    assert result['status'] == 'exited'
    assert result['confirm']


def test_create_plan_mode_tools_tool_descriptions() -> None:
    defs = create_plan_mode_tools()
    assert 'read-only' in defs['enter_plan_mode']['description']
    assert 'Exit' in defs['exit_plan_mode']['description']
