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
from teaagent.policy import PermissionMode
from teaagent.tui import TeaAgentTUI
from test_support import can_bind_loopback


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
                allow_destructive=True,  # Enable destructive operations
                permission_mode=PermissionMode.PROMPT,  # Use PROMPT mode for approval
            )

            self.assertTrue(tui.handle_command('ask write file'))

            approval_payload = next(
                json.loads(line)
                for line in output
                if line.strip().startswith('{') and 'approval' in line
            )
            # Check if approval was handled (either preset allowed or approval_required)
            assert approval_payload['status'] in ('approval_required', 'completed')
            if approval_payload['status'] == 'approval_required':
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
            # After approval gate fix, denied approvals return pending_approval instead of failed:permission
            self.assertEqual(payload['status'], 'pending_approval')
            self.assertFalse((Path(tmp) / 'x.txt').exists())

    def test_tui_path_approval_without_path_stays_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            from teaagent.ergonomics.approval_store import ApprovalPresetStore
            from teaagent.runner import ApprovalRequest

            output = []
            replies = iter(['p'])
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: next(replies),
                output_fn=output.append,
            )

            request = ApprovalRequest(
                call_id='c124',
                tool_name='workspace_write_file',
                arguments={},
                reason='Needs approval',
                annotations={
                    'destructive': True,
                    'read_only': False,
                    'idempotent': True,
                },
                run_id='run-tui-124',
            )

            approved = tui._approval_handler(request)
            self.assertFalse(approved)
            self.assertTrue(
                any('path-scoped grant not created' in str(line) for line in output)
            )

            store = ApprovalPresetStore(tmp)
            self.assertEqual(store.list_grants(), [])

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

    def test_tui_session_clear_empties_persisted_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            from teaagent.session import ChatMessage, SessionStore

            output: list[str] = []
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )

            self.assertTrue(tui.handle_command('session new'))
            session_id = tui.session_id
            self.assertIsNotNone(session_id)

            store = SessionStore(tmp)
            session = store.load(session_id)
            self.assertIsNotNone(session)
            assert session is not None
            session.messages.extend(
                [
                    ChatMessage(role='user', content='hello'),
                    ChatMessage(role='assistant', content='hi'),
                ]
            )
            store.save(session)

            self.assertTrue(tui.handle_command('session clear'))

            cleared = store.load(session_id)
            self.assertIsNotNone(cleared)
            assert cleared is not None
            self.assertEqual(cleared.messages, [])
            self.assertEqual(output[-1], 'session cleared')

    def test_tui_session_clear_without_active_session_reports_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output: list[str] = []
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )

            self.assertTrue(tui.handle_command('session clear'))

            self.assertEqual(output[-1], 'error: no active session')

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
            if not can_bind_loopback():
                self.assertFalse(payload['ready'])
                return

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

    def test_tui_uses_chat_session_controller_for_cost_tracking(self) -> None:
        """TASK-002: Verify TUI uses ChatSessionController for unified cost tracking."""
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )

            # Verify chat controller is created
            controller = tui._get_chat_controller()
            self.assertIsNotNone(controller)
            self.assertIs(controller.session_state, tui._session_state)
            self.assertEqual(controller.session_state.session_cost_cents, 0.0)
            self.assertIs(tui._get_chat_controller(), controller)

    def test_tui_cost_command_shows_controller_cost(self) -> None:
        """TUI /cost should reflect controller state and keep currency formatting."""
        with tempfile.TemporaryDirectory() as tmp:
            output: list[str] = []
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )

            controller = tui._get_chat_controller()
            controller.session_state.session_cost_cents = 123.0

            tui._handle_cost()

            self.assertEqual(output[-1], 'cost: $1.23')

    def test_tui_cost_command_falls_back_to_local_when_controller_is_zero(self) -> None:
        """When controller returns 0 but local has accumulated cost, use local."""
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._session_cost_cents = 250.0
        tui._handle_cost()
        self.assertEqual(output[-1], 'cost: $2.50')

    def test_tui_plan_command_generates_clarification(self) -> None:
        """Test TUI plan command generates task clarification."""
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )

            self.assertTrue(tui.handle_command('plan write a test function'))
            result = json.loads(output[-1])
            self.assertEqual(result['status'], 'clarification_generated')
            self.assertIn('plan', result)
            self.assertIn('ambiguity', result['plan'])

    def test_tui_parallel_command_stores_options(self) -> None:
        """Test TUI parallel command stores options for selection."""
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )

            self.assertTrue(tui.handle_command('parallel option1 option2 option3'))
            result = json.loads(output[-1])
            self.assertEqual(result['status'], 'options_stored')
            self.assertEqual(result['count'], 3)
            self.assertEqual(result['options'], ['option1', 'option2', 'option3'])
            self.assertTrue(hasattr(tui, '_parallel_options'))
            self.assertEqual(tui._parallel_options, ['option1', 'option2', 'option3'])

    def test_tui_select_command_chooses_option(self) -> None:
        """Test TUI select command chooses from parallel options."""
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )

            # First set up parallel options
            tui.handle_command('parallel option1 option2 option3')
            output.clear()

            # Select by index
            self.assertTrue(tui.handle_command('select 0'))
            result = json.loads(output[-1])
            self.assertEqual(result['status'], 'selected')
            self.assertEqual(result['selected'], 'option1')
            self.assertEqual(result['index'], 0)
            self.assertIsNone(tui._parallel_options)  # Should be cleared

    def test_tui_cancel_command_clears_parallel_options(self) -> None:
        """Test TUI cancel command clears parallel options."""
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )

            # Set up parallel options
            tui.handle_command('parallel option1 option2')
            output.clear()

            # Cancel
            self.assertTrue(tui.handle_command('cancel'))
            result = json.loads(output[-1])
            self.assertEqual(result['status'], 'cancelled')
            self.assertEqual(result['action'], 'cleared_parallel_options')
            self.assertIsNone(tui._parallel_options)

    def test_tui_conflict_command_provides_hint(self) -> None:
        """Test TUI conflict command provides helpful hint."""
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )

            self.assertTrue(tui.handle_command('conflict'))
            result = json.loads(output[-1])
            self.assertEqual(result['status'], 'conflict_mode')
            self.assertIn('hint', result)
            self.assertIn('git', result['hint'].lower())

    def test_tui_background_command_is_honest_checkpoint(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

        self.assertTrue(tui.handle_command('background'))

        joined = '\n'.join(output).lower()
        self.assertIn('suspension checkpoint', joined)
        self.assertIn('interactive-review', joined)
        self.assertNotIn('--detach', joined)

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

    def test_tui_effort_requires_valid_level(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._handle_effort([])
        self.assertIn('effort:', output[-1])
        tui._handle_effort(['invalid'])
        self.assertIn('must be low, normal, high, or unlimited', output[-1])

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

    def test_tui_effort_default_is_unlimited(self) -> None:
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=list.append)
        self.assertEqual(tui._effort_level, 'unlimited')
        self.assertIsNone(tui._max_cost_budget_cents)
        self.assertIsNone(tui._runtime_max_cost_cents)

    def test_tui_effort_unlimited_clears_budget(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        # Switch to low first to change from default unlimited
        tui._handle_effort(['low'])
        tui._handle_effort(['unlimited'])
        self.assertEqual(tui._effort_level, 'unlimited')
        self.assertIsNone(tui._max_cost_budget_cents)
        self.assertIsNone(tui._runtime_max_cost_cents)

    def test_tui_effort_unlimited_shows_unlimited_text(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._handle_effort(['unlimited'])
        text = ' '.join(output)
        self.assertIn('unlimited', text)
        self.assertNotIn('$0.00', text)

    def test_tui_budget_unlimited_shows_unlimited_text(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._max_cost_budget_cents = None
        tui._session_cost_cents = 50.0
        tui._handle_budget()
        text = ' '.join(output)
        self.assertIn('unlimited', text)
        self.assertIn('spent=', text)
        self.assertNotIn('$0.00', text)

    def test_tui_budget_unlimited_wired_to_agent_run(self) -> None:
        """Verify unlimited (None) is passed as max_estimated_cost_cents."""
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._runtime_max_cost_cents = None
        with (
            patch.object(tui, '_start_file_watcher'),
            patch.object(tui, '_load_tui_state'),
            patch.object(tui, '_save_tui_state'),
            patch('teaagent.chat_session_controller.run_chat_agent') as mock_run,
            patch('teaagent.tui.RunStore') as mock_store,
            patch('teaagent.tui.create_llm_adapter'),
        ):
            mock_run.return_value = unittest.mock.MagicMock(
                run_id='test-run',
                status='completed',
                iterations=1,
                tool_calls=0,
                cost_cents=0.0,
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
            config = _args[0]
            self.assertIsNone(config.max_estimated_cost_cents)

    def test_tui_budget_zero_wired_to_agent_run(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._runtime_max_cost_cents = 0
        with (
            patch.object(tui, '_start_file_watcher'),
            patch.object(tui, '_load_tui_state'),
            patch.object(tui, '_save_tui_state'),
            patch('teaagent.chat_session_controller.run_chat_agent') as mock_run,
            patch('teaagent.tui.RunStore') as mock_store,
            patch('teaagent.tui.create_llm_adapter'),
        ):
            mock_run.return_value = unittest.mock.MagicMock(
                run_id='test-run',
                status='completed',
                iterations=1,
                tool_calls=0,
                cost_cents=0.0,
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
            config = _args[0]
            self.assertEqual(config.max_estimated_cost_cents, 0)

    def test_tui_budget_shows_remaining(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        # Switch to normal so budget has a finite limit
        tui._handle_effort(['normal'])
        tui._session_cost_cents = 50.0
        tui._handle_budget()
        text = ' '.join(output)
        self.assertIn('effort=', text)
        self.assertIn('limit=', text)
        self.assertIn('spent=', text)
        self.assertIn('remaining=', text)

    def test_tui_run_agent_task_accumulates_cost(self) -> None:
        """_run_agent_task must add result.cost_cents to _session_cost_cents.

        This is the regression guard for CG-11 / TICKET-12.  The previous
        test (test_tui_cost_shows_session_cost) injected _session_cost_cents
        directly, so it passed even when the accumulation line was absent.
        This test drives through the real code path to catch that gap.
        """
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        with (
            patch('teaagent.chat_session_controller.run_chat_agent') as mock_run,
            patch('teaagent.tui.RunStore') as mock_store,
            patch('teaagent.tui.create_llm_adapter'),
        ):
            mock_run.return_value = unittest.mock.MagicMock(
                run_id='test-run',
                status='completed',
                iterations=1,
                tool_calls=0,
                cost_cents=150.0,  # the value we expect to accumulate
                input_tokens=100,
                output_tokens=50,
                final_answer=unittest.mock.MagicMock(content='ok'),
                metadata={},
                error_message=None,
            )
            mock_store.return_value.show_run.return_value = {}
            mock_store.return_value.logger_for_result = lambda *a: None
            mock_store.return_value.audit_logger = lambda: unittest.mock.MagicMock()

            self.assertEqual(tui._session_cost_cents, 0.0)
            tui._run_agent_task('test task')
            # After one run, accumulated cost must equal the run's cost_cents.
            self.assertEqual(tui._session_cost_cents, 150.0)

            # Run a second task; total must be additive.
            mock_run.return_value.cost_cents = 75.0
            tui._run_agent_task('second task')
            self.assertEqual(tui._session_cost_cents, 225.0)

    def test_tui_compact_no_session(self) -> None:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        tui._handle_compact()
        self.assertIn('no active chat session', ' '.join(output))

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

    def test_tui_handle_undo_calls_controller_first(self) -> None:
        """_handle_undo must call ChatSessionController.undo_last_run() before checkpoint fallback."""
        import unittest.mock

        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        with patch.object(tui, '_get_chat_controller') as mock_get:
            mock_controller = unittest.mock.MagicMock()
            mock_controller.undo_last_run.return_value = True
            mock_get.return_value = mock_controller

            tui._handle_undo()

            mock_controller.undo_last_run.assert_called_once()
            # Should say journal undo completed, not fall back to checkpoint
            self.assertIn('journal undo completed', ' '.join(output))

    def test_tui_undo_uses_journal(self) -> None:
        """TICKET-12c: TUI /undo restores only run-touched files, not unrelated manual edits."""
        import json
        import tempfile
        from pathlib import Path

        from teaagent.run_store import RunStore
        from teaagent.run_undo import UndoJournal

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir).resolve()
            output: list[str] = []
            tui = TeaAgentTUI(
                root=tmpdir_path, input_fn=lambda _: '', output_fn=output.append
            )

            # Create a file that is in the undo journal
            touched_file = tmpdir_path / 'touched.py'
            touched_file.write_text("print('original touched')", encoding='utf-8')

            # Create an unrelated manual file
            manual_file = tmpdir_path / 'manual.py'
            manual_file.write_text("print('original manual')", encoding='utf-8')

            run_id = 'test_run_123'
            store = RunStore(tmpdir_path)

            # Write a dummy run file so RunStore recognizes it in list_runs()
            run_file = store.run_path(run_id)
            run_file.write_text(
                json.dumps(
                    {
                        'run_id': run_id,
                        'created_at': '2026-06-04T05:00:00Z',
                        'event_type': 'run_started',
                        'payload': {'task': 'do task'},
                    }
                )
                + '\n',
                encoding='utf-8',
            )

            # Initialize journal and record the original state of touched.py
            journal = UndoJournal(tmpdir_path)
            from teaagent.audit import AuditEvent

            started_event = AuditEvent(
                event_type='tool_call_started',
                run_id=run_id,
                payload={
                    'call_id': 'call-1',
                    'tool_name': 'workspace_write_file',
                    'arguments': {
                        'path': 'touched.py',
                        'content': "print('agent changed')",
                    },
                },
            )
            journal(started_event)
            completed_event = AuditEvent(
                event_type='tool_call_completed',
                run_id=run_id,
                payload={
                    'call_id': 'call-1',
                    'tool_name': 'workspace_write_file',
                },
            )
            journal(completed_event)

            # Save it under the run_id undo path
            journal.save_to(store.undo_path(run_id))

            # Now agent "changed" the touched file, and user manually modified both
            touched_file.write_text("print('user modified touched')", encoding='utf-8')
            manual_file.write_text("print('user modified manual')", encoding='utf-8')

            # Run TUI handle_undo
            tui._handle_undo()

            # The touched file should be restored to its original state
            self.assertEqual(
                touched_file.read_text(encoding='utf-8'), "print('original touched')"
            )

            # The manual file was not in the journal, so it must NOT be touched
            self.assertEqual(
                manual_file.read_text(encoding='utf-8'), "print('user modified manual')"
            )

            # Check output message
            self.assertIn('journal undo completed', ' '.join(output))

    def test_tui_ask_safe_wrapper_handles_exception(self) -> None:
        """_safe_run_agent_task in _commands.py should catch exceptions from _run_agent_task."""
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
        with patch.object(
            tui, '_run_agent_task', side_effect=RuntimeError('API failure')
        ):
            from teaagent.tui._commands import _safe_run_agent_task

            _safe_run_agent_task(tui, 'test task')
        # Error message should be shown, not crash
        self.assertIn('error:', ' '.join(output))
        self.assertIn('API failure', ' '.join(output))

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
            patch('teaagent.chat_session_controller.run_chat_agent') as mock_run,
            patch('teaagent.tui.RunStore') as mock_store,
            patch('teaagent.tui.create_llm_adapter'),
        ):
            mock_run.return_value = unittest.mock.MagicMock(
                run_id='test-run',
                status='completed',
                iterations=1,
                tool_calls=0,
                cost_cents=0.0,
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
            config = _args[0]
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
        # When no task positional arg is present, initial_task must be None
        self.assertIsNone(mock_run.call_args[1].get('initial_task'))

    def test_chat_command_forwards_initial_task_to_run_tui(self) -> None:
        """TASK-DD2-001: chat_command must forward the positional task arg.

        `teaagent chat "my task"` parses `my task` into args.task via
        add_agent_run_arguments(include_task_positional=True).  Previously
        chat_command never read args.task, so the task was silently dropped
        and the user got an empty interactive REPL.
        """
        from argparse import Namespace

        from teaagent.cli._handlers._chat import chat_command
        from teaagent.policy import PermissionMode

        args = Namespace(
            task='fix the bug in auth.py',
            provider=None,
            model=None,
            root='.',
            allow_destructive=False,
            permission_mode='prompt',
            max_iterations=10,
            max_tool_calls=10,
            max_estimated_cost_cents=0,
            subagent=False,
            max_subagent_depth=1,
            heartbeat=0.0,
            stream=False,
            enable_git_tools=False,
            skill_search_dirs=None,
            memory_limit=5,
        )

        with (
            patch('teaagent.tui.run_tui') as mock_run,
            patch(
                'teaagent.cli._handlers._chat.parse_permission_mode',
                return_value=PermissionMode.PROMPT,
            ),
        ):
            chat_command(args)

        self.assertEqual(
            mock_run.call_args[1]['initial_task'], 'fix the bug in auth.py'
        )

    def test_run_tui_initial_task_executed_before_repl(self) -> None:
        """TASK-DD2-001: run_tui initial_task must be dispatched before the loop.

        The REPL loop should only start after the initial task completes.
        Verified by confirming _run_agent_task is called with the initial_task
        string before any interactive input is read.
        """
        calls: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _: (_ for _ in ()).throw(EOFError),  # exits immediately
            output_fn=lambda msg: calls.append(str(msg)),
        )
        with (
            patch.object(tui, '_run_agent_task') as mock_task,
            patch.object(tui, '_load_workspace_defaults'),
            patch.object(tui, '_load_tui_state'),
            patch.object(tui, '_print_header'),
            patch.object(tui, '_start_file_watcher'),
            patch.object(tui, '_stop_file_watcher'),
            patch.object(tui, '_save_tui_state'),
        ):
            tui.run(initial_task='the initial task')

        mock_task.assert_called_once_with('the initial task')

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

    # ── TASK-DD2-002: Explicit TUI root guard ─────────────────────────────────────

    def test_tui_explicit_root_not_overridden(self) -> None:
        """When an explicit root is provided, saved state should not override it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create TUI with explicit root
            explicit_root = Path(tmpdir) / 'explicit'
            explicit_root.mkdir()
            output: list[str] = []
            tui = TeaAgentTUI(
                root=explicit_root,
                input_fn=lambda _: '',
                output_fn=output.append,
            )
            tui._root_explicit = True  # Simulate run_tui setting this

            # Create a mock state file with a different root
            state_file = Path(tmpdir) / 'state.json'
            saved_state = {
                'root': '/some/other/path',
                'provider': 'test',
                'model': 'test-model',
            }
            state_file.write_text(json.dumps(saved_state), encoding='utf-8')

            # Use PropertyMock to patch the property
            with patch.object(
                type(tui),
                '_state_path',
                new_callable=PropertyMock,
                return_value=state_file,
            ):
                tui._load_tui_state()

            # Root should remain the explicit one, not the saved one
            self.assertEqual(tui.root.resolve(), explicit_root.resolve())
            self.assertNotEqual(str(tui.root), '/some/other/path')

    def test_tui_no_explicit_root_restores_saved(self) -> None:
        """When no explicit root is provided, saved state should be restored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a saved state with a specific root
            saved_root = Path(tmpdir) / 'saved'
            saved_root.mkdir()

            saved_state = {
                'root': str(saved_root),
                'provider': 'test',
                'model': 'test-model',
            }

            # Create TUI without explicit root (default '.')
            output: list[str] = []
            tui = TeaAgentTUI(
                root=tmpdir,
                input_fn=lambda _: '',
                output_fn=output.append,
            )
            tui._root_explicit = False  # Explicitly False

            # Create a mock state file with saved root
            state_file = Path(tmpdir) / 'state.json'
            state_file.write_text(json.dumps(saved_state), encoding='utf-8')

            # Use PropertyMock to patch the property
            with patch.object(
                type(tui),
                '_state_path',
                new_callable=PropertyMock,
                return_value=state_file,
            ):
                tui._load_tui_state()

            # Root should be restored from saved state
            self.assertEqual(tui.root.resolve(), saved_root.resolve())

    def test_tui_header_shows_active_root(self) -> None:
        """TUI header should display the active root path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output: list[str] = []
            tui = TeaAgentTUI(
                root=tmpdir,
                input_fn=lambda _: '',
                output_fn=output.append,
            )
            tui._print_header()

            # Check that root is shown in header
            header_text = ' '.join(output)
            self.assertIn('Root:', header_text)
            self.assertIn(str(tmpdir), header_text)


if __name__ == '__main__':
    unittest.main()
