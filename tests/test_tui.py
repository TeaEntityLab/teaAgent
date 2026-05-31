from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import PropertyMock, patch

from conftest import FakeAdapter

from teaagent.cli import main
from teaagent.ergonomics._approval_grants import _compute_argument_digest
from teaagent.graphqlite_store import GraphQLiteRuntimeError
from teaagent.tui import TeaAgentTUI


class CapturingAdapterFactory:
    def __init__(self, adapter):
        self.adapter = adapter
        self.calls = []

    def __call__(self, provider, model):
        self.calls.append((provider, model))
        return self.adapter


class TUITests(unittest.TestCase):
    def test_tui_handles_doctor_smoke_query_and_exit(self) -> None:
        from unittest.mock import MagicMock, patch

        commands = iter(
            [
                'doctor',
                'smoke',
                'query MATCH (n:SmokeTest) RETURN n.name',
                'exit',
            ]
        )
        output = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: next(commands), output_fn=output.append
        )
        graph_store = MagicMock()
        graph_store.graph.upsert_node = MagicMock()
        graph_store.query.return_value = [{'n.name': 'TeaAgent'}]

        with (
            patch.object(TeaAgentTUI, '_load_tui_state'),
            patch.object(TeaAgentTUI, '_save_tui_state'),
            patch.object(tui, '_get_store', return_value=graph_store),
            patch(
                'teaagent.tui._commands.check_graphqlite_runtime',
                return_value=(True, 'ok'),
            ),
        ):
            exit_code = tui.run()

        self.assertEqual(exit_code, 0)
        self.assertEqual(output[0], 'TeaAgent TUI 0.1.0')
        parsed = []
        for line in output:
            try:
                parsed.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        doctor_payload = parsed[0]
        self.assertTrue(doctor_payload['ok'])
        self.assertEqual(parsed[1], [{'n.name': 'TeaAgent'}])
        self.assertEqual(parsed[2], [{'n.name': 'TeaAgent'}])
        self.assertEqual(output[-1], 'bye')

    def test_tui_slash_alias_help(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)
        self.assertTrue(tui.handle_command('/help'))
        self.assertTrue(any('Commands:' in line for line in output))

    def test_tui_use_switches_database_label(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('use ./graph.db'))

        self.assertEqual(tui.database, './graph.db')
        self.assertEqual(output, ['database: ./graph.db'])

    def test_tui_smoke_reports_graphqlite_runtime_error(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        with patch.object(
            tui,
            '_get_store',
            side_effect=GraphQLiteRuntimeError('sqlite extension unavailable'),
        ):
            self.assertTrue(tui.handle_command('smoke'))

        self.assertEqual(output, ['error: sqlite extension unavailable'])

    def test_tui_query_reports_graphqlite_runtime_error(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        with patch.object(
            tui,
            '_get_store',
            side_effect=GraphQLiteRuntimeError('sqlite extension unavailable'),
        ):
            self.assertTrue(tui.handle_command('query MATCH (n) RETURN n'))

        self.assertEqual(output, ['error: sqlite extension unavailable'])

    def test_tui_state_save_ignores_os_write_failures(self) -> None:
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit')

        with patch.object(Path, 'write_text', side_effect=PermissionError('denied')):
            tui._save_tui_state()

    def test_tui_agent_settings_and_ask(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'note.txt').write_text('hello', encoding='utf-8')
            commands = iter(
                [
                    f'root {root}',
                    'provider gpt',
                    'model test-model',
                    'permission workspace-write',
                    'ask read note',
                    'runs',
                    'exit',
                ]
            )
            output = []
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"note.txt"},"call_id":"read-note"}',
                    '{"type":"final","content":"note read"}',
                ]
            )
            tui = TeaAgentTUI(
                input_fn=lambda _prompt: next(commands),
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: adapter,
            )
            tui.chat = False
            tui._chat_explicit = True

            exit_code = tui.run()

            self.assertEqual(exit_code, 0)
            self.assertIn(f'root: {root.resolve()}', output)
            self.assertIn('provider: gpt', output)
            self.assertIn('model: test-model', output)
            self.assertIn('permission: workspace-write', output)
            agent_payload = json.loads(output[-2])
            if isinstance(agent_payload, list):
                agent_payload = json.loads(output[-3])
            self.assertEqual(agent_payload['status'], 'completed')
            self.assertEqual(agent_payload['final_answer'], 'note read')
            runs_payload = json.loads(output[-2])
            self.assertEqual(runs_payload[0]['status'], 'completed')

    def test_tui_destructive_toggle(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('destructive on'))
        self.assertTrue(tui.allow_destructive)
        self.assertEqual(output, ['destructive: on'])

    def test_tui_permission_mode(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('permission read-only'))

        self.assertEqual(tui.permission_mode.value, 'read-only')
        self.assertEqual(output, ['permission: read-only'])

    def test_tui_approval_commands(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('approve write-1'))
        self.assertTrue(tui.handle_command('approvals'))
        self.assertTrue(tui.handle_command('unapprove write-1'))
        self.assertTrue(tui.handle_command('approvals'))

        self.assertEqual(output[0], 'approved: write-1')
        self.assertEqual(json.loads(output[1]), ['write-1'])
        self.assertEqual(output[2], 'unapproved: write-1')
        self.assertEqual(json.loads(output[3]), [])

    def test_tui_approved_call_id_allows_exact_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}',
                    '{"type":"final","content":"wrote"}',
                ]
            )
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: adapter,
            )

            self.assertTrue(tui.handle_command('approve write-1'))
            self.assertTrue(tui.handle_command('ask write file'))

            payload = json.loads(output[-1])
            self.assertEqual(payload['status'], 'completed')
            self.assertEqual((Path(tmp) / 'x.txt').read_text(encoding='utf-8'), 'x')

    def test_tui_hitl_approval_prompt_allows_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            replies = iter(['yes'])
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}',
                    '{"type":"final","content":"wrote"}',
                ]
            )
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: next(replies),
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: adapter,
            )

            self.assertTrue(tui.handle_command('ask write file'))

            approval_payload = next(
                json.loads(line)
                for line in output
                if line.strip().startswith('{') and 'approval_required' in line
            )
            self.assertEqual(approval_payload['status'], 'approval_required')
            self.assertIn('approval: approved write-1', output)
            payload = json.loads(output[-1])
            self.assertEqual(payload['status'], 'completed')
            self.assertEqual((Path(tmp) / 'x.txt').read_text(encoding='utf-8'), 'x')

    def test_tui_hitl_approval_denial_blocks_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            replies = iter(['no'])
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}'
                ]
            )
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: next(replies),
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: adapter,
            )

            self.assertTrue(tui.handle_command('ask write file'))

            payload = json.loads(output[-1])
            self.assertEqual(payload['status'], 'failed:permission')
            self.assertFalse((Path(tmp) / 'x.txt').exists())

    def test_tui_scoped_approval_exact_matching(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            from teaagent.ergonomics.approval_store import ApprovalPresetStore
            from teaagent.runner import ApprovalRequest

            output = []
            replies = iter(['yes'])
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: next(replies),
                output_fn=output.append,
            )

            # Create a mock ApprovalRequest with run_id
            request = ApprovalRequest(
                call_id='c123',
                tool_name='workspace_write_file',
                arguments={'path': 'a.txt', 'content': 'hello'},
                reason='Needs approval',
                annotations={
                    'destructive': True,
                    'read_only': False,
                    'idempotent': True,
                },
                run_id='run-tui-123',
            )

            # 1. Trigger the approval handler
            approved = tui._approval_handler(request)
            self.assertTrue(approved)

            # Verify that immediate interactive HITL approval does NOT create a persistent record in the database
            store = ApprovalPresetStore(tmp)
            records = store.list_scoped_approvals_for_run('run-tui-123')
            self.assertEqual(len(records), 0)

            # Verify legacy bare approved_call_ids in TUI is empty
            self.assertNotIn('c123', tui.approved_call_ids)

    def test_tui_resume_creates_precise_scoped_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            from teaagent.ergonomics.approval_store import ApprovalPresetStore
            from teaagent.run_store import RunStore

            output = []
            run_store = RunStore(tmp)
            run_id = 'run-resume-456'

            # Setup a persisted run with a pending approval using the audit logger
            audit = run_store.audit_logger(run_id)
            audit.record('run_started', run_id, task='ask write file')

            args_payload = {'path': 'x.txt', 'content': 'val'}
            digest = _compute_argument_digest(args_payload)

            audit.record(
                'tool_call_pending_approval',
                run_id,
                call_id='c456',
                tool_name='workspace_write_file',
                arguments=args_payload,
                argument_digest=digest,
                argument_digest_version='v1',
                reason='Needs approval',
                annotations={'destructive': True},
            )

            # Build TUI
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: FakeAdapter(
                    ['{"type":"final","content":"done"}']
                ),
            )

            # 2. Trigger TUI resume
            self.assertTrue(tui.handle_command(f'resume {run_id}'))

            # Verify exact scoped approval record exists in the store
            approval_store = ApprovalPresetStore(tmp)
            records = approval_store.list_scoped_approvals_for_run(run_id)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].call_id, 'c456')
            self.assertEqual(records[0].tool_name, 'workspace_write_file')

            # Verify that legacy bare approved_call_ids in TUI is empty
            self.assertNotIn('c456', tui.approved_call_ids)

    def test_tui_clarify_command(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('clarify improve stuff'))

        payload = json.loads(output[0])
        self.assertTrue(payload['needs_clarification'])
        self.assertEqual(
            payload['question'], 'What action do you want TeaAgent to take?'
        )

    def test_tui_progress_streams_audit_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'note.txt').write_text('hello', encoding='utf-8')
            output = []
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"note.txt"},"call_id":"r1"}',
                    '{"type":"final","content":"done"}',
                ]
            )
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: adapter,
            )

            self.assertTrue(tui.handle_command('progress on'))
            self.assertTrue(tui.handle_command('ask read note'))

            joined = '\n'.join(output)
            self.assertIn('iter 1', joined)
            self.assertIn('tool: workspace_read_file', joined)
            self.assertIn('tool ok: workspace_read_file', joined)

    def test_tui_resume_replays_persisted_run_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            adapter = FakeAdapter(
                [
                    '{"type":"final","content":"first"}',
                    '{"type":"final","content":"second"}',
                ]
            )
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: adapter,
            )

            self.assertTrue(tui.handle_command('ask read note'))
            run_id = json.loads(output[-1])['run_id']
            self.assertTrue(tui.handle_command(f'resume {run_id}'))

            resume_payload = json.loads(output[-1])
            self.assertEqual(resume_payload['final_answer'], 'second')
            self.assertIn(f'resume: {run_id}', output)

    def test_tui_resume_replays_observations_for_non_destructive_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'note.txt').write_text('hello', encoding='utf-8')
            output = []
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"note.txt"},"call_id":"read-1"}',
                    '{"type":"final","content":"first-done"}',
                    '{"type":"final","content":"second-done"}',
                ]
            )
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: adapter,
            )

            self.assertTrue(tui.handle_command('ask read note'))
            first_payload = json.loads(output[-1])
            run_id = first_payload['run_id']

            self.assertTrue(tui.handle_command(f'resume {run_id}'))
            resume_payload = json.loads(output[-1])

            self.assertEqual(resume_payload['status'], 'completed')
            self.assertEqual(resume_payload['final_answer'], 'second-done')
            self.assertEqual(resume_payload['replayed_observations'], 1)
            self.assertIn(f'resume: {run_id}', output)

    def test_tui_preflight_command_uses_current_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output: list[str] = []
            tui = TeaAgentTUI(
                root=tmp,
                provider='gpt',
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            self.assertTrue(tui.handle_command('route-model on'))
            self.assertTrue(
                tui.handle_command(
                    'preflight review this patch for regressions in the test suite'
                )
            )

            payload = json.loads(output[-1])
            self.assertTrue(payload['ready'])
            self.assertEqual(payload['routing']['category'], 'review')
            # With complexity-based routing, review tasks (medium complexity) use gpt-4o-mini
            self.assertEqual(payload['model'], 'gpt-4o-mini')
            self.assertIn('complexity', payload['routing'])

    def test_tui_memory_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            tui = TeaAgentTUI(
                root=tmp, input_fn=lambda _prompt: 'exit', output_fn=output.append
            )

            self.assertTrue(
                tui.handle_command('memory add Prefer read-only mode for audits')
            )
            memory_id = json.loads(output[0])['memory_id']
            self.assertTrue(tui.handle_command('memory search audits'))
            self.assertTrue(tui.handle_command(f'memory show {memory_id}'))

            self.assertEqual(json.loads(output[1])[0]['memory_id'], memory_id)
            self.assertEqual(
                json.loads(output[2])['content'], 'Prefer read-only mode for audits'
            )

    def test_tui_route_model_preview_and_ask(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            adapter = FakeAdapter(['{"type":"final","content":"reviewed"}'])
            factory = CapturingAdapterFactory(adapter)
            tui = TeaAgentTUI(
                root=tmp,
                provider='gpt',
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
                adapter_factory=factory,
            )

            self.assertTrue(tui.handle_command('route-model on'))
            self.assertTrue(tui.handle_command('route review this patch'))
            self.assertTrue(tui.handle_command('ask review this patch'))

            route_payload = json.loads(output[1])
            ask_payload = json.loads(output[-1])
            # With complexity-based routing, review tasks (medium complexity) use gpt-4o-mini
            self.assertEqual(route_payload['model'], 'gpt-4o-mini')
            self.assertIn('complexity', route_payload)
            self.assertEqual(factory.calls[0], ('gpt', 'gpt-4o-mini'))
            self.assertEqual(ask_payload['routing']['category'], 'review')

    def test_tui_ask_clarify_stops_before_adapter_when_ambiguous(self) -> None:
        output = []

        def fail_factory(_provider, _model):
            raise AssertionError('adapter should not be created')

        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
            adapter_factory=fail_factory,
        )

        self.assertTrue(tui.handle_command('ask --clarify improve stuff'))

        payload = json.loads(output[0])
        self.assertEqual(payload['status'], 'needs_clarification')
        self.assertTrue(payload['clarification']['needs_clarification'])

    def test_cli_tui_help_in_parser(self) -> None:
        output = io.StringIO()

        with self.assertRaises(SystemExit) as context, redirect_stdout(output):
            main(['tui', '--help'])

        self.assertEqual(context.exception.code, 0)
        self.assertIn('Start an interactive terminal UI', output.getvalue())
        self.assertIn('--provider', output.getvalue())

    def test_tui_empty_command_continues(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command(''))

    def test_tui_help_command(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('help'))
        self.assertIn('help', output[0])
        self.assertIn('provider', output[0])
        self.assertIn('ask', output[0])

    def test_tui_unknown_command(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('unknown-cmd'))
        self.assertIn('unknown command', output[0])

    def test_tui_malformed_shlex_input(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('unclosed "quote'))

    def test_tui_provider_requires_one_arg(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('provider'))
        self.assertIn('requires exactly one', output[0])
        self.assertTrue(tui.handle_command('provider a b'))
        self.assertIn('requires exactly one', output[1])

    def test_tui_provider_unknown_name(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('provider made-up-provider'))
        self.assertIn('unknown provider', output[0])

    def test_tui_model_requires_one_arg(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('model'))
        self.assertIn('requires a model name', output[0])

    def test_tui_model_default_clears_override(self) -> None:
        output = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit', output_fn=output.append, model='custom'
        )

        self.assertTrue(tui.handle_command('model default'))
        self.assertIsNone(tui.model)

    def test_tui_route_model_invalid_arg(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('route-model yes'))
        self.assertIn("requires 'on' or 'off'", output[0])

    def test_tui_route_requires_task(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('route'))
        self.assertIn('requires a task', output[0])

    def test_tui_root_requires_one_arg(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('root'))
        self.assertIn('requires exactly one path', output[0])

    def test_tui_destructive_invalid_arg(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('destructive yes'))
        self.assertIn("requires 'on' or 'off'", output[0])

    def test_tui_progress_invalid_arg(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('progress enabled'))
        self.assertIn("requires 'on' or 'off'", output[0])

    def test_tui_subagent_invalid_arg(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('subagent enabled'))
        self.assertIn("requires 'on' or 'off'", output[0])

    def test_tui_heartbeat_with_number(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('heartbeat 5.5'))
        self.assertEqual(tui.heartbeat_seconds, 5.5)

    def test_tui_heartbeat_zero_disables(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('heartbeat 0'))
        self.assertEqual(tui.heartbeat_seconds, 0.0)

    def test_tui_heartbeat_negative_clamped(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('heartbeat -1'))
        self.assertEqual(tui.heartbeat_seconds, 0.0)

    def test_tui_heartbeat_non_numeric(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('heartbeat abc'))
        self.assertIn('must be a number', output[0])

    def test_tui_heartbeat_requires_one_arg(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('heartbeat'))
        self.assertIn('requires a seconds', output[0])

    def test_tui_status_requires_run_id(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('status'))
        self.assertIn('requires a run id', output[0])

    def test_tui_permission_invalid_raises(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('permission'))
        self.assertIn('requires one mode', output[0])

    def test_tui_permission_invalid_mode(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('permission bogus'))
        self.assertIn('unknown permission mode', output[0])

    def test_tui_approve_requires_call_id(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('approve'))
        self.assertIn('requires one call id', output[0])

    def test_tui_unapprove_requires_call_id(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('unapprove'))
        self.assertIn('requires one call id', output[0])

    def test_tui_ask_requires_task(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('ask'))
        self.assertIn('requires a task', output[0])

    def test_tui_ask_clarify_requires_task(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('ask --clarify'))
        self.assertIn('requires a task', output[0])

    def test_tui_clarify_requires_task(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('clarify'))
        self.assertIn('requires a task', output[0])

    def test_tui_preflight_requires_task(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('preflight'))
        self.assertIn('requires a task', output[0])

    def test_tui_show_requires_run_id(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('show'))
        self.assertIn('requires a run id', output[0])

    def test_tui_resume_requires_run_id(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('resume'))
        self.assertIn('requires a run id', output[0])

    def test_tui_resume_unknown_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            tui = TeaAgentTUI(
                root=tmp, input_fn=lambda _prompt: 'exit', output_fn=output.append
            )

            self.assertTrue(tui.handle_command('resume no-such-run'))
            self.assertIn('error:', output[0])

    def test_tui_use_requires_one_arg(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('use'))
        self.assertIn('requires exactly one database path', output[0])

    def test_tui_query_requires_cypher(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('query'))
        self.assertIn('requires a Cypher string', output[0])

    def test_tui_memory_no_subcommand(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('memory'))
        self.assertIn('requires add, list, search, or show', output[0])

    def test_tui_memory_add_no_text(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('memory add'))
        self.assertIn('requires text', output[0])

    def test_tui_memory_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            tui = TeaAgentTUI(
                root=tmp, input_fn=lambda _prompt: 'exit', output_fn=output.append
            )

            self.assertTrue(tui.handle_command('memory list'))
            self.assertEqual(json.loads(output[0]), [])

    def test_tui_memory_search_no_query(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('memory search'))
        self.assertIn('requires a query', output[0])

    def test_tui_memory_show_requires_id(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('memory show'))
        self.assertIn('requires one id', output[0])

    def test_tui_memory_unknown_subcommand(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('memory delete'))
        self.assertIn('unknown memory command', output[0])

    def test_tui_runs_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            tui = TeaAgentTUI(
                root=tmp, input_fn=lambda _prompt: 'exit', output_fn=output.append
            )

            self.assertTrue(tui.handle_command('runs'))
            self.assertEqual(json.loads(output[0]), [])

    def test_tui_eof_returns_zero(self) -> None:
        output = []

        def raise_eof(_prompt: str) -> str:
            raise EOFError()

        tui = TeaAgentTUI(input_fn=raise_eof, output_fn=output.append)

        exit_code = tui.run()
        self.assertEqual(exit_code, 0)
        self.assertEqual(output[-1], 'bye')

    def test_tui_subagent_on_off(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('subagent on'))
        self.assertTrue(tui.subagent)
        self.assertTrue(tui.handle_command('subagent off'))
        self.assertFalse(tui.subagent)

    def test_tui_clarify_accepts_concrete_task(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(
            tui.handle_command('clarify Update docs/cli.md to document clarify command')
        )
        payload = json.loads(output[0])
        self.assertFalse(payload['needs_clarification'])

    def test_tui_print_header_output(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)
        tui._print_header()

        self.assertEqual(output[0], 'TeaAgent TUI 0.1.0')

    def test_tui_status_with_valid_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            adapter = FakeAdapter(['{"type":"final","content":"done"}'])
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: adapter,
            )
            self.assertTrue(tui.handle_command('ask hello world'))
            run_id = json.loads(output[-1])['run_id']

            self.assertTrue(tui.handle_command(f'status {run_id}'))
            status_payload = json.loads(output[-1])
            self.assertEqual(status_payload['run_id'], run_id)
            self.assertEqual(status_payload['status'], 'completed')

    def test_tui_show_with_valid_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            adapter = FakeAdapter(['{"type":"final","content":"result"}'])
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: adapter,
            )
            self.assertTrue(tui.handle_command('ask task'))
            run_id = json.loads(output[-1])['run_id']

            self.assertTrue(tui.handle_command(f'show {run_id}'))
            events = json.loads(output[-1])
            self.assertIsInstance(events, list)
            self.assertGreater(len(events), 0)

    def test_tui_ask_clarify_with_concrete_task_builds_spec(self) -> None:
        output = []
        adapter = FakeAdapter(['{"type":"final","content":"done"}'])
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
            adapter_factory=lambda _provider, _model: adapter,
        )
        self.assertTrue(
            tui.handle_command(
                'ask --clarify Update docs/cli.md to document clarify command'
            )
        )
        payload = json.loads(output[-1])
        self.assertEqual(payload['status'], 'completed')

    def test_tui_progress_sink_handles_run_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"nonexistent_tool","arguments":{},"call_id":"bad"}',
                ]
            )
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: adapter,
            )
            self.assertTrue(tui.handle_command('progress on'))
            self.assertTrue(tui.handle_command('ask broken'))

            joined = '\n'.join(output)
            self.assertIn('failed:', joined)

    def test_tui_setup_command_writes_workspace_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            state_path = Path(tmp) / '.teaagent' / 'tui_state.json'
            with (
                patch(
                    'teaagent.tui._setup.check_llm_configuration',
                    return_value=(True, 'configured'),
                ),
                patch.object(
                    TeaAgentTUI, '_state_path', new_callable=PropertyMock
                ) as mock_state_path,
            ):
                mock_state_path.return_value = state_path
                tui = TeaAgentTUI(
                    root=tmp,
                    provider='gpt',
                    input_fn=lambda _prompt: 'sk-tui-setup-key',
                    output_fn=output.append,
                )
                self.assertTrue(tui.handle_command('setup write-env'))

            cfg_path = Path(tmp) / '.teaagent' / 'config.json'
            self.assertTrue(cfg_path.exists())
            cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
            self.assertEqual(cfg['provider'], 'gpt')
            env_path = Path(tmp) / '.teaagent' / 'env'
            self.assertTrue(env_path.exists())
            payload = json.loads(next(line for line in output if line.startswith('{')))
            self.assertEqual(payload['mode'], 'setup')
            self.assertNotIn('sk-tui-setup-key', json.dumps(payload))
            self.assertTrue(any('setup: ok' in line for line in output))

    def test_tui_unconfigured_workspace_shows_setup_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            state_path = Path(tmp) / '.teaagent' / 'tui_state.json'
            with patch.object(
                TeaAgentTUI, '_state_path', new_callable=PropertyMock
            ) as mock_state_path:
                mock_state_path.return_value = state_path
                tui = TeaAgentTUI(
                    root=tmp,
                    input_fn=lambda _prompt: 'exit',
                    output_fn=output.append,
                )
                tui.run()
            self.assertTrue(any("type 'setup'" in line.lower() for line in output[:5]))

    def test_run_tui_setup_flag_runs_wizard_before_repl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / '.teaagent' / 'tui_state.json'
            with (
                patch(
                    'teaagent.tui._setup.run_tui_setup', return_value=True
                ) as mock_setup,
                patch.object(
                    TeaAgentTUI, '_state_path', new_callable=PropertyMock
                ) as mock_state_path,
            ):
                mock_state_path.return_value = state_path
                from teaagent.tui import run_tui

                run_tui(
                    root=tmp,
                    run_setup=True,
                    setup_write_env=True,
                    input_fn=lambda _prompt: 'exit',
                )
                mock_setup.assert_called_once()
                _, kwargs = mock_setup.call_args
                self.assertTrue(kwargs.get('write_env'))

    # ── Effort / budget / cost ────────────────────────────────────────────────

    def test_tui_effort_requires_low_normal_high(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._handle_effort([])
        self.assertIn('effort:', output[-1])
        tui._handle_effort(['invalid'])
        self.assertIn('must be low, normal, or high', output[-1])

    def test_tui_effort_sets_level_and_budget(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._handle_effort(['high'])
        self.assertEqual(tui._effort_level, 'high')
        self.assertEqual(tui._max_cost_budget_cents, 5000)
        self.assertEqual(tui._runtime_max_cost_cents, 5000)
        summary = ' '.join(output)
        self.assertIn('budget=$50', summary)

    def test_tui_effort_low_sets_200_cents(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._handle_effort(['low'])
        self.assertEqual(tui._effort_level, 'low')
        self.assertEqual(tui._max_cost_budget_cents, 200)
        self.assertEqual(tui._runtime_max_cost_cents, 200)
        self.assertIn('budget=$2', ' '.join(output))

    def test_tui_budget_shows_remaining(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._session_cost_cents = 50.0
        tui._handle_budget()
        text = ' '.join(output)
        self.assertIn('effort=', text)
        self.assertIn('limit=', text)
        self.assertIn('spent=', text)
        self.assertIn('remaining=', text)

    def test_tui_cost_shows_session_cost(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._session_cost_cents = 123.0
        tui._handle_cost()
        self.assertIn('$1.23', ' '.join(output))

    def test_tui_compact_stub(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._handle_compact()
        self.assertIn('not yet implemented', ' '.join(output))

    # ── Checkpoint / undo ─────────────────────────────────────────────────────

    def test_tui_checkpoint_not_created_yet_returns_false(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        ok = tui._restore_checkpoint()
        self.assertFalse(ok)
        self.assertIn('no checkpoint', ' '.join(output))

    def test_tui_handle_checkpoint_delegates(self) -> None:
        # Use a temp dir (not a git repo) so git commands fail safely
        with tempfile.TemporaryDirectory() as tmpdir:
            output: list[str] = []
            tui = TeaAgentTUI(
                root=tmpdir, input_fn=lambda _: '', output_fn=output.append
            )
            with patch.object(tui, '_start_file_watcher'):
                tui._handle_checkpoint()
            text = ' '.join(output)
            # git stash push in a non-git dir should produce a warning
            self.assertTrue('warning' in text or 'error' in text)

    def test_tui_handle_undo_delegates(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._handle_undo()
        self.assertIn('no checkpoint', ' '.join(output))

    # ── Pin / unpin / pinned ──────────────────────────────────────────────────

    def test_tui_pin_requires_path(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._handle_pin([])
        self.assertIn('requires a file path', ' '.join(output))

    def test_tui_pin_non_existent_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output: list[str] = []
            tui = TeaAgentTUI(
                root=tmpdir, input_fn=lambda _: '', output_fn=output.append
            )
            tui._handle_pin(['nonexistent.py'])
            self.assertIn('file not found', ' '.join(output))

    def test_tui_unpin_requires_path(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._handle_unpin([])
        self.assertIn('requires a file path', ' '.join(output))

    def test_tui_pinned_empty(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._handle_pinned()
        self.assertIn('no files pinned', ' '.join(output))

    def test_tui_budget_wired_to_agent_run(self) -> None:
        """Verify max_estimated_cost_cents is passed to ChatAgentConfig.from_root."""
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._runtime_max_cost_cents = 200
        with (
            patch.object(tui, '_start_file_watcher'),
            patch.object(tui, '_load_tui_state'),
            patch.object(tui, '_save_tui_state'),
            patch('teaagent.tui.run_chat_agent') as mock_run,
            patch('teaagent.tui.RunStore') as mock_store,
            patch('teaagent.tui.create_llm_adapter'),
        ):
            mock_run.return_value = unittest.mock.MagicMock(
                run_id='test-run',
                status='completed',
                iterations=1,
                tool_calls=0,
                final_answer=unittest.mock.MagicMock(content='ok'),
                metadata={},
                error_message=None,
            )
            mock_store.return_value.list_runs.return_value = []
            mock_store.return_value.show_run.return_value = {}
            mock_store.return_value.logger_for_result = lambda *a: None
            mock_store.return_value.audit_logger = lambda: unittest.mock.MagicMock()

            tui._run_agent_task('test task')

            _args, kwargs = mock_run.call_args
            config = kwargs['config']
            self.assertEqual(config.max_estimated_cost_cents, 200)

    def test_tui_file_watcher_start_stop(self) -> None:
        """Verify watcher starts and stops cleanly."""
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        with (
            patch.object(tui, '_start_file_watcher'),
            patch.object(tui, '_stop_file_watcher'),
        ):
            # Pin should try to start watcher
            tui._handle_pin(['nonexistent.py'])
            # unpin should not call stop since pin failed
            tui._handle_unpin(['nonexistent.py'])
        # Just verify no exceptions — real FileWatcher isn't instantiated

    def test_run_tui_function(self) -> None:

        commands = iter(['exit'])
        tui = TeaAgentTUI(
            database=':memory:',
            provider='gpt',
            model='test',
            root='.',
            input_fn=lambda _prompt: next(commands),
            output_fn=lambda _msg: None,
        )
        exit_code = tui.run()
        self.assertEqual(exit_code, 0)

    # ── chat_command() delegation ─────────────────────────────────────────────

    def test_chat_command_forwards_params_to_run_tui(self) -> None:
        """Verify chat_command() forwards CLI args to run_tui()."""
        from argparse import Namespace

        from teaagent.cli._handlers._chat import chat_command
        from teaagent.policy import PermissionMode

        args = Namespace(
            provider='test-provider',
            model='test-model',
            root='/tmp/test-root',
            allow_destructive=True,
            permission_mode='allow',
            max_iterations=5,
            max_tool_calls=3,
            max_estimated_cost_cents=100,
            subagent=True,
            max_subagent_depth=2,
            heartbeat=1.5,
            stream=True,
            skill_search_dirs=['/custom/skills'],
            memory_limit=10,
        )

        with (
            patch('teaagent.tui.run_tui') as mock_run,
            patch(
                'teaagent.cli._handlers._chat.parse_permission_mode',
                return_value=PermissionMode.ALLOW,
            ),
        ):
            chat_command(args)

        self.assertEqual(mock_run.call_args[1]['provider'], 'test-provider')
        self.assertEqual(mock_run.call_args[1]['model'], 'test-model')
        self.assertTrue(mock_run.call_args[1]['allow_destructive'])
        self.assertEqual(mock_run.call_args[1]['permission_mode'], PermissionMode.ALLOW)
        self.assertTrue(mock_run.call_args[1]['chat'])
        self.assertEqual(mock_run.call_args[1]['stream'], True)
        self.assertEqual(mock_run.call_args[1]['subagent'], True)
        self.assertEqual(mock_run.call_args[1]['max_iterations'], 5)
        self.assertEqual(mock_run.call_args[1]['max_tool_calls'], 3)
        self.assertEqual(mock_run.call_args[1]['max_subagent_depth'], 2)
        self.assertEqual(mock_run.call_args[1]['heartbeat_seconds'], 1.5)
        self.assertEqual(mock_run.call_args[1]['max_estimated_cost_cents'], 100)
        self.assertEqual(mock_run.call_args[1]['memory_limit'], 10)

    def test_chat_command_handles_keyboard_interrupt(self) -> None:
        """Verify chat_command() returns 130 on KeyboardInterrupt."""
        from argparse import Namespace

        from teaagent.cli._handlers._chat import chat_command

        args = Namespace(
            provider=None,
            model=None,
            root='.',
            allow_destructive=False,
            permission_mode='prompt',
        )

        with patch('teaagent.tui.run_tui', side_effect=KeyboardInterrupt):
            exit_code = chat_command(args)
        self.assertEqual(exit_code, 130)

    def test_chat_command_handles_exception(self) -> None:
        """Verify chat_command() returns 1 on generic Exception."""
        from argparse import Namespace

        from teaagent.cli._handlers._chat import chat_command

        args = Namespace(
            provider=None,
            model=None,
            root='.',
            allow_destructive=False,
            permission_mode='prompt',
        )

        with patch('teaagent.tui.run_tui', side_effect=RuntimeError('test error')):
            exit_code = chat_command(args)
        self.assertEqual(exit_code, 1)

    def test_chat_command_default_memory_limit(self) -> None:
        """Verify memory_limit defaults to 5 when not in args."""
        from argparse import Namespace

        from teaagent.cli._handlers._chat import chat_command
        from teaagent.policy import PermissionMode

        args = Namespace(
            provider=None,
            model=None,
            root='.',
            allow_destructive=False,
            permission_mode='prompt',
        )

        with (
            patch('teaagent.tui.run_tui') as mock_run,
            patch(
                'teaagent.cli._handlers._chat.parse_permission_mode',
                return_value=PermissionMode.PROMPT,
            ),
        ):
            chat_command(args)

        self.assertEqual(mock_run.call_args[1].get('memory_limit'), 5)

    # ── TeaAgentCompleter tests ───────────────────────────────────────────────

    def test_complete_file_paths_no_at(self) -> None:
        try:
            from teaagent.tui._completion import complete_file_paths
        except ImportError:
            self.skipTest('prompt_toolkit not installed')

        result = complete_file_paths('no-at', Path('.'))
        self.assertEqual(result, [])

    def test_complete_file_paths_basic(self) -> None:
        try:
            from teaagent.tui._completion import complete_file_paths
        except ImportError:
            self.skipTest('prompt_toolkit not installed')

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / 'src').mkdir()
            (root / 'src' / 'main.py').write_text('')
            (root / 'README.md').write_text('')

            result = complete_file_paths('@RE', root)
            self.assertIn('@README.md', result)

            result = complete_file_paths('@src/', root)
            self.assertIn('@src/main.py', result)

    def test_complete_symbols_no_at(self) -> None:
        try:
            from teaagent.tui._completion import complete_symbols
        except ImportError:
            self.skipTest('prompt_toolkit not installed')

        result = complete_symbols('no-at', Path('.'))
        self.assertEqual(result, [])

    def test_get_cached_symbols_empty_repo(self) -> None:
        try:
            from teaagent.tui._completion import _get_cached_symbols
        except ImportError:
            self.skipTest('prompt_toolkit not installed')

        with tempfile.TemporaryDirectory() as tmpdir:
            result = _get_cached_symbols(Path(tmpdir))
        self.assertIsInstance(result, list)

    # ── Memory failures handlers ──────────────────────────────────────────────

    def test_memory_failures_no_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output: list[str] = []
            tui = TeaAgentTUI(
                root=tmpdir, input_fn=lambda _: '', output_fn=output.append
            )
            with patch.object(tui, '_start_file_watcher'):
                tui._handle_memory_failures([])
            self.assertIn('no failure cards recorded', ' '.join(output))

    def test_memory_clear_no_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output: list[str] = []
            tui = TeaAgentTUI(
                root=tmpdir, input_fn=lambda _: '', output_fn=output.append
            )
            with patch.object(tui, '_start_file_watcher'):
                tui._handle_memory_clear([])
            self.assertIn('memory clear:', ' '.join(output))

    def test_memory_clear_invalid_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output: list[str] = []
            tui = TeaAgentTUI(
                root=tmpdir, input_fn=lambda _: '', output_fn=output.append
            )
            with patch.object(tui, '_start_file_watcher'):
                tui._handle_memory_clear(['abc'])
            self.assertIn('requires a number', ' '.join(output))

    def test_memory_clear_out_of_range_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output: list[str] = []
            tui = TeaAgentTUI(
                root=tmpdir, input_fn=lambda _: '', output_fn=output.append
            )
            with patch.object(tui, '_start_file_watcher'):
                tui._handle_memory_clear(['99'])
            self.assertIn('invalid card index', ' '.join(output))


if __name__ == '__main__':
    unittest.main()
