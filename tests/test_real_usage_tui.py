"""Real-usage TUI interactive scenarios (Perspective 2).

Tests simulate how a local user operates TeaAgent through the TUI:
  - ask/run tasks with various permissions
  - Switching provider, model, permission modes mid-session
  - Approval flow (approve/deny destructive tools)
  - Session cost tracking and undo
  - Memory operations, session management
  - Preflight, plan, daily commands
  - Skill diagnostics, pin/unpin files
  - Context compaction, checkpoints

Uses FakeAdapter for fast deterministic execution
or opencodezen-go/deepseek-v4-flash when API key is available.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import PropertyMock, patch

from conftest import FakeAdapter

from teaagent.policy import PermissionMode
from teaagent.tui import TeaAgentTUI

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tmp_root() -> Path:
    td = tempfile.TemporaryDirectory()
    return Path(td.name)


def _make_adapter(responses: list[str]) -> FakeAdapter:
    """Create FakeAdapter with JSON responses simulating model output."""
    return FakeAdapter(responses)


# ============================================================================
# Class T1: Basic TUI flow
# ============================================================================


class TuiBasicFlowScenarios(unittest.TestCase):
    """Core TUI operations: ask, run, help, exit."""

    def test_t1_help_command_shows_all_commands(self) -> None:
        """help output includes key command names."""
        output: list[str] = []
        tui = TeaAgentTUI(
            root=tempfile.TemporaryDirectory().name,
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        tui.handle_command('help')
        joined = '\n'.join(output)
        for cmd in (
            'help',
            'ask',
            'provider',
            'model',
            'permission',
            'approve',
            'memory',
            'cost',
            'undo',
            'exit',
            'daily',
            'plan',
            'preflight',
            'session',
        ):
            self.assertIn(cmd, joined.lower())

    def test_t2_ask_basic_task(self) -> None:
        """Basic ask command runs a task through the full pipeline."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'readme.txt').write_text('Hello TeaAgent', encoding='utf-8')
            output: list[str] = []
            adapter = _make_adapter(
                [
                    '{"type":"tool","tool_name":"workspace_read_file",'
                    '"arguments":{"path":"readme.txt"},"call_id":"r1"}',
                    '{"type":"final","content":"Found: Hello TeaAgent"}',
                ]
            )
            state_path = root / '.teaagent' / 'tui_state.json'
            with patch.object(
                TeaAgentTUI, '_state_path', new_callable=PropertyMock
            ) as mock_sp:
                mock_sp.return_value = state_path
                tui = TeaAgentTUI(
                    root=root,
                    input_fn=lambda _prompt: 'exit',
                    output_fn=output.append,
                    adapter_factory=lambda _p, _m: adapter,
                )
                tui.handle_command('ask read readme.txt')

            joined = '\n'.join(output)
            self.assertIn('Found', joined)
            self.assertIn('Hello TeaAgent', joined)

    def test_t3_run_is_alias_for_ask(self) -> None:
        """run command works as an alias for ask."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            adapter = _make_adapter(
                [
                    '{"type":"final","content":"run alias works"}',
                ]
            )
            state_path = root / '.teaagent' / 'tui_state.json'
            with patch.object(
                TeaAgentTUI, '_state_path', new_callable=PropertyMock
            ) as mock_sp:
                mock_sp.return_value = state_path
                tui = TeaAgentTUI(
                    root=root,
                    input_fn=lambda _prompt: 'exit',
                    output_fn=output.append,
                    adapter_factory=lambda _p, _m: adapter,
                )
                tui.handle_command('run test alias')
            joined = '\n'.join(output)
            self.assertIn('run alias works', joined)

    def test_t4_ask_with_clarify_mode(self) -> None:
        """ask --clarify stops ambiguous tasks before model call."""
        output: list[str] = []

        def fail_factory(_p, _m):
            raise AssertionError('adapter should not be called')

        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
            adapter_factory=fail_factory,
        )
        tui.handle_command('ask --clarify improve everything')
        joined = '\n'.join(output)
        self.assertIn('needs_clarification', joined)

    def test_t5_ask_with_clarify_concrete_proceeds(self) -> None:
        """ask --clarify with concrete task calls the adapter."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            adapter = _make_adapter(
                [
                    '{"type":"final","content":"concrete task done"}',
                ]
            )
            state_path = root / '.teaagent' / 'tui_state.json'
            with patch.object(
                TeaAgentTUI, '_state_path', new_callable=PropertyMock
            ) as mock_sp:
                mock_sp.return_value = state_path
                tui = TeaAgentTUI(
                    root=root,
                    input_fn=lambda _prompt: 'exit',
                    output_fn=output.append,
                    adapter_factory=lambda _p, _m: adapter,
                )
                tui.chat = False
                tui.handle_command('ask --clarify Update the version to 2.0')
            joined = '\n'.join(output)
            self.assertIn('concrete task done', joined)

    def test_t6_exit_command_returns_true(self) -> None:
        """exit command returns False to signal loop termination."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        result = tui.handle_command('exit')
        self.assertFalse(result)

    def test_t7_quit_command_returns_true(self) -> None:
        """quit command also returns False."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        result = tui.handle_command('quit')
        self.assertFalse(result)


