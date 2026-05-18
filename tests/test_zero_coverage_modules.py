"""Tests for acp_adapter, plugin_system, and plan_mode modules."""

from __future__ import annotations

import json
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

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


class TestACPRequest(unittest.TestCase):
    def test_default_values(self) -> None:
        req = ACPRequest()
        self.assertEqual(req.jsonrpc, '2.0')
        self.assertIsNone(req.id)
        self.assertEqual(req.method, '')
        self.assertEqual(req.params, {})

    def test_custom_values(self) -> None:
        req = ACPRequest(id='abc', method='initialize', params={'foo': 'bar'})
        self.assertEqual(req.id, 'abc')
        self.assertEqual(req.method, 'initialize')
        self.assertEqual(req.params, {'foo': 'bar'})


class TestACPResponse(unittest.TestCase):
    def test_success_response(self) -> None:
        resp = ACPResponse(id='1', result={'ok': True})
        self.assertEqual(resp.jsonrpc, '2.0')
        self.assertEqual(resp.id, '1')
        self.assertIsNone(resp.error)

    def test_error_response(self) -> None:
        resp = ACPResponse(id='1', error={'code': -32601, 'message': 'not found'})
        self.assertIsNone(resp.result)
        self.assertEqual(resp.error['code'], -32601)


class TestACPToolCall(unittest.TestCase):
    def test_defaults(self) -> None:
        call = ACPToolCall(tool_name='read_file', arguments={'path': 'foo.py'})
        self.assertEqual(call.tool_name, 'read_file')
        self.assertEqual(call.arguments, {'path': 'foo.py'})
        self.assertTrue(call.call_id)

    def test_custom_id(self) -> None:
        call = ACPToolCall(tool_name='x', arguments={}, call_id='custom-id')
        self.assertEqual(call.call_id, 'custom-id')


class TestACPToolResult(unittest.TestCase):
    def test_success(self) -> None:
        result = ACPToolResult(call_id='1', result='done')
        self.assertIsNone(result.error)

    def test_error(self) -> None:
        result = ACPToolResult(call_id='1', result=None, error='failed')
        self.assertEqual(result.error, 'failed')


class _FakeRegistry:
    def mcp_metadata(self):
        return {
            'tools': [
                {'name': 'read_file', 'description': 'Read a file'},
                {'name': 'write_file', 'description': 'Write a file'},
            ]
        }

    def get(self, name):
        tools = {
            'read_file': MagicMock(handler=lambda args: {'content': 'hello'}),
            'write_file': MagicMock(handler=lambda args: {'written': True}),
        }
        return tools.get(name)


class _FakeRunner:
    pass