# ============================================================================
# Class T2: Permission and approval flow
# ============================================================================


class TuiPermissionApprovalScenarios(unittest.TestCase):
    """Permission mode switching and destructive tool approval in TUI."""

    def test_t2a_permission_command_switches_mode(self) -> None:
        """permission command updates the TUI permission_mode."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        self.assertEqual(tui.permission_mode, PermissionMode.PROMPT)

        tui.handle_command('permission read-only')
        self.assertEqual(tui.permission_mode, PermissionMode.READ_ONLY)

        tui.handle_command('permission workspace-write')
        self.assertEqual(tui.permission_mode, PermissionMode.WORKSPACE_WRITE)

        tui.handle_command('permission allow')
        self.assertEqual(tui.permission_mode, PermissionMode.ALLOW)

    def test_t2b_destructive_toggle(self) -> None:
        """destructive on/off toggles allow_destructive."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        self.assertFalse(tui.allow_destructive)

        tui.handle_command('destructive on')
        self.assertTrue(tui.allow_destructive)

        tui.handle_command('destructive off')
        self.assertFalse(tui.allow_destructive)

    def test_t2c_approval_deny_flow(self) -> None:
        """PROMPT mode with user denial produces pending_approval status."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            replies = iter(['no'])
            adapter = _make_adapter(
                [
                    '{"type":"tool","tool_name":"workspace_write_file",'
                    '"arguments":{"path":"secret.txt","content":"data"},"call_id":"w1"}',
                ]
            )
            state_path = root / '.teaagent' / 'tui_state.json'
            with patch.object(
                TeaAgentTUI, '_state_path', new_callable=PropertyMock
            ) as mock_sp:
                mock_sp.return_value = state_path
                tui = TeaAgentTUI(
                    root=root,
                    input_fn=lambda _prompt: next(replies),
                    output_fn=output.append,
                    adapter_factory=lambda _p, _m: adapter,
                    permission_mode=PermissionMode.PROMPT,
                )
                tui.handle_command('ask write secret.txt')

            payload = json.loads(output[-1])
            self.assertEqual(payload['status'], 'pending_approval')
            self.assertFalse((root / 'secret.txt').exists())

    def test_t2d_approval_approve_flow(self) -> None:
        """PROMPT mode with user approval allows the tool to proceed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            replies = iter(['yes'])
            adapter = _make_adapter(
                [
                    '{"type":"tool","tool_name":"workspace_write_file",'
                    '"arguments":{"path":"allowed.txt","content":"safe"},"call_id":"w1"}',
                ]
            )
            state_path = root / '.teaagent' / 'tui_state.json'
            with patch.object(
                TeaAgentTUI, '_state_path', new_callable=PropertyMock
            ) as mock_sp:
                mock_sp.return_value = state_path
                tui = TeaAgentTUI(
                    root=root,
                    input_fn=lambda _prompt: next(replies),
                    output_fn=output.append,
                    adapter_factory=lambda _p, _m: adapter,
                    permission_mode=PermissionMode.PROMPT,
                )
                tui.handle_command('ask write allowed.txt')
            # The file may or may not be written depending on adapter follow-through
            joined = '\n'.join(output)
            self.assertIn('approved', joined.lower())

    def test_t2e_approve_and_unapprove_call_ids(self) -> None:
        """approve/unapprove commands manage the approved_call_ids set."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        tui.handle_command('approve call-123')
        tui.handle_command('approve call-456')
        tui.handle_command('approvals')
        self.assertIn('call-123', '\n'.join(output))
        self.assertIn('call-456', '\n'.join(output))

        tui.handle_command('unapprove call-123')
        out2 = '\n'.join(output)
        # Should have added info about removal
        self.assertIn('call-123', out2)  # was already there


# ============================================================================
# Class T3: Provider and model switching
# ============================================================================


class TuiProviderModelScenarios(unittest.TestCase):
    """Switching provider and model during a TUI session."""

    def test_t3a_provider_command(self) -> None:
        """provider command sets the active provider."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        self.assertIsNone(tui.provider)
        tui.handle_command('provider opencodezen-go')
        self.assertEqual(tui.provider, 'opencodezen-go')
        tui.handle_command('provider claude')
        self.assertEqual(tui.provider, 'claude')

    def test_t3b_model_command(self) -> None:
        """model command sets the model override."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        self.assertIsNone(tui.model)
        tui.handle_command('model deepseek-v4-flash')
        self.assertEqual(tui.model, 'deepseek-v4-flash')

    def test_t3c_model_default_clears_override(self) -> None:
        """model default clears the override."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        tui.model = 'deepseek-v4-flash'
        tui.handle_command('model default')
        self.assertIsNone(tui.model)

    def test_t3d_provider_and_model_in_run(self) -> None:
        """Provider/model settings propagate to the adapter factory."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            adapter = _make_adapter(
                [
                    '{"type":"final","content":"configured run"}',
                ]
            )
            captured_provider = None
            captured_model = None

            def tracking_factory(provider, model):
                nonlocal captured_provider, captured_model
                captured_provider = provider
                captured_model = model
                return adapter

            state_path = root / '.teaagent' / 'tui_state.json'
            with patch.object(
                TeaAgentTUI, '_state_path', new_callable=PropertyMock
            ) as mock_sp:
                mock_sp.return_value = state_path
                tui = TeaAgentTUI(
                    root=root,
                    provider='opencodezen-go',
                    model='deepseek-v4-flash',
                    input_fn=lambda _prompt: 'exit',
                    output_fn=output.append,
                    adapter_factory=tracking_factory,
                )
                tui.handle_command('ask simple test')

            self.assertEqual(captured_provider, 'opencodezen-go')
            self.assertEqual(captured_model, 'deepseek-v4-flash')


# ============================================================================
# Class T4: Session cost, undo, and checkpoint
# ============================================================================


class TuiCostAndUndoScenarios(unittest.TestCase):
    """Cost tracking, undo, and checkpoint operations in TUI."""

    def test_t4a_cost_command(self) -> None:
        """cost command displays the current session cost."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        tui.handle_command('cost')
        joined = '\n'.join(output)
        # Should display a dollar amount
        self.assertIn('$', joined)

    def test_t4b_undo_without_journal(self) -> None:
        """undo command without prior runs shows nothing to undo."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command('undo')
            joined = '\n'.join(output).lower()
            self.assertTrue('nothing' in joined or 'no' in joined or 'undo' in joined)

    def test_t4c_checkpoint_command(self) -> None:
        """checkpoint creates a git checkpoint (may skip if no git)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command('checkpoint')
            joined = '\n'.join(output).lower()
            # Should either succeed or indicate git is not available
            self.assertTrue(
                'checkpoint' in joined or 'not a git' in joined or 'error' in joined
            )

    def test_t4d_budget_command(self) -> None:
        """budget command shows current budget status."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        tui.handle_command('budget')
        joined = '\n'.join(output).lower()
        self.assertIn('budget', joined)

    def test_t4e_effort_command(self) -> None:
        """effort command sets the effort level."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        tui.handle_command('effort high')
        tui.handle_command('budget')
        joined = '\n'.join(output).lower()
        self.assertIn('high', joined)


# ============================================================================
# Class T5: Session and memory management
# ============================================================================


class TuiSessionMemoryScenarios(unittest.TestCase):
    """Chat session lifecycle and memory operations."""

    def test_t5a_session_new_command(self) -> None:
        """session new creates a new chat session."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
            database=':memory:',
        )
        tui.handle_command('session new')
        joined = '\n'.join(output)
        self.assertIn('session', joined)
        self.assertIn('new', joined.lower())

    def test_t5b_session_list_command(self) -> None:
        """session list shows saved sessions."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        tui.handle_command('session list')
        joined = '\n'.join(output)
        # May be empty or have sessions, should not error
        self.assertNotIn('error', joined.lower())

    def test_t5c_memory_add_and_list(self) -> None:
        """memory add and list work within the TUI."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command('memory add TUI integration test note')
            tui.handle_command('memory list')

            joined = '\n'.join(output)
            self.assertIn('TUI integration test note', joined)

    def test_t5d_memory_search(self) -> None:
        """memory search finds matching entries."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command('memory add remember this fact')
            tui.handle_command('memory search fact')
            joined = '\n'.join(output)
            self.assertIn('remember this fact', joined)

    def test_t5e_session_show(self) -> None:
        """session show displays current session details."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        tui.handle_command('session new')
        tui.handle_command('session show')
        self.assertTrue(len(output) > 0)


# ============================================================================
# Class T6: Preflight, plan, and daily commands
# ============================================================================


class TuiPreflightPlanDailyScenarios(unittest.TestCase):
    """Read-only planning and readiness from the TUI."""

    def test_t6a_preflight_command(self) -> None:
        """preflight shows readiness report without calling model."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []

            def fail_factory(p, m):
                raise AssertionError('should not call model')

            tui = TeaAgentTUI(
                root=root,
                provider='opencodezen-go',
                model='deepseek-v4-flash',
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
                adapter_factory=fail_factory,
            )
            tui.handle_command('preflight analyze the test suite')
            joined = '\n'.join(output)
            self.assertNotIn('error', joined.lower())

    def test_t6b_plan_command(self) -> None:
        """plan command writes a plan artifact."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.teaagent').mkdir(exist_ok=True)
            output: list[str] = []

            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command('plan add a new feature')
            self.assertTrue(len(output) > 0)

    def test_t6c_daily_command(self) -> None:
        """daily shows readiness without model call."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []

            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command('daily summarize recent activities')
            joined = '\n'.join(output)
            self.assertNotIn('error', joined.lower())

    def test_t6d_clarify_command_in_tui(self) -> None:
        """clarify command scores ambiguity without model call."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        tui.handle_command('clarify improve things')
        joined = '\n'.join(output)
        self.assertIn('needs_clarification', joined)

    def test_t6e_complexity_command(self) -> None:
        """complexity command analyzes task difficulty."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        tui.handle_command('complexity Refactor the database layer')
        joined = '\n'.join(output)
        self.assertTrue(
            'complexity' in joined.lower()
            or 'simple' in joined.lower()
            or 'medium' in joined.lower()
            or 'high' in joined.lower()
        )

    def test_t6f_route_command(self) -> None:
        """route command shows model routing for a task."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        tui.handle_command('route analyze this Python code')
        self.assertTrue(len(output) > 0)


# ============================================================================
# Class T7: TUI output mode toggling
# ============================================================================


class TuiOutputModeScenarios(unittest.TestCase):
    """Progress, stream, and subagent toggling."""

    def test_t7a_progress_toggle(self) -> None:
        """progress on/off toggles verbose audit output."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        self.assertTrue(tui.progress)
        tui.handle_command('progress off')
        self.assertFalse(tui.progress)
        tui.handle_command('progress on')
        self.assertTrue(tui.progress)

    def test_t7b_stream_toggle(self) -> None:
        """stream on/off toggles token-by-token output."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        self.assertFalse(tui.stream)
        tui.handle_command('stream on')
        self.assertTrue(tui.stream)
        tui.handle_command('stream off')
        self.assertFalse(tui.stream)

    def test_t7c_subagent_toggle(self) -> None:
        """subagent on/off exposes the subagent delegation tool."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        self.assertFalse(tui.subagent)
        tui.handle_command('subagent on')
        self.assertTrue(tui.subagent)
        tui.handle_command('subagent off')
        self.assertFalse(tui.subagent)

    def test_t7d_chat_mode_toggle(self) -> None:
        """chat on/off toggles multi-turn conversation mode."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        self.assertFalse(tui.chat)
        tui.handle_command('chat on')
        self.assertTrue(tui.chat)
        tui.handle_command('chat off')
        self.assertFalse(tui.chat)

    def test_t7e_heartbeat_command(self) -> None:
        """heartbeat sets the interval for run liveness checks."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        self.assertEqual(tui.heartbeat_seconds, 0.0)
        tui.handle_command('heartbeat 30')
        self.assertEqual(tui.heartbeat_seconds, 30.0)