class TestACPServer(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = _FakeRegistry()
        self.runner = _FakeRunner()
        self.server = ACPServer(self.registry, self.runner)

    def test_initialize(self) -> None:
        result = self.server.initialize({'clientVersion': '1.0'})
        self.assertEqual(result['serverVersion'], ACP_VERSION)
        self.assertTrue(result['capabilities']['tools'])
        self.assertTrue(self.server._initialized)

    def test_initialize_default_version(self) -> None:
        result = self.server.initialize({})
        self.assertEqual(result['serverVersion'], ACP_VERSION)

    def test_list_tools_not_initialized(self) -> None:
        with self.assertRaises(ACPError):
            self.server.list_tools()

    def test_list_tools(self) -> None:
        self.server.initialize({})
        tools = self.server.list_tools()
        self.assertEqual(len(tools), 2)
        self.assertEqual(tools[0]['name'], 'read_file')

    def test_call_tool_not_initialized(self) -> None:
        with self.assertRaises(ACPError):
            self.server.call_tool({'name': 'read_file'})

    def test_call_tool_missing_name(self) -> None:
        self.server.initialize({})
        with self.assertRaises(ACPError) as ctx:
            self.server.call_tool({})
        self.assertIn('Tool name is required', str(ctx.exception))

    def test_call_tool_not_found(self) -> None:
        self.server.initialize({})
        with self.assertRaises(ACPError) as ctx:
            self.server.call_tool({'name': 'nonexistent'})
        self.assertIn('Tool not found', str(ctx.exception))

    def test_call_tool_success(self) -> None:
        self.server.initialize({})
        result = self.server.call_tool({'name': 'read_file', 'arguments': {}})
        self.assertFalse(result.get('isError'))
        self.assertIn('content', result)

    def test_call_tool_handler_error(self) -> None:
        self.server.initialize({})
        bad_tool = MagicMock()
        bad_tool.handler.side_effect = RuntimeError('boom')
        self.registry.get = lambda name: bad_tool if name == 'bad' else None
        result = self.server.call_tool({'name': 'bad', 'arguments': {}})
        self.assertTrue(result['isError'])

    def test_handle_request_initialize(self) -> None:
        req = ACPRequest(id='1', method='initialize', params={})
        resp = self.server.handle_request(req)
        self.assertIsNone(resp.error)
        self.assertEqual(resp.result['serverVersion'], ACP_VERSION)

    def test_handle_request_tools_list(self) -> None:
        self.server.initialize({})
        req = ACPRequest(id='2', method='tools/list')
        resp = self.server.handle_request(req)
        self.assertIsNone(resp.error)
        self.assertEqual(len(resp.result), 2)

    def test_handle_request_tools_call(self) -> None:
        self.server.initialize({})
        req = ACPRequest(id='3', method='tools/call', params={'name': 'read_file'})
        resp = self.server.handle_request(req)
        self.assertIsNone(resp.error)

    def test_handle_request_shutdown(self) -> None:
        self.server.initialize({})
        req = ACPRequest(id='4', method='shutdown')
        resp = self.server.handle_request(req)
        self.assertIsNone(resp.error)
        self.assertIsNone(resp.result)
        self.assertFalse(self.server._initialized)

    def test_handle_request_unknown_method(self) -> None:
        req = ACPRequest(id='5', method='unknown/method')
        resp = self.server.handle_request(req)
        self.assertIsNotNone(resp.error)
        self.assertEqual(resp.error['code'], -32601)

    def test_handle_request_internal_error(self) -> None:
        self.server.initialize({})
        with patch.object(self.server, 'list_tools', side_effect=RuntimeError('crash')):
            req = ACPRequest(id='6', method='tools/list')
            resp = self.server.handle_request(req)
            self.assertEqual(resp.error['code'], -32603)


class TestACPClient(unittest.TestCase):
    def test_send_request(self) -> None:
        fake_stdin = StringIO('{"jsonrpc":"2.0","id":"1","result":{"ok":true}}\n')
        fake_stdout = StringIO()
        fake_proc = MagicMock()
        fake_proc.stdin = fake_stdout
        fake_proc.stdout = fake_stdin

        client = ACPClient(fake_proc)
        result = client.send_request('initialize', {'version': '1.0'})
        self.assertEqual(result, {'ok': True})
        output = fake_stdout.getvalue()
        self.assertIn('initialize', output)


class TestCreateACPServer(unittest.TestCase):
    def test_factory(self) -> None:
        server = create_acp_server(_FakeRegistry(), _FakeRunner())
        self.assertIsInstance(server, ACPServer)


class TestRunACPServer(unittest.TestCase):
    def test_handles_valid_json(self) -> None:
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
        self.assertIn('result', output)

    def test_ignores_invalid_json(self) -> None:
        fake_stdin = StringIO('not json\n')
        fake_stdout = StringIO()

        with (
            patch.object(sys, 'stdin', fake_stdin),
            patch.object(sys, 'stdout', fake_stdout),
        ):
            run_acp_server(_FakeRegistry(), _FakeRunner())

        self.assertEqual(fake_stdout.getvalue(), '')

    def test_ignores_exception_lines(self) -> None:
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
        self.assertIn('error', output)


class TestACPIntegrationConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = ACPIntegrationConfig()
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.host, '127.0.0.1')
        self.assertEqual(cfg.port, 7331)
        self.assertTrue(cfg.auto_start)
        self.assertFalse(cfg.log_requests)

    def test_custom(self) -> None:
        cfg = ACPIntegrationConfig(enabled=True, port=9999)
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.port, 9999)


class TestCreateACPToolDefinitions(unittest.TestCase):
    def test_returns_dict(self) -> None:
        defs = create_acp_tool_definitions()
        self.assertIn('acp_status', defs)
        self.assertIn('handler', defs['acp_status'])

    def test_handler_returns_status(self) -> None:
        defs = create_acp_tool_definitions()
        result = defs['acp_status']['handler']({})
        self.assertEqual(result['status'], 'available')
        self.assertEqual(result['protocol'], ACP_VERSION)


# ---------------------------------------------------------------------------
# Plugin System Tests
# ---------------------------------------------------------------------------