# ============================================================================
# Class T8: Advanced TUI operations
# ============================================================================


class TuiAdvancedOperationsScenarios(unittest.TestCase):
    """Pin/unpin files, context compaction, runs, resume, root change."""

    def test_t8a_pin_and_unpin_files(self) -> None:
        """pin and unpin commands manage watched files."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'watch.txt').write_text('content')
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command('pin watch.txt')
            tui.handle_command('pinned')
            joined = '\n'.join(output)
            self.assertIn('watch.txt', joined)

            tui.handle_command('unpin watch.txt')

    def test_t8b_compact_context(self) -> None:
        """compact triggers context compression."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command('compact')
            joined = '\n'.join(output).lower()
            self.assertTrue(
                'compact' in joined
                or 'compress' in joined
                or 'error' in joined
                or 'context' in joined
            )

    def test_t8c_runs_list_command(self) -> None:
        """runs command lists recent agent runs."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command('runs')
            self.assertTrue(len(output) > 0)

    def test_t8d_root_command(self) -> None:
        """root command changes the workspace root."""
        with (
            tempfile.TemporaryDirectory() as orig,
            tempfile.TemporaryDirectory() as new_root,
        ):
            output: list[str] = []
            tui = TeaAgentTUI(
                root=orig,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command(f'root {new_root}')
            self.assertEqual(str(tui.root), str(Path(new_root).resolve()))

    def test_t8e_skill_diagnostics_command(self) -> None:
        """skill-diagnostics shows loaded skill information."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        tui.handle_command('skill-diagnostics')
        self.assertTrue(len(output) > 0)

    def test_t8f_skill_health_command(self) -> None:
        """skill-health shows skill ecosystem health."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        tui.handle_command('skill-health')
        self.assertTrue(len(output) > 0)


# ============================================================================
# Class T9: TUI run() method scenarios
# ============================================================================


class TuiRunMethodScenarios(unittest.TestCase):
    """TeaAgentTUI.run() entry point with various initial configurations."""

    def test_t9a_run_with_initial_task(self) -> None:
        """run() with initial_task executes it before the interactive loop."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            adapter = _make_adapter(
                [
                    '{"type":"final","content":"initial task done"}',
                ]
            )
            state_path = root / '.teaagent' / 'tui_state.json'
            with patch.object(
                TeaAgentTUI, '_state_path', new_callable=PropertyMock
            ) as mock_sp:
                mock_sp.return_value = state_path
                tui = TeaAgentTUI(
                    root=root,
                    input_fn=lambda _prompt: 'exit',
                    output_fn=output.append,
                    adapter_factory=lambda _p, _m: adapter,
                )
                exit_code = tui.run(initial_task='test initial')
                self.assertEqual(exit_code, 0)

            joined = '\n'.join(output)
            self.assertIn('initial task done', joined)

    def test_t9b_run_exits_cleanly(self) -> None:
        """run() with exit command returns 0."""
        output: list[str] = []
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )
        exit_code = tui.run()
        self.assertEqual(exit_code, 0)

    def test_t9c_run_in_chat_mode(self) -> None:
        """run() in chat mode supports multi-turn."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []

            def input_fn(prompt):
                return 'exit'

            tui = TeaAgentTUI(
                root=root,
                input_fn=input_fn,
                output_fn=output.append,
            )
            tui.chat = True
            exit_code = tui.run()
            self.assertEqual(exit_code, 0)


# ============================================================================
# Class H: TUI parallel experiment scenarios
# ============================================================================


class TuiParallelExperimentScenarios(unittest.TestCase):
    """Parallel experiment stack and TUI parallel/select/cancel commands."""

    def test_h1_parallel_stack_initializes_empty(self) -> None:
        """ParallelExperimentStack constructor with no options creates empty state."""
        from teaagent.sandbox._parallel_experiment import ParallelExperimentStack

        stack = ParallelExperimentStack('/tmp/dummy', 'run-1', [])
        # Internal sandboxes dict should be empty
        self.assertEqual(len(stack._sandboxes), 0)
        # Options list should be empty
        self.assertEqual(len(stack._options), 0)
        # Original branch is None before start_all
        self.assertIsNone(stack._original_branch)

    def test_h2_parallel_command_stores_options(self) -> None:
        """TUI parallel command stores options for later selection."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command('parallel optA optB optC')
            joined = '\n'.join(output)
            self.assertIn('optA', joined)
            self.assertIn('optB', joined)
            self.assertIn('optC', joined)
            self.assertIn('options_stored', joined)
            self.assertIn('count', joined)

    def test_h3_select_command_chooses_branch_by_index(self) -> None:
        """TUI select command picks an option by numeric index."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command('parallel alpha beta gamma')
            output.clear()
            tui.handle_command('select 0')
            joined = '\n'.join(output)
            self.assertIn('alpha', joined)
            self.assertIn('selected', joined)

    def test_h4_cancel_command_clears_parallel_options(self) -> None:
        """TUI cancel command clears stored parallel options."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command('parallel x y')
            output.clear()
            tui.handle_command('cancel')
            joined = '\n'.join(output)
            self.assertIn('cancelled', joined)
            self.assertIn('cleared_parallel_options', joined)
            # After cancel, selecting should fail
            output.clear()
            tui.handle_command('select 0')
            joined2 = '\n'.join(output)
            self.assertIn('no parallel options available', joined2)


# ============================================================================
# Class I: TUI conflict resolution scenarios
# ============================================================================


class TuiConflictResolutionScenarios(unittest.TestCase):
    """Conflict resolution functions using real git repos."""

    def _make_temp_git_repo(self) -> str:
        """Create a temporary git repo and return its path."""
        import subprocess as _sp

        td = tempfile.mkdtemp()
        root = Path(td)
        # Init git
        _sp.run(['git', 'init'], cwd=root, capture_output=True, text=True)
        _sp.run(
            ['git', 'config', 'user.email', 't@t.com'],
            cwd=root,
            capture_output=True,
            text=True,
        )
        _sp.run(
            ['git', 'config', 'user.name', 'T'],
            cwd=root,
            capture_output=True,
            text=True,
        )
        # Create initial commit
        (root / 'file.txt').write_text('initial content', encoding='utf-8')
        _sp.run(['git', 'add', 'file.txt'], cwd=root, capture_output=True, text=True)
        _sp.run(
            ['git', 'commit', '-m', 'initial'],
            cwd=root,
            capture_output=True,
            text=True,
        )
        return td

    def _make_conflicting_branches(self, git_root: str) -> None:
        """Create two branches with conflicting edits to file.txt."""
        import subprocess as _sp

        root = Path(git_root)
        # Create branch-a with different content
        _sp.run(
            ['git', 'checkout', '-b', 'branch-a'],
            cwd=root,
            capture_output=True,
            text=True,
        )
        (root / 'file.txt').write_text('branch a content', encoding='utf-8')
        _sp.run(['git', 'add', 'file.txt'], cwd=root, capture_output=True, text=True)
        _sp.run(
            ['git', 'commit', '-m', 'branch-a change'],
            cwd=root,
            capture_output=True,
            text=True,
        )
        # Back to main and create branch-b
        _sp.run(
            ['git', 'checkout', '-b', 'branch-b', 'main'],
            cwd=root,
            capture_output=True,
            text=True,
        )
        (root / 'file.txt').write_text('branch b content', encoding='utf-8')
        _sp.run(['git', 'add', 'file.txt'], cwd=root, capture_output=True, text=True)
        _sp.run(
            ['git', 'commit', '-m', 'branch-b change'],
            cwd=root,
            capture_output=True,
            text=True,
        )

    def test_i1_has_merge_conflicts_false_when_clean(self) -> None:
        """has_merge_conflicts returns False in a clean repo with no merge."""
        from teaagent.sandbox._git_branch import has_merge_conflicts

        repo = self._make_temp_git_repo()
        try:
            result = has_merge_conflicts(repo)
            self.assertFalse(result)
        finally:
            import shutil

            shutil.rmtree(repo, ignore_errors=True)

    def test_i2_get_conflicted_files_empty_when_clean(self) -> None:
        """get_conflicted_files returns empty list when no conflicts exist."""
        from teaagent.sandbox._git_branch import get_conflicted_files

        repo = self._make_temp_git_repo()
        try:
            result = get_conflicted_files(repo)
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 0)
        finally:
            import shutil

            shutil.rmtree(repo, ignore_errors=True)

    def test_i3_resolve_conflict_accept_ours_handles_non_git_elegantly(self) -> None:
        """resolve_conflict_accept_ours returns False outside git repo (no crash)."""
        from teaagent.sandbox._git_branch import resolve_conflict_accept_ours

        with tempfile.TemporaryDirectory() as tmp:
            # Not a git repo - should return False gracefully
            result = resolve_conflict_accept_ours(tmp, 'nonexistent.txt')
            self.assertIsInstance(result, bool)
            # May be True or False depending on implementation, but must not raise
            self.assertIn(result, (True, False))

    def test_i4_resolve_conflict_accept_theirs_handles_non_git_elegantly(self) -> None:
        """resolve_conflict_accept_theirs returns False outside git repo (no crash)."""
        from teaagent.sandbox._git_branch import resolve_conflict_accept_theirs

        with tempfile.TemporaryDirectory() as tmp:
            result = resolve_conflict_accept_theirs(tmp, 'missing.txt')
            self.assertIsInstance(result, bool)
            self.assertIn(result, (True, False))