class TestPluginType(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(PluginType.COMMAND.value, 'command')
        self.assertEqual(PluginType.AGENT.value, 'agent')
        self.assertEqual(PluginType.HOOK.value, 'hook')
        self.assertEqual(PluginType.MCP_SERVER.value, 'mcp_server')


class TestPluginManifest(unittest.TestCase):
    def test_defaults(self) -> None:
        m = PluginManifest(
            name='test',
            version='1.0',
            plugin_type=PluginType.COMMAND,
            description='desc',
        )
        self.assertEqual(m.author, 'unknown')
        self.assertEqual(m.license, 'MIT')
        self.assertIsNone(m.entry_point)
        self.assertEqual(m.dependencies, ())

    def test_full(self) -> None:
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
        self.assertEqual(m.author, 'me')
        self.assertEqual(m.entry_point, 'main.py')
        self.assertEqual(m.dependencies, ('dep1', 'dep2'))


class TestPlugin(unittest.TestCase):
    def test_plugin_dataclass(self) -> None:
        m = PluginManifest(
            name='p', version='1.0', plugin_type=PluginType.COMMAND, description='d'
        )
        p = Plugin(manifest=m, path=Path('/tmp/test'))
        self.assertEqual(p.manifest.name, 'p')
        self.assertIsNone(p.module)


class TestCommandPlugin(unittest.TestCase):
    def test_with_aliases(self) -> None:
        cmd = CommandPlugin(
            name='hello',
            description='greet',
            handler=lambda x: x,
            aliases=('hi', 'hey'),
        )
        self.assertEqual(cmd.aliases, ('hi', 'hey'))


class TestAgentPlugin(unittest.TestCase):
    def test_defaults(self) -> None:
        agent = AgentPlugin(name='coder', description='codes', system_prompt='code!')
        self.assertIsNone(agent.model)
        self.assertEqual(agent.tools, ())


class TestPluginRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = PluginRegistry()

    def test_register_and_get_command(self) -> None:
        cmd = CommandPlugin(name='hello', description='greet', handler=lambda x: x)
        self.registry.register_command(cmd)
        self.assertEqual(self.registry.get_command('hello'), cmd)

    def test_command_aliases(self) -> None:
        cmd = CommandPlugin(
            name='hello', description='greet', handler=lambda x: x, aliases=('hi',)
        )
        self.registry.register_command(cmd)
        self.assertEqual(self.registry.get_command('hi'), cmd)

    def test_register_and_get_agent(self) -> None:
        agent = AgentPlugin(
            name='reviewer', description='reviews', system_prompt='review!'
        )
        self.registry.register_agent(agent)
        self.assertEqual(self.registry.get_agent('reviewer'), agent)

    def test_list_commands(self) -> None:
        cmd1 = CommandPlugin(name='a', description='a', handler=lambda x: x)
        cmd2 = CommandPlugin(name='b', description='b', handler=lambda x: x)
        self.registry.register_command(cmd1)
        self.registry.register_command(cmd2)
        commands = self.registry.list_commands()
        self.assertEqual(len(commands), 2)

    def test_list_agents(self) -> None:
        agent = AgentPlugin(name='x', description='x', system_prompt='x')
        self.registry.register_agent(agent)
        agents = self.registry.list_agents()
        self.assertEqual(len(agents), 1)

    def test_get_unknown_command(self) -> None:
        self.assertIsNone(self.registry.get_command('nonexistent'))

    def test_get_unknown_agent(self) -> None:
        self.assertIsNone(self.registry.get_agent('nonexistent'))


class TestDiscoverPlugins(unittest.TestCase):
    def test_empty_dir(self) -> None:
        with patch.object(Path, 'is_dir', return_value=False):
            plugins = discover_plugins(Path('/nonexistent'))
            self.assertEqual(plugins, [])

    def test_invalid_manifest_skipped(self, tmp_path=None) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plugin_dir = root / '.teaagent' / 'plugins'
            plugin_dir.mkdir(parents=True)
            bad_plugin = plugin_dir / 'bad'
            bad_plugin.mkdir()
            (bad_plugin / 'plugin.json').write_text('not json')

            plugins = discover_plugins(root)
            self.assertEqual(plugins, [])

    def test_valid_plugin_discovered(self) -> None:
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
            self.assertEqual(len(plugins), 1)
            self.assertEqual(plugins[0].manifest.name, 'good-plugin')

    def test_duplicate_name_skipped(self) -> None:
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
            self.assertEqual(len(plugins), 1)

    def test_non_directory_entries_skipped(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plugin_dir = root / '.teaagent' / 'plugins'
            plugin_dir.mkdir(parents=True)
            (plugin_dir / 'not_a_dir.txt').write_text('hello')

            plugins = discover_plugins(root)
            self.assertEqual(plugins, [])


class TestLoadManifest(unittest.TestCase):
    def test_minimal_manifest(self) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({'name': 'test', 'type': 'command'}, f)
            f.flush()
            manifest = _load_manifest(Path(f.name))
        self.assertEqual(manifest.name, 'test')
        self.assertEqual(manifest.version, '1.0.0')
        self.assertEqual(manifest.plugin_type, PluginType.COMMAND)

    def test_full_manifest(self) -> None:
        import tempfile

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
            json.dump(data, f)
            f.flush()
            manifest = _load_manifest(Path(f.name))
        self.assertEqual(manifest.name, 'full')
        self.assertEqual(manifest.version, '2.0.0')
        self.assertEqual(manifest.author, 'test-author')
        self.assertEqual(manifest.entry_point, 'main.py')
        self.assertEqual(manifest.dependencies, ('dep1',))


class TestRegisterBuiltinPlugins(unittest.TestCase):
    def test_registers_agents(self) -> None:
        registry = PluginRegistry()
        register_builtin_plugins(registry)
        agents = registry.list_agents()
        names = {a.name for a in agents}
        self.assertIn('code-reviewer', names)
        self.assertIn('tester', names)
        self.assertIn('docs-writer', names)

    def test_agent_has_tools(self) -> None:
        registry = PluginRegistry()
        register_builtin_plugins(registry)
        reviewer = registry.get_agent('code-reviewer')
        self.assertIn('workspace_read_file', reviewer.tools)


# ---------------------------------------------------------------------------
# Plan Mode Tests
# ---------------------------------------------------------------------------


class TestPlanModeState(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(PlanModeState.DISABLED.value, 'disabled')
        self.assertEqual(PlanModeState.ENABLED.value, 'enabled')
        self.assertEqual(PlanModeState.CONFIRMING.value, 'confirming')


class TestPlanModeConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = PlanModeConfig()
        self.assertTrue(cfg.allow_file_reads)
        self.assertTrue(cfg.allow_search)
        self.assertTrue(cfg.allow_lsp_navigation)
        self.assertTrue(cfg.allow_web_search)
        self.assertTrue(cfg.block_writes)
        self.assertTrue(cfg.block_shell)
        self.assertTrue(cfg.require_confirmation_before_exit)


class TestPlanMode(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = PlanMode()

    def test_initial_state(self) -> None:
        self.assertEqual(self.plan.state, PlanModeState.DISABLED)
        self.assertFalse(self.plan.is_enabled())
        self.assertIsNone(self.plan.reason)

    def test_enable(self) -> None:
        self.plan.enable('testing')
        self.assertTrue(self.plan.is_enabled())
        self.assertEqual(self.plan.reason, 'testing')

    def test_enable_default_reason(self) -> None:
        self.plan.enable()
        self.assertEqual(self.plan.reason, 'User requested plan mode')

    def test_enable_clears_notes(self) -> None:
        self.plan.enable()
        self.plan.add_note('note1')
        self.plan.enable()
        self.assertEqual(self.plan.exploration_notes, [])

    def test_disable_without_notes(self) -> None:
        self.plan.enable()
        self.plan.disable()
        self.assertEqual(self.plan.state, PlanModeState.DISABLED)

    def test_disable_with_notes_enters_confirming(self) -> None:
        self.plan.enable()
        self.plan.add_note('found something')
        self.plan.disable()
        self.assertEqual(self.plan.state, PlanModeState.CONFIRMING)

    def test_confirm_exit(self) -> None:
        self.plan.enable()
        self.plan.add_note('note')
        self.plan.disable()
        self.plan.confirm_exit()
        self.assertEqual(self.plan.state, PlanModeState.DISABLED)
        self.assertIsNone(self.plan.reason)

    def test_cancel_exit(self) -> None:
        self.plan.enable()
        self.plan.add_note('note')
        self.plan.disable()
        self.plan.cancel_exit()
        self.assertEqual(self.plan.state, PlanModeState.ENABLED)

    def test_force_disable(self) -> None:
        self.plan.enable('test')
        self.plan._force_disable()
        self.assertEqual(self.plan.state, PlanModeState.DISABLED)
        self.assertIsNone(self.plan.reason)


class TestPlanModeToolBlocking(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = PlanMode()

    def test_allows_tools_when_disabled(self) -> None:
        allowed, reason = self.plan.can_execute_tool('shell')
        self.assertTrue(allowed)
        self.assertIsNone(reason)

    def test_blocks_write_when_enabled(self) -> None:
        self.plan.enable()
        allowed, reason = self.plan.can_execute_tool('workspace_write_file')
        self.assertFalse(allowed)
        self.assertIn('blocks file writes', reason)

    def test_blocks_shell_when_enabled(self) -> None:
        self.plan.enable()
        allowed, reason = self.plan.can_execute_tool('shell')
        self.assertFalse(allowed)
        self.assertIn('blocks shell', reason)

    def test_allows_read_when_enabled(self) -> None:
        self.plan.enable()
        allowed, reason = self.plan.can_execute_tool('workspace_read_file')
        self.assertTrue(allowed)
        self.assertIsNone(reason)

    def test_allows_search_when_enabled(self) -> None:
        self.plan.enable()
        allowed, reason = self.plan.can_execute_tool('grep')
        self.assertTrue(allowed)
        self.assertIsNone(reason)

    def test_blocks_terminal_when_enabled(self) -> None:
        self.plan.enable()
        allowed, reason = self.plan.can_execute_tool('terminal')
        self.assertFalse(allowed)

    def test_blocks_process_when_enabled(self) -> None:
        self.plan.enable()
        allowed, reason = self.plan.can_execute_tool('process')
        self.assertFalse(allowed)

    def test_blocks_write_tools(self) -> None:
        self.plan.enable()
        write_tools = [
            'workspace_write_file',
            'workspace_apply_patch',
            'workspace_edit_at_hash',
            'workspace_create_directory',
            'workspace_delete',
        ]
        for tool in write_tools:
            allowed, reason = self.plan.can_execute_tool(tool)
            self.assertFalse(allowed, f'{tool} should be blocked')


class TestPlanModeNotes(unittest.TestCase):
    def test_add_note_when_enabled(self) -> None:
        plan = PlanMode()
        plan.enable()
        plan.add_note('note1')
        plan.add_note('note2')
        self.assertEqual(len(plan.exploration_notes), 2)

    def test_add_note_when_disabled(self) -> None:
        plan = PlanMode()
        plan.add_note('ignored')
        self.assertEqual(len(plan.exploration_notes), 0)

    def test_exploration_summary_empty(self) -> None:
        plan = PlanMode()
        plan.enable()
        self.assertEqual(
            plan.get_exploration_summary(), 'No exploration notes recorded.'
        )

    def test_exploration_summary_with_notes(self) -> None:
        plan = PlanMode()
        plan.enable()
        plan.add_note('first')
        plan.add_note('second')
        summary = plan.get_exploration_summary()
        self.assertIn('- first', summary)
        self.assertIn('- second', summary)


class TestCreatePlanModeTools(unittest.TestCase):
    def test_returns_definitions(self) -> None:
        defs = create_plan_mode_tools()
        self.assertIn('enter_plan_mode', defs)
        self.assertIn('exit_plan_mode', defs)

    def test_enter_plan_mode_handler(self) -> None:
        defs = create_plan_mode_tools()
        result = defs['enter_plan_mode']['handler']({'reason': 'testing'})
        self.assertEqual(result['status'], 'enabled')
        self.assertEqual(result['reason'], 'testing')

    def test_enter_plan_mode_default_reason(self) -> None:
        defs = create_plan_mode_tools()
        result = defs['enter_plan_mode']['handler']({})
        self.assertEqual(result['reason'], 'Exploration mode enabled')

    def test_exit_plan_mode_handler(self) -> None:
        defs = create_plan_mode_tools()
        result = defs['exit_plan_mode']['handler']({'confirm': True})
        self.assertEqual(result['status'], 'exited')
        self.assertTrue(result['confirm'])

    def test_tool_descriptions(self) -> None:
        defs = create_plan_mode_tools()
        self.assertIn('read-only', defs['enter_plan_mode']['description'])
        self.assertIn('Exit', defs['exit_plan_mode']['description'])