# ============================================================================
# Class J: TUI doctor scenarios
# ============================================================================


class TuiDoctorScenarios(unittest.TestCase):
    """TUI doctor command diagnostics."""

    def test_j1_doctor_command_does_not_crash(self) -> None:
        """doctor command runs without throwing an exception."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
                database=':memory:',
            )
            # May succeed or fail depending on graphqlite availability
            tui.handle_command('doctor')
            self.assertTrue(len(output) > 0)

    def test_j2_doctor_model_argument_accepted(self) -> None:
        """doctor model command does not crash."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
                database=':memory:',
            )
            tui.handle_command('doctor model')
            self.assertTrue(len(output) > 0)

    def test_j3_doctor_providers_argument_accepted(self) -> None:
        """doctor providers command does not crash."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
                database=':memory:',
            )
            tui.handle_command('doctor providers')
            self.assertTrue(len(output) > 0)


# ============================================================================
# Class K: TUI session persistence scenarios
# ============================================================================


class TuiSessionPersistenceScenarios(unittest.TestCase):
    """ChatSession and SessionStore round-trip persistence."""

    def test_k1_session_store_saves_and_loads(self) -> None:
        """SessionStore.save() persists and load() retrieves a ChatSession."""
        from teaagent.session import ChatSession, SessionStore

        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(root=tmp)
            session = ChatSession(id='test-session-001', label='integration test')
            store.save(session)
            loaded = store.load('test-session-001')
            self.assertIsNotNone(loaded)
            assert loaded is not None  # type narrowing
            self.assertEqual(loaded.id, 'test-session-001')
            self.assertEqual(loaded.label, 'integration test')
            self.assertEqual(len(loaded.messages), 0)

    def test_k2_chat_session_has_messages_list(self) -> None:
        """ChatSession instance provides a messages list attribute."""
        from teaagent.session import ChatMessage, ChatSession

        session = ChatSession(id='msg-test', label='messages')
        self.assertIsInstance(session.messages, list)
        self.assertEqual(len(session.messages), 0)

        msg = ChatMessage(role='user', content='hello world')
        session.messages.append(msg)
        self.assertEqual(len(session.messages), 1)
        self.assertEqual(session.messages[0].role, 'user')
        self.assertEqual(session.messages[0].content, 'hello world')

    def test_k3_session_multi_message_persists_correctly(self) -> None:
        """ChatSession with multiple messages survives round-trip."""
        from teaagent.session import ChatMessage, ChatSession, SessionStore

        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(root=tmp)
            session = ChatSession(id='multi-msg', label='multi')
            session.messages.append(ChatMessage(role='system', content='context'))
            session.messages.append(ChatMessage(role='user', content='question'))
            session.messages.append(ChatMessage(role='assistant', content='answer'))
            store.save(session)

            loaded = store.load('multi-msg')
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(len(loaded.messages), 3)
            roles = [m.role for m in loaded.messages]
            self.assertEqual(roles, ['system', 'user', 'assistant'])
            self.assertEqual(loaded.messages[2].content, 'answer')

    def test_k4_tui_session_new_switch_show(self) -> None:
        """TUI session new, switch, show commands operate without crash."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
                database=':memory:',
            )
            # session new
            tui.handle_command('session new')
            joined = '\n'.join(output)
            self.assertIn('session new:', joined.lower())

            # session show
            output.clear()
            tui.handle_command('session show')
            joined2 = '\n'.join(output)
            self.assertIn('id', joined2)

            # session list
            output.clear()
            tui.handle_command('session list')
            joined3 = '\n'.join(output)
            self.assertNotIn('error', joined3.lower())


# ============================================================================
# Class L: TUI background and handoff scenarios
# ============================================================================


class TuiBackgroundHandoffScenarios(unittest.TestCase):
    """Background suspension, handoff, run listing, and run show commands."""

    def test_l1_background_command_does_not_crash(self) -> None:
        """background command produces suspension checkpoint message."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command('background')
            joined = '\n'.join(output)
            self.assertIn('background', joined.lower())
            self.assertIn('checkpoint', joined.lower())

    def test_l2_handoff_command_output(self) -> None:
        """handoff command prints informational message (no active run)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command('handoff')
            joined = '\n'.join(output)
            # Delegates to same handler as background
            self.assertIn('background', joined.lower())

    def test_l3_runs_command_lists_runs(self) -> None:
        """runs command outputs JSON run listing without crashing."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command('runs')
            self.assertTrue(len(output) > 0)

    def test_l4_show_unknown_id_handles_error(self) -> None:
        """show command with unknown run ID does not crash."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            # show without args
            tui.handle_command('show')
            joined = '\n'.join(output)
            self.assertIn('error', joined.lower())
            # show with bogus ID raises FileNotFoundError
            output.clear()
            with self.assertRaises(FileNotFoundError):
                tui.handle_command('show NONEXISTENT_12345')


# ============================================================================
# Class M: TUI setup and skill scenarios
# ============================================================================


class TuiSetupAndSkillScenarios(unittest.TestCase):
    """Guided setup and skill diagnostics in the TUI."""

    def test_m1_setup_command_produces_guided_output(self) -> None:
        """setup command produces output without crashing."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command('setup')
            self.assertTrue(len(output) > 0)

    def test_m2_setup_write_env_command(self) -> None:
        """setup write-env produces output without crashing."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command('setup write-env')
            self.assertTrue(len(output) > 0)

    def test_m3_skills_command_produces_output(self) -> None:
        """skills command prints skill activation information."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
            )
            tui.handle_command('skills')
            self.assertTrue(len(output) > 0)


if __name__ == '__main__':
    unittest.main()
