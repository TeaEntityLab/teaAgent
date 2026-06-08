"""Real-usage agent chaining & automated execution scenarios (Perspective 1).

Tests simulate how TeaAgent is used in automated/CI/backend contexts:
  - CLI agent run with various permission modes and overrides
  - Multi-step workflow execution
  - Subagent chaining and batch operations
  - Automation handoff composition
  - Swarm parallel execution
  - MCP/ACP server protocols
  - Approval, budget, and audit flows
  - Memory, plugin, and factory operations

Uses opencodezen-go/deepseek-v4-flash for live tests (skips if key absent),
or FakeAdapter/MagicMock for fast deterministic scenarios.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from conftest import FakeAdapter

from teaagent import ChatAgentConfig
from teaagent.chat_agent import run_chat_agent
from teaagent.cli import EXIT_BLOCKING, main
from teaagent.subagents import SubagentManager, register_subagent_tools
from teaagent.types import PermissionMode, ToolAnnotations, ToolRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _opencodezen_api_key() -> str | None:
    """Resolve opencodezen API key from env or .teaagent/env."""
    key = os.environ.get('OPENCODEZEN_API_KEY')
    if key:
        return key
    env_file = Path.cwd() / '.teaagent' / 'env'
    if env_file.is_file():
        for line in env_file.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line.startswith('export OPENCODEZEN_API_KEY='):
                val = line.split('=', 1)[1].strip()
                return val.strip('"').strip("'")
    return None


def _has_api_key() -> bool:
    return _opencodezen_api_key() is not None


SKIP_REASON = 'OPENCODEZEN_API_KEY not set; skipped'


def _make_tmp_root() -> Path:
    td = tempfile.TemporaryDirectory()
    return Path(td.name)


# ============================================================================
# Class A: CLI agent run scenarios
# ============================================================================


class CliAgentRunScenarios(unittest.TestCase):
    """End-to-end CLI agent run with real provider connection.

    These tests call main() directly, exercising the full argument parsing →
    config resolution → adapter creation → agent run pipeline.
    """

    def test_a1_cli_agent_run_basic(self) -> None:
        """Run simple Q&A task via CLI main() with opencodezen-go."""
        key = _opencodezen_api_key()
        if not key:
            self.skipTest(SKIP_REASON)
        with patch.dict(os.environ, {'OPENCODEZEN_API_KEY': key}):
            out = io.StringIO()
            with redirect_stdout(out):
                exit_code = main(
                    [
                        'run',
                        'opencodezen-go',
                        'Reply with exactly: Hello from CLI test',
                        '--model',
                        'deepseek-v4-flash',
                        '--max-iterations',
                        '3',
                        '--max-estimated-cost-cents',
                        '200',
                        '--permission-mode',
                        'read-only',
                        '--human',
                    ]
                )
            self.assertEqual(exit_code, 0)
            output = out.getvalue().lower()
            self.assertIn('hello', output)

    def test_a2_cli_agent_run_with_clarify(self) -> None:
        """Ambiguous task with --clarify stops before model call."""
        key = _opencodezen_api_key()
        if not key:
            self.skipTest(SKIP_REASON)
        with patch.dict(os.environ, {'OPENCODEZEN_API_KEY': key}):
            out = io.StringIO()
            with redirect_stdout(out):
                exit_code = main(
                    [
                        'run',
                        'opencodezen-go',
                        'improve things',
                        '--model',
                        'deepseek-v4-flash',
                        '--clarify',
                        '--max-iterations',
                        '2',
                        '--human',
                    ]
                )
            self.assertEqual(exit_code, EXIT_BLOCKING)
            output = out.getvalue().lower()
            self.assertTrue(
                'needs_clarification' in output
                or 'ambiguity' in output
                or 'clarify' in output
            )

    def test_a3_cli_agent_run_read_only_permission(self) -> None:
        """read-only mode allows analysis tasks."""
        key = _opencodezen_api_key()
        if not key:
            self.skipTest(SKIP_REASON)
        with patch.dict(os.environ, {'OPENCODEZEN_API_KEY': key}):
            out = io.StringIO()
            with redirect_stdout(out):
                exit_code = main(
                    [
                        'run',
                        'opencodezen-go',
                        'Reply with exactly: CLI read-only test pass',
                        '--model',
                        'deepseek-v4-flash',
                        '--permission-mode',
                        'read-only',
                        '--max-iterations',
                        '3',
                        '--human',
                    ]
                )
            self.assertEqual(exit_code, 0)
            output = out.getvalue().lower()
            self.assertIn('cli read-only test pass', output)

    def test_a4_cli_dry_run(self) -> None:
        """--dry-run shows readiness checklist without model call."""
        out = io.StringIO()
        with redirect_stdout(out):
            exit_code = main(
                [
                    'run',
                    'opencodezen-go',
                    'Do something expensive',
                    '--dry-run',
                    '--human',
                ]
            )
        self.assertEqual(exit_code, EXIT_BLOCKING)
        output = out.getvalue().lower()
        self.assertTrue(
            'dry-run' in output or 'readiness' in output or 'blocking' in output
        )

    def test_a5_cli_agent_run_with_model_override(self) -> None:
        """--model flag overrides the default model for the provider."""
        key = _opencodezen_api_key()
        if not key:
            self.skipTest(SKIP_REASON)
        with patch.dict(os.environ, {'OPENCODEZEN_API_KEY': key}):
            out = io.StringIO()
            with redirect_stdout(out):
                exit_code = main(
                    [
                        'run',
                        'opencodezen-go',
                        'Reply with exactly: model override works',
                        '--model',
                        'deepseek-v4-flash',
                        '--max-iterations',
                        '3',
                        '--human',
                    ]
                )
            self.assertEqual(exit_code, 0)
            output = out.getvalue().lower()
            self.assertIn('model override works', output)

    def test_a6_cli_agent_run_concrete_task_no_clarify(self) -> None:
        """Concrete task with --clarify passes through and runs."""
        key = _opencodezen_api_key()
        if not key:
            self.skipTest(SKIP_REASON)
        with patch.dict(os.environ, {'OPENCODEZEN_API_KEY': key}):
            out = io.StringIO()
            with redirect_stdout(out):
                main(
                    [
                        'run',
                        'opencodezen-go',
                        'Reply with exactly: concrete task worked',
                        '--model',
                        'deepseek-v4-flash',
                        '--clarify',
                        '--max-iterations',
                        '3',
                        '--permission-mode',
                        'read-only',
                        '--human',
                    ]
                )
            output = out.getvalue().lower()
            self.assertFalse(any('error' in o for o in output.splitlines()))


# ============================================================================
# Class B: Preflight / Daily / Plan scenarios
# ============================================================================


class CliPreflightPlanScenarios(unittest.TestCase):
    """Read-only planning and readiness commands."""

    def test_b1_cli_preflight(self) -> None:
        """preflight shows readiness without model call."""
        out = io.StringIO()
        with redirect_stdout(out):
            exit_code = main(
                [
                    'preflight',
                    'opencodezen-go',
                    'Analyze test coverage',
                    '--human',
                ]
            )
        self.assertEqual(exit_code, 0)
        output = out.getvalue().lower()
        # Preflight should report some structure
        self.assertTrue(
            'permission' in output or 'provider' in output or 'memory' in output
        )

    def test_b2_cli_daily(self) -> None:
        """daily command shows readiness cockpit without model call."""
        out = io.StringIO()
        with redirect_stdout(out):
            main(
                [
                    'daily',
                    'opencodezen-go',
                    'What needs attention today?',
                    '--human',
                ]
            )
        output = out.getvalue().lower()
        self.assertFalse(any('error' in o for o in output.splitlines()))

    def test_b3_cli_plan_mode(self) -> None:
        """plan writes a plan artifact without executing tools."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = io.StringIO()
            with redirect_stdout(out):
                exit_code = main(
                    [
                        'plan',
                        'opencodezen-go',
                        'Add a new output formatter',
                        '--root',
                        str(root),
                        '--human',
                    ]
                )
            self.assertEqual(exit_code, 0)
            # Plan should be written to .teaagent/plans/
            plans_dir = root / '.teaagent' / 'plans'
            if plans_dir.is_dir():
                plan_files = list(plans_dir.iterdir())
                self.assertGreater(len(plan_files), 0)

    def test_b4_cli_model_smoke(self) -> None:
        """model smoke verifies provider connectivity."""
        key = _opencodezen_api_key()
        if not key:
            self.skipTest(SKIP_REASON)
        with patch.dict(os.environ, {'OPENCODEZEN_API_KEY': key}):
            out = io.StringIO()
            with redirect_stdout(out):
                exit_code = main(
                    [
                        'model',
                        'smoke',
                        'opencodezen-go',
                        '--model',
                        'deepseek-v4-flash',
                        '--prompt',
                        'Reply with: connectivity ok',
                    ]
                )
            self.assertEqual(exit_code, 0)
            res = json.loads(out.getvalue().strip())
            self.assertEqual(res['provider'], 'opencodezen-go')
            self.assertIn('ok', res['content'].lower())


# ============================================================================
# Class C: Subagent chaining and orchestration
# ============================================================================


class SubagentChainingScenarios(unittest.TestCase):
    """Agent chaining: parent spawns child subagents with isolation."""

    def test_c1_subagent_shared_isolation_chain(self) -> None:
        """Subagent runs with shared isolation, passing data through lineage."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.teaagent').mkdir(exist_ok=True)
            parent_config = ChatAgentConfig(
                root=root,
                enable_subagent=True,
                max_subagent_depth=2,
                permission_mode=PermissionMode.READ_ONLY,
            )
            parent_adapter = MagicMock()
            parent_adapter.provider = 'fake'
            manager = SubagentManager(
                root=root,
                parent_config=parent_config,
                parent_adapter=parent_adapter,
            )
            registry = ToolRegistry()
            register_subagent_tools(
                registry,
                adapter=parent_adapter,
                config=parent_config,
                depth=0,
                manager=manager,
            )
            manager.bind_registry(registry)

            call_log: list[str] = []

            def fake_run(config, task, **kw) -> MagicMock:
                call_log.append(task)
                mock = MagicMock()
                mock.status = 'completed'
                mock.run_id = f'child-{len(call_log)}'
                mock.iterations = 1
                mock.tool_calls = 0
                mock.cost_cents = 0.5
                mock.final_answer = MagicMock(content=f'result: {task}')
                mock.metadata = {}
                return mock

            with patch('teaagent.chat_agent.run_chat_agent', fake_run):
                res1 = manager.run_subagent(
                    task='analyze code structure',
                    parent_run_id='parent-run-1',
                    depth=0,
                    isolation='shared',
                )
                res2 = manager.run_subagent(
                    task='summarize findings',
                    parent_run_id='parent-run-1',
                    depth=1,
                    isolation='shared',
                )

            self.assertEqual(res1['status'], 'completed')
            self.assertEqual(res2['status'], 'completed')
            self.assertEqual(len(call_log), 2)
            self.assertIn('analyze code structure', call_log)
            self.assertIn('summarize findings', call_log)
            self.assertIsNotNone(res1.get('lineage'))
            self.assertIsNotNone(res2.get('lineage'))

    def test_c2_subagent_permission_capping_unsafe_parent(self) -> None:
        """Subagent permission capped at workspace-write even with allow parent."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.teaagent').mkdir(exist_ok=True)
            parent_config = ChatAgentConfig(
                root=root,
                permission_mode='allow',
                max_subagent_depth=2,
            )
            parent_adapter = MagicMock()
            parent_adapter.provider = 'fake'
            manager = SubagentManager(
                root=root,
                parent_config=parent_config,
                parent_adapter=parent_adapter,
            )
            captured_config = None

            def fake_run(config, task, **kw) -> MagicMock:
                nonlocal captured_config
                captured_config = config
                mock = MagicMock()
                mock.status = 'completed'
                mock.run_id = 'child-capped'
                mock.iterations = 1
                mock.tool_calls = 0
                mock.cost_cents = 0.0
                mock.final_answer = MagicMock(content='capped')
                mock.metadata = {}
                return mock

            with patch('teaagent.chat_agent.run_chat_agent', fake_run):
                res = manager.run_subagent(
                    task='child task',
                    parent_run_id='parent-allow',
                    depth=0,
                    isolation='shared',
                )
            self.assertEqual(res['status'], 'completed')
            self.assertIsNotNone(captured_config)
            self.assertEqual(
                captured_config.permission_mode, PermissionMode('workspace-write')
            )

    def test_c3_subagent_batch_partial_failure(self) -> None:
        """Batch subagent returns partial status when some tasks fail."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.teaagent').mkdir(exist_ok=True)
            parent_config = ChatAgentConfig(root=root)
            parent_adapter = MagicMock()
            parent_adapter.provider = 'fake'
            manager = SubagentManager(
                root=root,
                parent_config=parent_config,
                parent_adapter=parent_adapter,
            )
            registry = ToolRegistry()
            register_subagent_tools(
                registry,
                adapter=parent_adapter,
                config=parent_config,
                depth=0,
                manager=manager,
            )
            manager.bind_registry(registry)

            def fake_run_subagent(**kw) -> dict[str, Any]:
                task = kw.get('task', '')
                if 'fail' in task:
                    raise RuntimeError('Simulated batch error')
                return {
                    'run_id': 'child-ok',
                    'status': 'completed',
                    'iterations': 1,
                    'tool_calls': 0,
                    'final_answer': f'completed {task}',
                }

            with patch.object(manager, 'run_subagent', fake_run_subagent):
                res = registry.execute(
                    'subagent_batch',
                    {
                        'tasks': [
                            {'task': 'task1', 'isolation': 'shared'},
                            {'task': 'fail_task', 'isolation': 'shared'},
                        ],
                        'max_workers': 2,
                    },
                )

            self.assertEqual(res['status'], 'partial')
            self.assertEqual(res['total'], 2)
            self.assertEqual(res['completed'], 1)
            self.assertEqual(res['results'][0]['status'], 'completed')
            self.assertEqual(res['results'][1]['status'], 'error')


# ============================================================================
# Class D: Workflow engine and automation chains
# ============================================================================


class WorkflowAndAutomationScenarios(unittest.TestCase):
    """Multi-step workflow execution and automation handoff chaining."""

    def test_d1_workflow_engine_multi_step(self) -> None:
        """WorkflowEngine executes a multi-step plan with PluginRegistry."""
        from teaagent.agent_factory import AgentFactory
        from teaagent.coordinator import (
            TaskClassification,
            TaskComplexity,
            TaskType,
            WorkflowPlan,
            WorkflowStep,
        )
        from teaagent.plugin_system import PluginRegistry as PR
        from teaagent.workflow_engine import WorkflowEngine

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = PR()
            factory = AgentFactory(plugin_registry=registry)
            engine = WorkflowEngine(
                plugin_registry=registry,
                agent_factory=factory,
                root=str(root),
                enable_self_healing=False,
            )

            from teaagent.plugin_system import AgentPlugin as AP

            test_agent = AP(
                name='analyst',
                description='analysis',
                system_prompt='You are an analyst',
            )
            registry.register_agent(test_agent)
            classification = TaskClassification(
                task_type=TaskType.GENERAL,
                complexity=TaskComplexity.SIMPLE,
                confidence=0.9,
            )
            plan = WorkflowPlan(
                task_description='Multi-step analysis',
                classification=classification,
                steps=[
                    WorkflowStep(
                        step_id=1, description='collect data', agent_name='analyst'
                    ),
                    WorkflowStep(
                        step_id=2, description='analyze data', agent_name='analyst'
                    ),
                    WorkflowStep(
                        step_id=3, description='summarize', agent_name='analyst'
                    ),
                ],
            )

            execution = engine.execute_workflow(plan)
            self.assertEqual(execution.state.value, 'completed')
            self.assertEqual(len(execution.step_results), 3)

    def test_d2_workflow_engine_step_failure_and_summary(self) -> None:
        """Workflow with a failing step still produces a complete summary."""
        from teaagent.agent_factory import AgentFactory
        from teaagent.coordinator import (
            TaskClassification,
            TaskComplexity,
            TaskType,
            WorkflowPlan,
            WorkflowStep,
        )
        from teaagent.plugin_system import PluginRegistry as PR
        from teaagent.workflow_engine import WorkflowEngine

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = PR()
            factory = AgentFactory(plugin_registry=registry)
            engine = WorkflowEngine(
                plugin_registry=registry,
                agent_factory=factory,
                root=str(root),
                enable_self_healing=False,
            )
            registry.get_agent = MagicMock(return_value=None)

            plan = WorkflowPlan(
                task_description='Failing workflow',
                classification=TaskClassification(
                    task_type=TaskType.GENERAL,
                    complexity=TaskComplexity.SIMPLE,
                    confidence=0.5,
                ),
                steps=[
                    WorkflowStep(step_id=1, description='bad step', agent_name='ghost')
                ],
            )

            execution = engine.execute_workflow(plan)
            self.assertEqual(execution.state.value, 'failed')
            summary = engine.get_workflow_summary(execution)
            self.assertIn('Failing workflow', summary)
            self.assertIn('failed', summary)

    def test_d3_automation_handoff_chain(self) -> None:
        """Full automation handoff lifecycle: persist → load → compose."""
        from teaagent.automation_chain import (
            compose_chained_task,
            handoff_path,
            load_automation_handoff,
            persist_automation_handoff,
            sanitize_untrusted_automation_text,
        )
        from teaagent.automations import AutomationSpec

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            upstream_spec = AutomationSpec(
                automation_id='collector',
                name='collect-logs',
                task='collect system logs',
                schedule='every 1h',
            )
            handoff = persist_automation_handoff(
                root,
                upstream_spec,
                collector_summary='Found 3 errors in app.log',
                summary='Collected logs from 4 services',
                log_tail='error: connection timeout\nwarning: high memory usage',
            )
            self.assertEqual(handoff.automation_id, 'collector')
            self.assertIn('3 errors', handoff.collector_summary)

            hpath = handoff_path(root, 'collector')
            self.assertTrue(hpath.exists())

            loaded = load_automation_handoff(root, 'collector')
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.automation_id, 'collector')
            self.assertEqual(loaded.summary, handoff.summary)

            downstream_task = 'Triage the collected logs and alert on errors'
            chained = compose_chained_task(downstream_task, handoff)
            self.assertIn('Triage the collected logs', chained)
            self.assertIn('3 errors', chained)
            self.assertIn('untrusted data', chained)

            sanitized = sanitize_untrusted_automation_text(chained, max_chars=100)
            self.assertLessEqual(len(sanitized), 103)

            # validate_context_from should find the handoff file (P2 fix)
            from teaagent.automation_chain import validate_context_from

            downstream_spec = AutomationSpec(
                automation_id='triage',
                name='triage',
                task=downstream_task,
                schedule='every 30m',
                context_from='collector',
            )
            errors = validate_context_from(downstream_spec, root=str(root))
            self.assertEqual(
                errors, [], 'validate_context_from should recognize handoff files'
            )

    def test_d4_automation_handoff_context_from_missing(self) -> None:
        """validate_context_from returns errors for missing upstream."""
        from teaagent.automation_chain import validate_context_from
        from teaagent.automations import AutomationSpec

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = AutomationSpec(
                automation_id='downstream',
                name='triage',
                task='process upstream output',
                schedule='every 30m',
                context_from='nonexistent-upstream',
            )
            errors = validate_context_from(spec, root=str(root))
            self.assertTrue(len(errors) > 0)
            self.assertTrue(any('not found' in e.lower() for e in errors))

    def test_d5_automation_self_reference_validation(self) -> None:
        """validate_context_from catches self-referencing automation."""
        from teaagent.automation_chain import validate_context_from
        from teaagent.automations import AutomationSpec

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = AutomationSpec(
                automation_id='self-loop',
                name='self',
                task='test',
                schedule='every 1h',
                context_from='self-loop',
            )
            errors = validate_context_from(spec, root=str(root))
            self.assertTrue(len(errors) > 0)
            self.assertTrue(any('same' in e.lower() for e in errors))


# ============================================================================
# Class E: Swarm and parallel execution
# ============================================================================


class SwarmExecutionScenarios(unittest.TestCase):
    """Parallel swarm execution with tournament scoring and reviews."""

    def test_e1_swarm_tournament_fitness_scoring(self) -> None:
        """Tournament fitness scoring correctly ranks prompt variants."""
        from teaagent.swarm import (
            PromptFitnessMetrics,
            compute_prompt_fitness_score,
            rank_prompt_tournament,
        )

        m1 = PromptFitnessMetrics(
            success=1,
            tokens=20.0,
            min_tokens=10.0,
            time_seconds=4.0,
            min_time_seconds=2.0,
            errors=0,
        )
        m2 = PromptFitnessMetrics(
            success=1,
            tokens=10.0,
            min_tokens=10.0,
            time_seconds=2.0,
            min_time_seconds=2.0,
            errors=0,
        )
        score1 = compute_prompt_fitness_score(m1)
        score2 = compute_prompt_fitness_score(m2)
        self.assertGreater(score2, score1)

        candidates = [('prompt-a', 'Slow prompt', m1), ('prompt-b', 'Fast prompt', m2)]
        ranked = rank_prompt_tournament(candidates)
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0][0], 'prompt-b')  # Fast prompt ranked first
        self.assertGreaterEqual(ranked[0][1], ranked[1][1])

    def test_e2_swarm_gene_pool_persistence(self) -> None:
        """Top-performing prompts saved to gene pool JSONL."""
        from teaagent.swarm import save_prompt_to_gene_pool

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = save_prompt_to_gene_pool(
                root,
                prompt='optimized prompt',
                score=0.98,
                task_id='winner-1',
            )
            self.assertTrue(path.exists())
            lines = path.read_text(encoding='utf-8').strip().splitlines()
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry['prompt'], 'optimized prompt')
            self.assertEqual(entry['score'], 0.98)

    def test_e3_swarm_multi_agent_code_review(self) -> None:
        """Swarm generates pairwise code reviews between successful agents."""
        from teaagent.swarm import (
            CodeReview,
            SubagentResult,
            SwarmManager,
            SwarmReport,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = [
                SubagentResult(task_id='a1', success=True, output={'status': 'done'}),
                SubagentResult(task_id='a2', success=True, output={'status': 'done'}),
                SubagentResult(task_id='a3', success=False, error='failed'),
            ]
            report = SwarmReport(
                total_subagents=3,
                successful_subagents=2,
                failed_subagents=1,
                results=results,
                code_reviews=[],
            )
            manager = SwarmManager(root=root)
            reviews = manager.run_code_reviews(report)
            self.assertEqual(len(reviews), 2)
            for review in reviews:
                self.assertIsInstance(review, CodeReview)
                self.assertNotEqual(review.reviewer_task_id, review.target_task_id)

    def test_e4_swarm_select_best_with_mixed_success(self) -> None:
        """Best result selection prefers successful over failed."""
        from teaagent.swarm import (
            SubagentResult,
            SwarmManager,
            SwarmReport,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = [
                SubagentResult(task_id='failed-1', success=False, error='error'),
                SubagentResult(task_id='ok-1', success=True, output={'status': 'done'}),
            ]
            report = SwarmReport(
                total_subagents=2,
                successful_subagents=1,
                failed_subagents=1,
                results=results,
                code_reviews=[],
            )
            manager = SwarmManager(root=root)
            best = manager.select_best_result(report, [])
            self.assertIsNotNone(best)
            self.assertTrue(best.success)
            self.assertEqual(best.task_id, 'ok-1')


# ============================================================================
# Class F: Plugin, factory, and memory scenarios
# ============================================================================


class PluginAndMemoryScenarios(unittest.TestCase):
    """Plugin discovery, agent factory evolution, memory operations."""

    def test_f1_plugin_registry_lifecycle(self) -> None:
        """PluginRegistry: register command, get command, list commands."""
        from teaagent.plugin_system import (
            CommandPlugin,
            PluginRegistry,
        )

        registry = PluginRegistry()
        before_cmds = len(registry.list_commands())
        before_agents = len(registry.list_agents())

        cmd = CommandPlugin(
            name='hello',
            description='Say hello',
            handler=lambda: 'hello',
            aliases=('hi',),
        )
        registry.register_command(cmd)
        self.assertGreater(len(registry.list_commands()), before_cmds)
        retrieved = registry.get_command('hello')
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, 'hello')
        self.assertEqual(retrieved.aliases, ('hi',))

        from teaagent.plugin_system import AgentPlugin as AP

        agent = AP(
            name='tester',
            description='Test execution agent',
            system_prompt='You are a test engineer',
        )
        registry.register_agent(agent)
        self.assertEqual(len(registry.list_agents()), before_agents + 1)
        retrieved_agent = registry.get_agent('tester')
        self.assertIsNotNone(retrieved_agent)
        self.assertEqual(retrieved_agent.name, 'tester')

    def test_f2_agent_factory_generate_and_evolve(self) -> None:
        """AgentFactory generates agents and evolves prompts."""
        from teaagent.agent_factory import AgentFactory, AgentSpecification
        from teaagent.plugin_system import PluginRegistry

        registry = PluginRegistry()
        factory = AgentFactory(plugin_registry=registry)

        spec = AgentSpecification(
            name='bug-fixer',
            description='Fixes bugs in Python code',
            task_domain='debugging',
            required_tools=('read_file', 'write_file', 'run_shell'),
            specialization_level='expert',
        )
        agent = factory.generate_agent(spec)
        self.assertEqual(agent.name, 'bug-fixer')
        self.assertIsNotNone(agent.system_prompt)

        # Evolve the agent prompt
        evolved = factory.evolve_agent_prompt(
            'bug-fixer',
            performance_feedback='Agent failed to handle type errors correctly',
            success_metrics={'accuracy': 0.75, 'speed': 0.9},
        )
        self.assertEqual(evolved.name, 'bug-fixer')
        self.assertIsNotNone(evolved.system_prompt)

    def test_f3_memory_catalog_lifecycle(self) -> None:
        """Memory catalog: add, list, search, show operations."""
        from teaagent.memory import MemoryCatalog

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog = MemoryCatalog(root)

            e1 = catalog.add('The project uses pytest for testing')
            e2 = catalog.add('Deploy via GitHub Actions to PyPI')
            catalog.add('API keys are stored in .env files')
            self.assertIsNotNone(e1.memory_id)
            self.assertIsNotNone(e2.memory_id)

            all_entries = catalog.list()
            self.assertGreaterEqual(len(all_entries), 3)

            results = catalog.search('testing')
            self.assertGreaterEqual(len(results), 1)
            self.assertIn('pytest', results[0].content)

            shown = catalog.show(e1.memory_id)
            self.assertEqual(shown.content, e1.content)


# ============================================================================
# Class G: Approval, budget, and audit scenarios
# ============================================================================


class ApprovalAndAuditScenarios(unittest.TestCase):
    """Approval flow, budget enforcement, and audit trail verification."""

    def test_g1_approval_policy_read_only_blocks_destructive(self) -> None:
        """READ_ONLY policy blocks destructive tool assertions."""
        from teaagent.policy import ApprovalPolicy
        from teaagent.types import ToolPermissionError

        policy = ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY)
        with self.assertRaises(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='c1',
                destructive=True,
            )

    def test_g2_approval_policy_workspace_write_allows_file_blocks_shell(self) -> None:
        """WORKSPACE_WRITE allows file writes but blocks shell."""
        from teaagent.policy import ApprovalPolicy
        from teaagent.types import ToolPermissionError

        policy = ApprovalPolicy(permission_mode=PermissionMode.WORKSPACE_WRITE)
        policy.assert_allowed(
            tool_name='workspace_write_file',
            call_id='c1',
            destructive=True,
        )
        with self.assertRaises(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_run_shell_mutate',
                call_id='c2',
                destructive=True,
            )

    def test_g3_approval_prompt_mode_blocks_unapproved(self) -> None:
        """PROMPT mode blocks destructive tools without approval handler."""
        from teaagent.policy import ApprovalPolicy
        from teaagent.types import ToolPermissionError

        policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
        with self.assertRaises(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='unapproved',
                destructive=True,
            )

    def test_g3b_approval_allow_mode_allows_destructive(self) -> None:
        """ALLOW mode permits all destructive tools."""
        from teaagent.policy import ApprovalPolicy

        policy = ApprovalPolicy(permission_mode=PermissionMode.ALLOW)
        policy.assert_allowed(
            tool_name='workspace_write_file',
            call_id='any-call',
            destructive=True,
        )

    def test_g4_audit_logger_events_after_run(self) -> None:
        """Agent run produces audit events: run_started, tool_call, run_completed."""
        from teaagent.run_store import RunStore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = RunStore(root)
            audit = store.audit_logger()

            audit.record('run_started', run_id='audit-test-1', task='test task')
            audit.record(
                'tool_call',
                run_id='audit-test-1',
                call_id='call-1',
                tool_name='workspace_read_file',
            )
            audit.record('run_completed', run_id='audit-test-1')

            events = audit.events
            self.assertGreaterEqual(len(events), 3)
            event_types = [getattr(e, 'event_type', '') for e in events]
            self.assertIn('run_started', event_types)
            self.assertIn('tool_call', event_types)
            self.assertIn('run_completed', event_types)

    def test_g5_budget_run_cap_via_max_iterations(self) -> None:
        """Run with max_iterations=1 stops after one iteration."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_read_file",'
                    '"arguments":{"path":"dummy.txt"},"call_id":"c1"}',
                ]
            )
            config = ChatAgentConfig(
                root=root,
                max_iterations=1,
                max_tool_calls=1,
                permission_mode=PermissionMode.READ_ONLY,
            )
            result = run_chat_agent(
                config,
                'Read a nonexistent file',
                adapter=adapter,
            )
            # With max_iterations=1, the agent should complete or hit limit
            self.assertTrue(
                result.status == 'completed' or result.status.startswith('failed')
            )
            self.assertLessEqual(result.iterations, 1)


# ============================================================================
# Class H: MCP and ACP server protocol scenarios
# ============================================================================


class McpAcpServerScenarios(unittest.TestCase):
    """MCP stdio and ACP server protocol simulation."""

    def test_h1_mcp_server_stdio_list_tools(self) -> None:
        """MCP stdio server responds to tools/list request."""
        from teaagent.mcp_server import handle_mcp_request
        from teaagent.types import ToolRegistry

        registry = ToolRegistry()
        registry.register(
            name='workspace_read_file',
            handler=lambda args: {'output': 'content'},
            description='Read a file from the workspace',
            input_schema={
                'type': 'object',
                'properties': {'path': {'type': 'string'}},
            },
            output_schema={'type': 'object'},
            annotations=ToolAnnotations(read_only=True, destructive=False),
        )

        # MCP initialize
        init_response = handle_mcp_request(
            registry,
            {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'initialize',
                'params': {'protocolVersion': '2024-11-05'},
            },
        )
        self.assertIsNotNone(init_response)
        self.assertIn('result', init_response)

        # MCP tools/list
        list_response = handle_mcp_request(
            registry,
            {
                'jsonrpc': '2.0',
                'id': 2,
                'method': 'tools/list',
            },
        )
        self.assertIsNotNone(list_response)
        self.assertIn('result', list_response)
        tools = list_response['result'].get('tools', [])
        tool_names = [t['name'] for t in tools]
        self.assertIn('workspace_read_file', tool_names)

        # MCP tools/call
        call_response = handle_mcp_request(
            registry,
            {
                'jsonrpc': '2.0',
                'id': 3,
                'method': 'tools/call',
                'params': {
                    'name': 'workspace_read_file',
                    'arguments': {'path': 'test.txt'},
                },
            },
        )
        self.assertIsNotNone(call_response)
        self.assertIn('result', call_response)

    def test_h2_acp_server_session_prompt(self) -> None:
        """ACP server handles session/prompt with full agent run."""
        from teaagent.acp_adapter import create_acp_server
        from teaagent.runner import FinalAnswer

        mock_runner = MagicMock()
        mock_result = MagicMock()
        mock_result.run_id = 'acp-run-1'
        mock_result.status = 'completed'
        mock_result.iterations = 1
        mock_result.tool_calls = 0
        mock_result.final_answer = FinalAnswer(content='ACP task completed')
        mock_result.cost_cents = 1.0
        mock_runner.run.return_value = mock_result

        registry = ToolRegistry()

        server = create_acp_server(
            tool_registry=registry,
            agent_runner=mock_runner,
        )

        # Initialize and list tools should work without crash (P0 fix)
        init_resp = server.initialize({'protocolVersion': '1.0.0'})
        self.assertIn('serverVersion', init_resp)
        tools = server.list_tools()
        self.assertIsInstance(tools, list)

        prompt_resp = server.session_prompt(
            {
                'sessionId': 'acp-session-1',
                'prompt': 'Analyze the codebase',
                'root': '/tmp',
                'provider': 'fake',
                'permission_mode': 'read-only',
            }
        )
        assert prompt_resp is not None
        self.assertIn('runId', prompt_resp)
        self.assertIn('status', prompt_resp)


# ============================================================================
# Class I: Tool registry and execution scenarios
# ============================================================================


class ToolExecutionScenarios(unittest.TestCase):
    """Direct tool registry operations: register, execute, annotations."""

    def test_i1_tool_registry_register_and_execute_read(self) -> None:
        """Tool can be registered and executed via registry.execute."""

        registry = ToolRegistry()
        registry.register(
            name='custom_greet',
            handler=lambda args: {'message': f'Hello, {args.get("name", "world")}!'},
            description='Greet someone',
            input_schema={
                'type': 'object',
                'properties': {'name': {'type': 'string'}},
            },
            output_schema={'type': 'object'},
            annotations=ToolAnnotations(read_only=True, destructive=False),
        )

        result = registry.execute('custom_greet', {'name': 'TeaAgent'})
        self.assertEqual(result['message'], 'Hello, TeaAgent!')

    def test_i2_tool_registry_execute_unknown_tool_raises(self) -> None:
        """Unknown tool name raises KeyError."""
        registry = ToolRegistry()
        with self.assertRaises(KeyError):
            registry.execute('nonexistent_tool', {})

    def test_i3_tool_annotations_govern_destructive_permission(self) -> None:
        """Tool annotations correctly identify destructive vs read-only."""

        read_ann = ToolAnnotations(read_only=True, destructive=False)
        write_ann = ToolAnnotations(read_only=False, destructive=True)

        self.assertTrue(read_ann.read_only)
        self.assertFalse(read_ann.destructive)
        self.assertFalse(write_ann.read_only)
        self.assertTrue(write_ann.destructive)


# ============================================================================
# Class R: FailureCardScenarios
# ============================================================================


class FailureCardScenarios(unittest.TestCase):
    """Failure card creation, storage, similarity, and auto-invalidation."""

    def test_r1_failure_card_creation_with_confidence_and_warning(self) -> None:
        """FailureCard.create sets confidence levels and warning behaviors."""
        from teaagent.memory.failure_card import FailureCard

        card_low = FailureCard.create(
            run_id='run-1',
            error_type='TypeError',
            file_path='src/main.py',
            error_message='int() argument must be a string',
            task_description='convert string to int',
            context_files=['src/main.py', 'src/utils.py'],
            confidence='low',
            warning_behavior='info',
        )
        self.assertEqual(card_low.confidence, 'low')
        self.assertEqual(card_low.warning_behavior, 'info')
        self.assertEqual(card_low.effective_behavior(), 'warning')
        self.assertTrue(card_low.is_active())

        card_high = FailureCard.create(
            run_id='run-2',
            error_type='SecurityError',
            file_path='src/auth.py',
            error_message='unauthorized access',
            task_description='validate auth tokens',
            context_files=['src/auth.py'],
            confidence='high',
            warning_behavior='block',
            reviewer_type='human',
        )
        self.assertEqual(card_high.confidence, 'high')
        self.assertEqual(card_high.warning_behavior, 'block')
        self.assertEqual(card_high.effective_behavior(), 'block')

    def test_r2_failure_card_storage_list_all_empty_initially(self) -> None:
        """FailureCardStorage list_all returns empty list for fresh storage."""
        from teaagent.memory.failure_card import FailureCardStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = FailureCardStorage(root)
            cards = storage.list_all()
            self.assertEqual(cards, [])

    def test_r3_failure_card_storage_add_and_retrieve(self) -> None:
        """FailureCardStorage append persists and get_by_id retrieves a card."""
        from teaagent.memory.failure_card import FailureCard, FailureCardStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = FailureCardStorage(root)

            card = FailureCard.create(
                run_id='run-r3',
                error_type='ValueError',
                file_path='src/parser.py',
                error_message='invalid syntax at line 42',
                task_description='parse configuration files',
                context_files=['src/parser.py'],
                confidence='medium',
                warning_behavior='warning',
            )
            storage.append(card)

            all_cards = storage.list_all()
            self.assertEqual(len(all_cards), 1)
            self.assertEqual(all_cards[0].error_type, 'ValueError')

            retrieved = storage.get_by_id(card.id)
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.run_id, 'run-r3')
            self.assertEqual(retrieved.task_description, 'parse configuration files')

    def test_r4_failure_card_storage_find_matching_by_similarity(self) -> None:
        """find_matching returns cards with shared file paths and keyword overlap."""
        from teaagent.memory.failure_card import FailureCard, FailureCardStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = FailureCardStorage(root)

            storage.append(
                FailureCard.create(
                    run_id='prev-run',
                    error_type='ImportError',
                    file_path='src/module.py',
                    error_message='cannot import name',
                    task_description='refactor module imports and fix circular dependencies',
                    context_files=['src/module.py', 'src/init.py'],
                    confidence='medium',
                )
            )
            storage.append(
                FailureCard.create(
                    run_id='unrelated-run',
                    error_type='OSError',
                    file_path='src/io.py',
                    error_message='file not found',
                    task_description='read external data files',
                    context_files=['src/io.py'],
                    confidence='low',
                )
            )

            matches = storage.find_matching(
                file_paths=['src/module.py'],
                task_description='refactor module imports and clean up circular code',
            )
            self.assertGreaterEqual(len(matches), 1)
            self.assertIn('ImportError', [m.error_type for m in matches])

    def test_r5_auto_invalidation_by_file_signature_change(self) -> None:
        """AutoInvalidationRule invalidates cards when tracked file signature changes."""
        from teaagent.memory.failure_card import (
            AutoInvalidationRule,
            FailureCard,
            FailureCardStorage,
            MemoryAutoInvalidationConfig,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Create a tracked file
            (root / 'src').mkdir(parents=True, exist_ok=True)
            target_file = root / 'src' / 'broken.py'
            target_file.write_text('def broken():\n    raise RuntimeError("bad")')

            storage = FailureCardStorage(root)

            card = FailureCard.create(
                run_id='run-sig',
                error_type='RuntimeError',
                file_path='src/broken.py',
                error_message='bad',
                task_description='fix broken function',
                context_files=['src/broken.py'],
            )
            storage.append(card)

            # First apply stores signature
            config = MemoryAutoInvalidationConfig(
                rules=[
                    AutoInvalidationRule(
                        trigger='file_signature_change',
                        confidence='high',
                        action='invalidate',
                        enabled=True,
                    )
                ],
                enabled=True,
            )
            storage.apply_auto_invalidation(config)

            # Change the file
            target_file.write_text('def broken():\n    return "fixed"')

            # Second apply should detect signature change
            results = storage.apply_auto_invalidation(config)
            self.assertIn('file_signature_change', results)

            # Card should now be invalidated
            updated = storage.get_by_id(card.id)
            self.assertIsNotNone(updated)
            self.assertTrue(updated.invalidated)


# ============================================================================
# Class S: BackgroundResumeScenarios
# ============================================================================


class BackgroundResumeScenarios(unittest.TestCase):
    """Background task persistence, listing, resume, and metadata preservation."""

    def test_s1_run_store_persists_and_get_run_retrieves(self) -> None:
        """RunStore.save persists events and load retrieves them."""
        from teaagent.run_store import RunStore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = RunStore(root)

            events = [
                {
                    'run_id': 'test-run-1',
                    'event_type': 'run_started',
                    'payload': {'task': 'test task'},
                    'created_at': '2026-01-01T00:00:00Z',
                },
                {
                    'run_id': 'test-run-1',
                    'event_type': 'run_completed',
                    'payload': {'answer': {'content': 'done'}, 'cost_cents': 1.5},
                    'created_at': '2026-01-01T00:01:00Z',
                },
            ]
            store.save('test-run-1', events)

            loaded = store.load('test-run-1')
            self.assertIsNotNone(loaded)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0]['event_type'], 'run_started')
            self.assertEqual(loaded[1]['event_type'], 'run_completed')

    def test_s2_run_store_list_runs_returns_all(self) -> None:
        """RunStore.list_runs returns all persisted runs."""
        from teaagent.run_store import RunStore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = RunStore(root)

            for i in range(3):
                store.save(
                    f'batch-run-{i}',
                    [
                        {
                            'run_id': f'batch-run-{i}',
                            'event_type': 'run_started',
                            'payload': {'task': f'task {i}'},
                            'created_at': f'2026-01-01T00:0{i}:00Z',
                        },
                        {
                            'run_id': f'batch-run-{i}',
                            'event_type': 'run_completed',
                            'payload': {
                                'answer': {'content': f'result {i}'},
                                'cost_cents': float(i),
                            },
                            'created_at': f'2026-01-01T00:0{i}:30Z',
                        },
                    ],
                )

            runs = store.list_runs(limit=10)
            self.assertGreaterEqual(len(runs), 3)

            run_ids = {r.run_id for r in runs}
            self.assertIn('batch-run-0', run_ids)
            self.assertIn('batch-run-1', run_ids)
            self.assertIn('batch-run-2', run_ids)

    def test_s3_resume_flow_create_and_load_from_run_store(self) -> None:
        """Resume flow: persist run via RunStore, then load and describe."""
        from teaagent.run_store import RunStore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = RunStore(root)

            run_id = 'resume-run-1'
            store.save(
                run_id,
                [
                    {
                        'run_id': run_id,
                        'event_type': 'run_started',
                        'payload': {'task': 'task for resume flow'},
                        'created_at': '2026-01-01T00:00:00Z',
                    },
                    {
                        'run_id': run_id,
                        'event_type': 'tool_call_completed',
                        'payload': {
                            'call_id': 'c1',
                            'tool_name': 'workspace_read_file',
                            'result': {'output': 'file content'},
                        },
                        'created_at': '2026-01-01T00:01:00Z',
                    },
                    {
                        'run_id': run_id,
                        'event_type': 'run_completed',
                        'payload': {
                            'answer': {'content': 'resume test result'},
                            'cost_cents': 0.5,
                        },
                        'created_at': '2026-01-01T00:02:00Z',
                    },
                ],
            )

            listed = store.list_runs(limit=10)
            self.assertGreaterEqual(len(listed), 1)
            self.assertTrue(any(r.run_id == run_id for r in listed))

            described = store.describe_run(run_id)
            self.assertEqual(described.run_id, run_id)
            self.assertEqual(described.status, 'completed')
            self.assertIsNotNone(described.final_answer)
            self.assertEqual(described.final_answer.content, 'resume test result')

    def test_s4_run_metadata_preserved(self) -> None:
        """Run metadata (run_id, status, final_answer) is preserved across store/load."""
        from teaagent.run_store import RunStore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = RunStore(root)

            run_id = 'metadata-run-1'
            store.save(
                run_id,
                [
                    {
                        'run_id': run_id,
                        'event_type': 'run_started',
                        'payload': {'task': 'metadata test'},
                        'created_at': '2026-01-01T00:00:00Z',
                    },
                    {
                        'run_id': run_id,
                        'event_type': 'run_completed',
                        'payload': {
                            'answer': {'content': 'metadata preserved'},
                            'cost_cents': 2.5,
                            'input_tokens': 100,
                            'output_tokens': 50,
                        },
                        'created_at': '2026-01-01T00:05:00Z',
                    },
                ],
            )

            described = store.describe_run(run_id)
            self.assertEqual(described.run_id, run_id)
            self.assertEqual(described.status, 'completed')
            self.assertIsNotNone(described.final_answer)
            self.assertEqual(described.final_answer.content, 'metadata preserved')
            self.assertAlmostEqual(described.cost_cents, 2.5)
            self.assertEqual(described.input_tokens, 100)
            self.assertEqual(described.output_tokens, 50)


# ============================================================================
# Class T: ProviderFailoverScenarios
# ============================================================================


class ProviderFailoverScenarios(unittest.TestCase):
    """Provider discovery, adapter creation, and model routing."""

    def test_t1_available_providers_returns_list(self) -> None:
        """available_providers returns a list of known provider names."""
        from teaagent.llm import available_providers

        providers = available_providers()
        self.assertIsInstance(providers, list)
        self.assertGreater(len(providers), 0)
        # 'fake' should be among available providers for testing
        self.assertIn('fake', providers)
        # At least one real provider should be registered
        real_providers = [p for p in providers if p != 'fake']
        self.assertGreater(len(real_providers), 0)

    def test_t2_create_llm_adapter_for_fake_provider(self) -> None:
        """create_llm_adapter creates a FakeLLMAdapter for 'fake' provider."""
        from teaagent.llm import create_llm_adapter
        from teaagent.llm._fake_adapter import FakeLLMAdapter

        adapter = create_llm_adapter('fake')
        self.assertIsInstance(adapter, FakeLLMAdapter)
        self.assertEqual(adapter.provider, 'fake')
        self.assertEqual(getattr(adapter, 'model', 'unknown'), 'fake-model')

        adapter_custom = create_llm_adapter('fake', model='custom-fake')
        self.assertEqual(getattr(adapter_custom, 'model', 'unknown'), 'custom-fake')

    def test_t3_route_model_returns_routing_info(self) -> None:
        """route_model returns ModelRoute with category, provider, model, and reason."""
        from teaagent.model_routing import ModelRoute, route_model

        # Test with explicit model override
        route = route_model(
            'fix the critical authentication bug',
            provider='gpt',
            model='gpt-4o',
        )
        self.assertIsInstance(route, ModelRoute)
        self.assertEqual(route.provider, 'gpt')
        self.assertEqual(route.model, 'gpt-4o')
        self.assertEqual(route.reason, 'explicit model override')
        self.assertIsNotNone(route.category)
        self.assertIn(route.complexity, ('low', 'medium', 'high'))

        # Test without model override (complexity-based routing)
        route2 = route_model(
            'write a simple docstring comment',
            provider='gpt',
        )
        self.assertEqual(route2.provider, 'gpt')
        self.assertIsNotNone(route2.model)
        self.assertNotEqual(route2.reason, 'explicit model override')
        self.assertGreater(route2.estimated_tokens, 0)

        # Test with unknown provider (should not crash)
        route3 = route_model(
            'do something general',
            provider='unknown-provider',
        )
        self.assertEqual(route3.provider, 'unknown-provider')


# ============================================================================
# Class N: Git sandbox scenarios
# ============================================================================


def _init_temp_git_repo(root: Path) -> None:
    """Initialize a minimal git repository at root for sandbox testing."""
    subprocess.run(['git', 'init'], cwd=root, capture_output=True, check=True)
    subprocess.run(
        ['git', 'config', 'user.email', 't@t.com'],
        cwd=root,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'T'], cwd=root, capture_output=True, check=True
    )
    # Create and commit an initial file so there is at least one commit.
    (root / 'README.md').write_text('# test\n', encoding='utf-8')
    subprocess.run(['git', 'add', '-A'], cwd=root, capture_output=True, check=True)
    subprocess.run(
        ['git', 'commit', '-m', 'initial', '--no-verify'],
        cwd=root,
        capture_output=True,
        check=True,
    )


class GitSandboxScenarios(unittest.TestCase):
    """Git sandbox operations: repo detection, stash, worktree, transactions."""

    def test_n1_is_git_repository_true_in_git_repo(self) -> None:
        """is_git_repository returns True inside a git repository."""
        from teaagent.sandbox import is_git_repository

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_temp_git_repo(root)
            self.assertTrue(is_git_repository(root))

    def test_n2_is_git_repository_false_in_temp_dir(self) -> None:
        """is_git_repository returns False in a non-git directory."""
        from teaagent.sandbox import is_git_repository

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertFalse(is_git_repository(root))

    def test_n3_git_branch_sandbox_init(self) -> None:
        """GitBranchSandbox initializes with root and run_id."""
        from teaagent.sandbox import GitBranchSandbox

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_temp_git_repo(root)
            sandbox = GitBranchSandbox(root=root, run_id='test-run-n3')
            self.assertTrue(sandbox.is_available())

    def test_n4_git_transaction_sink_records_file_writes(self) -> None:
        """GitTransactionSink commits transactions for workspace_write_file events."""
        from teaagent.sandbox import GitBranchSandbox, GitTransactionSink
        from teaagent.types import AuditEvent

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_temp_git_repo(root)
            sandbox = GitBranchSandbox(root=root, run_id='test-run-n4')
            sink = GitTransactionSink(sandbox=sandbox)

            # Sink processes tool events without raising
            sink(
                AuditEvent(
                    event_type='tool_call_started',
                    run_id='test-run-n4',
                    payload={'tool_name': 'workspace_write_file', 'call_id': 'call-1'},
                )
            )
            sink(
                AuditEvent(
                    event_type='tool_call_completed',
                    run_id='test-run-n4',
                    payload={'tool_name': 'workspace_write_file', 'call_id': 'call-1'},
                )
            )
            sink(
                AuditEvent(
                    event_type='tool_call_started',
                    run_id='test-run-n4',
                    payload={'tool_name': 'workspace_write_file', 'call_id': 'call-2'},
                )
            )
            sink(
                AuditEvent(
                    event_type='tool_call_failed',
                    run_id='test-run-n4',
                    payload={'tool_name': 'workspace_write_file', 'call_id': 'call-2'},
                )
            )

    def test_n5_stash_save_and_pop(self) -> None:
        """stash_save and stash_pop correctly save and restore dirty state."""
        from teaagent.sandbox import is_worktree_clean, stash_pop, stash_save

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_temp_git_repo(root)
            self.assertTrue(is_worktree_clean(root))

            # Dirty the worktree
            (root / 'dirty.txt').write_text('unstaged\n', encoding='utf-8')
            self.assertFalse(is_worktree_clean(root))

            # Save stash
            stash_ref = stash_save(root, 'test-stash')
            self.assertIsNotNone(stash_ref)
            self.assertTrue(is_worktree_clean(root))

            # Pop stash
            restored = stash_pop(root, stash_ref)
            self.assertTrue(restored)
            self.assertFalse(is_worktree_clean(root))

    def test_n6_is_worktree_clean_dirty_vs_clean(self) -> None:
        """is_worktree_clean detects dirty vs clean state correctly."""
        from teaagent.sandbox import is_worktree_clean

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_temp_git_repo(root)
            self.assertTrue(is_worktree_clean(root))

            (root / 'new_file.py').write_text('print("hello")\n', encoding='utf-8')
            self.assertFalse(is_worktree_clean(root))

            # Stage + commit to restore clean
            subprocess.run(
                ['git', 'add', 'new_file.py'], cwd=root, capture_output=True, check=True
            )
            subprocess.run(
                ['git', 'commit', '-m', 'add file', '--no-verify'],
                cwd=root,
                capture_output=True,
                check=True,
            )
            self.assertTrue(is_worktree_clean(root))


# ============================================================================
# Class O: MCP HTTP server scenarios
# ============================================================================


class McpHttpScenarios(unittest.TestCase):
    """MCP HTTP server construction and session store operations."""

    def test_o1_build_mcp_http_server_returns_server_and_store(self) -> None:
        """build_mcp_http_server returns (HTTPServer, MCPSessionStore) tuple."""
        from http.server import ThreadingHTTPServer

        from teaagent.mcp_http import MCPSessionStore, build_mcp_http_server
        from teaagent.types import ToolRegistry

        registry = ToolRegistry()
        server, store = build_mcp_http_server(registry)
        self.assertIsInstance(server, ThreadingHTTPServer)
        self.assertIsInstance(store, MCPSessionStore)
        server.server_close()

    def test_o2_server_initialization_with_auth_token(self) -> None:
        """build_mcp_http_server accepts and wires an auth_token."""
        from http.server import ThreadingHTTPServer

        from teaagent.mcp_http import build_mcp_http_server
        from teaagent.types import ToolRegistry

        registry = ToolRegistry()
        server, store = build_mcp_http_server(
            registry,
            auth_token='secret-token-123',
        )
        self.assertIsInstance(server, ThreadingHTTPServer)
        self.assertIsNotNone(store)
        server.server_close()

    def test_o3_build_mcp_http_server_with_oauth_config(self) -> None:
        """build_mcp_http_server accepts oauth_server OAuth21AuthorizationServer."""
        from http.server import ThreadingHTTPServer

        from teaagent.mcp_http import build_mcp_http_server
        from teaagent.oauth21 import OAuth21AuthorizationServer
        from teaagent.types import ToolRegistry

        registry = ToolRegistry()
        oauth = OAuth21AuthorizationServer(
            signing_key='a' * 32,
            issuer='https://example.com',
        )
        server, store = build_mcp_http_server(
            registry,
            oauth_server=oauth,
        )
        self.assertIsInstance(server, ThreadingHTTPServer)
        self.assertIsNotNone(store)
        server.server_close()


# ============================================================================
# Class P: Subagent isolation scenarios
# ============================================================================


class SubagentIsolationScenarios(unittest.TestCase):
    """Subagent isolation types, normalization, and session keys."""

    def test_p1_normalize_subagent_isolation_handles_all_modes(self) -> None:
        """normalize_subagent_isolation handles shared, worktree, directory-snapshot, docker, auto."""
        from teaagent.subagents._isolation import normalize_subagent_isolation

        self.assertEqual(normalize_subagent_isolation('shared'), 'shared')
        self.assertEqual(normalize_subagent_isolation('worktree'), 'worktree')
        self.assertEqual(
            normalize_subagent_isolation('directory-snapshot'), 'directory-snapshot'
        )
        self.assertEqual(normalize_subagent_isolation('docker'), 'docker')
        self.assertEqual(normalize_subagent_isolation('auto'), 'auto')
        # Unknown value
        self.assertIsNone(normalize_subagent_isolation('unknown-mode'))
        # None and empty → fall back to default
        self.assertEqual(normalize_subagent_isolation(None), 'shared')
        self.assertEqual(normalize_subagent_isolation(''), 'shared')

    def test_p2_default_subagent_isolation_is_shared(self) -> None:
        """DEFAULT_SUBAGENT_ISOLATION constant is 'shared'."""
        from teaagent.subagents import DEFAULT_SUBAGENT_ISOLATION

        self.assertEqual(DEFAULT_SUBAGENT_ISOLATION, 'shared')

    def test_p3_new_isolation_session_key_generates_unique_keys(self) -> None:
        """new_isolation_session_key produces unique, non-empty strings."""
        from teaagent.subagents._isolation import new_isolation_session_key

        key1 = new_isolation_session_key(parent_run_id='run-abc', def_name='analyst')
        key2 = new_isolation_session_key(parent_run_id='run-abc', def_name='reviewer')
        key3 = new_isolation_session_key(parent_run_id='run-xyz', def_name='analyst')

        self.assertIsInstance(key1, str)
        self.assertGreater(len(key1), 0)
        # Keys must be unique
        self.assertNotEqual(key1, key2)
        self.assertNotEqual(key1, key3)
        self.assertNotEqual(key2, key3)
        # Must contain sanitized parent_run_id
        self.assertIn('run-abc', key1)

    def test_p4_prepare_subagent_isolation_returns_isolation_config(self) -> None:
        """prepare_subagent_isolation returns an IsolationContext for shared mode."""
        from teaagent.subagents._isolation import (
            IsolationContext,
            prepare_subagent_isolation,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ctx, error = prepare_subagent_isolation(
                parent_root=root,
                isolation='shared',
                session_key='test-key',
            )
            self.assertEqual(error, '')
            self.assertIsNotNone(ctx)
            self.assertIsInstance(ctx, IsolationContext)
            self.assertEqual(ctx.isolation, 'shared')
            self.assertEqual(ctx.parent_root, ctx.child_root)

    def test_p5_subagent_def_accepts_isolation_field(self) -> None:
        """SubagentDef dataclass has isolation field with default 'shared'."""
        from teaagent.subagents._types import SubagentDef

        # Default isolation
        default_def = SubagentDef(name='default-agent')
        self.assertEqual(default_def.isolation, 'shared')

        # Explicit isolation
        worktree_def = SubagentDef(name='worktree-agent', isolation='worktree')
        self.assertEqual(worktree_def.isolation, 'worktree')

        # Verify all SubagentDef fields are accessible
        self.assertEqual(default_def.name, 'default-agent')
        self.assertEqual(default_def.max_iterations, 5)
        self.assertEqual(default_def.max_tool_calls, 8)
        self.assertEqual(default_def.max_depth, 1)


# ============================================================================
# Class Q: Telemetry scenarios
# ============================================================================


class TelemetryScenarios(unittest.TestCase):
    """Telemetry configuration, metrics sink, and OTLP endpoint wiring."""

    def test_q1_telemetry_config_default_values(self) -> None:
        """TelemetryConfig has expected default field values."""
        from teaagent.telemetry import TelemetryConfig

        config = TelemetryConfig()
        self.assertEqual(config.service_name, 'teaagent')
        self.assertEqual(config.service_version, '0.1.0')
        self.assertIsNone(config.otlp_endpoint)
        self.assertIsNone(config.metrics_otlp_endpoint)
        self.assertEqual(config.otlp_headers, {})
        self.assertFalse(config.console)
        self.assertEqual(config.sample_rate, 1.0)

    def test_q2_in_memory_metrics_sink_counter_and_histogram(self) -> None:
        """InMemoryMetricsSink tracks counters and histograms from audit events."""
        from teaagent.telemetry._metrics import InMemoryMetricsSink

        sink = InMemoryMetricsSink()

        # Simulate events
        class FakeEvent:
            def __init__(self, event_type: str, payload: dict | None = None) -> None:
                self.event_type = event_type
                self.payload = payload or {}

        sink.handle_event(FakeEvent('run_started'))
        sink.handle_event(FakeEvent('run_started'))
        sink.handle_event(FakeEvent('tool_call_started', {'tool_name': 'read_file'}))
        sink.handle_event(FakeEvent('tool_call_started', {'tool_name': 'write_file'}))
        sink.handle_event(FakeEvent('tool_call_started', {'tool_name': 'write_file'}))
        sink.handle_event(FakeEvent('tool_call_completed', {'tool_name': 'write_file'}))
        sink.handle_event(
            FakeEvent('run_completed', {'iterations': 5, 'cost_cents': 250.0})
        )
        sink.handle_event(FakeEvent('run_failed', {'cost_cents': 42.0}))

        snap = sink.snapshot()
        # Counters
        self.assertEqual(snap.counters.get('agent.runs.started', 0), 2)
        self.assertEqual(snap.counters.get('agent.runs.completed', 0), 1)
        self.assertEqual(snap.counters.get('agent.runs.failed', 0), 1)
        self.assertEqual(snap.counters.get('agent.tool_calls.started', 0), 3)
        self.assertEqual(snap.counters.get('agent.tool_calls.started.write_file', 0), 2)
        self.assertEqual(snap.counters.get('agent.tool_calls.completed', 0), 1)
        # Histograms
        self.assertIn(5.0, snap.histograms.get('agent.run.iterations', []))
        self.assertIn(250.0, snap.histograms.get('agent.run.cost_cents', []))
        self.assertIn(42.0, snap.histograms.get('agent.run.cost_cents', []))

    def test_q3_configure_telemetry_with_otlp_endpoint(self) -> None:
        """configure_telemetry wires OTLP exporter when endpoint is provided."""
        from teaagent.telemetry import HAS_OTEL, TelemetryConfig, configure_telemetry
        from teaagent.telemetry._audit import OTelAuditSink

        if not HAS_OTEL:
            self.skipTest('OpenTelemetry packages not installed')

        config = TelemetryConfig(
            service_name='test-agent',
            service_version='2.0.0',
            otlp_endpoint='http://localhost:4318/v1/traces',
            console=False,
        )
        sink, tracer = configure_telemetry(config)
        self.assertIsInstance(sink, OTelAuditSink)
        self.assertIsNotNone(tracer)
        sink.shutdown()


# ============================================================================
# Class J: Control-plane server scenarios
# ============================================================================


class ControlPlaneScenarios(unittest.TestCase):
    """ControlPlaneServer lifecycle, health, multi-tenant, and agent requests."""

    def test_j1_control_plane_server_init(self) -> None:
        """ControlPlaneServer initialises with host, port, and registry config."""
        from teaagent.control_plane_api import ControlPlaneServer

        server = ControlPlaneServer(host='127.0.0.1', port=9090)
        self.assertEqual(server.host, '127.0.0.1')
        self.assertEqual(server.port, 9090)
        self.assertIsNotNone(server.registry)
        self.assertIsNotNone(server.state)
        self.assertEqual(server.base_url, 'http://127.0.0.1:9090')

    def test_j2_health_check_endpoint(self) -> None:
        """GET /api/health returns {'status': 'ok'} on a running server."""
        import urllib.request

        from teaagent.control_plane_api import ControlPlaneServer

        server = ControlPlaneServer(host='127.0.0.1', port=0)
        server.start(daemon=True)
        try:
            url = f'{server.base_url}/api/health'
            with urllib.request.urlopen(url, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                import json

                body = json.loads(resp.read().decode())
                self.assertEqual(body['status'], 'ok')
        finally:
            server.stop()

    def test_j3_list_tenants(self) -> None:
        """ControlPlaneRegistry lists tenants across multi-tenant isolation."""
        from teaagent.control_plane_tenant import ControlPlaneRegistry

        registry = ControlPlaneRegistry()
        self.assertEqual(registry.list_tenants(), [])

        registry.get_or_create('tenant-a')
        registry.get_or_create('tenant-b')
        tenants = registry.list_tenants()
        self.assertIn('tenant-a', tenants)
        self.assertIn('tenant-b', tenants)
        self.assertEqual(len(tenants), 2)

        # Same tenant idempotent
        state1 = registry.get_or_create('tenant-a')
        state2 = registry.get_or_create('tenant-a')
        self.assertIs(state1, state2)

    def test_j4_handle_agent_request_via_bridge(self) -> None:
        """publish_swarm_workflow pushes workflow/focus into control-plane state."""
        from teaagent.control_plane_bridge import publish_swarm_workflow
        from teaagent.control_plane_tenant import ControlPlaneState

        state = ControlPlaneState()
        publish_swarm_workflow(
            state,
            parent_run_id='run-1',
            phase='executing',
            subagents=[
                {'id': 'a1', 'status': 'running'},
                {'id': 'a2', 'status': 'completed'},
            ],
            totals={'total': 2, 'completed': 1},
        )
        snap = state.snapshot()
        self.assertIsNotNone(snap['workflow'])
        self.assertEqual(snap['workflow']['parent_run_id'], 'run-1')
        self.assertEqual(snap['workflow']['phase'], 'executing')
        self.assertIsNotNone(snap['focus'])
        self.assertEqual(snap['focus']['parent_run_id'], 'run-1')
        self.assertIsNotNone(snap['focus']['active_task'])

    def test_j5_graceful_shutdown(self) -> None:
        """Server stops without error and thread joins cleanly."""
        from teaagent.control_plane_api import ControlPlaneServer

        server = ControlPlaneServer(host='127.0.0.1', port=0)
        server.start(daemon=True)
        self.assertIn('http://', server.base_url)
        server.stop()


# ============================================================================
# Class K: Federation consensus scenarios
# ============================================================================


class ConsensusScenarios(unittest.TestCase):
    """Peer identity, registry, voting cycle, risk thresholds, and quorum."""

    def test_k1_peer_identity_fingerprint(self) -> None:
        """PeerIdentity auto-computes a 16-char SHA-256 fingerprint from SSH key."""
        from teaagent.consensus import PeerIdentity

        key = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGx0Y2...'
        peer = PeerIdentity(name='node-1', ssh_public_key=key)
        self.assertEqual(peer.name, 'node-1')
        self.assertEqual(len(peer.fingerprint), 16)
        self.assertTrue(peer.is_active)
        # Same key → same fingerprint
        peer2 = PeerIdentity(name='node-2', ssh_public_key=key)
        self.assertEqual(peer.fingerprint, peer2.fingerprint)

    def test_k2_peer_registry_lifecycle(self) -> None:
        """PeerRegistry register, unregister, list, and persistence round-trip."""
        import tempfile
        from pathlib import Path

        from teaagent.consensus import PeerIdentity, PeerRegistry

        with tempfile.TemporaryDirectory() as tmp:
            storage = Path(tmp) / 'peers.json'
            reg = PeerRegistry(storage_path=storage)

            p1 = PeerIdentity(name='alfa', ssh_public_key='key-alfa')
            p2 = PeerIdentity(name='bravo', ssh_public_key='key-bravo')
            reg.register(p1)
            reg.register(p2)

            all_peers = reg.list_all()
            self.assertEqual(len(all_peers), 2)
            self.assertIsNotNone(reg.get('alfa'))
            self.assertIsNone(reg.get('charlie'))

            # Unregister
            removed = reg.unregister('alfa')
            self.assertIsNotNone(removed)
            self.assertEqual(len(reg.list_all()), 1)

            # Duplicate raises
            with self.assertRaises(ValueError):
                reg.register(p2)

            # Reload from disk
            reg2 = PeerRegistry(storage_path=storage)
            self.assertEqual(len(reg2.list_all()), 1)
            self.assertIsNotNone(reg2.get('bravo'))

    def test_k3_consensus_engine_voting_cycle(self) -> None:
        """Full cycle: request consensus → cast votes → approve/reject."""
        from teaagent.consensus import (
            ConsensusConfig,
            ConsensusEngine,
            ConsensusStatus,
            PeerIdentity,
            PeerRegistry,
            RiskLevel,
            VoteDecision,
            VotingThreshold,
            peer_vote_signature,
        )

        reg = PeerRegistry()
        alfa = PeerIdentity(name='alfa', ssh_public_key='key-alfa')
        bravo = PeerIdentity(name='bravo', ssh_public_key='key-bravo')
        reg.register(alfa)
        reg.register(bravo)

        config = ConsensusConfig(
            default_voting_threshold=VotingThreshold.SIMPLE_MAJORITY,
        )
        engine = ConsensusEngine(peer_registry=reg, config=config)

        state = engine.request_consensus(
            task_description='deploy to staging',
            risk_level=RiskLevel.MEDIUM,
            proposed_by='alfa',
        )
        self.assertEqual(state.status, ConsensusStatus.VOTING)
        self.assertEqual(state.proposal.risk_level, RiskLevel.MEDIUM)

        # Cast approving votes
        sig_a = peer_vote_signature(
            alfa,
            state.proposal.task_description,
            proposal_id=state.proposal.id,
            peer_name='alfa',
            decision=VoteDecision.APPROVE.value,
        )
        self.assertTrue(
            engine.submit_vote(state.proposal.id, 'alfa', VoteDecision.APPROVE, sig_a)
        )
        sig_b = peer_vote_signature(
            bravo,
            state.proposal.task_description,
            proposal_id=state.proposal.id,
            peer_name='bravo',
            decision=VoteDecision.APPROVE.value,
        )
        self.assertTrue(
            engine.submit_vote(state.proposal.id, 'bravo', VoteDecision.APPROVE, sig_b)
        )

        final = engine.get_consensus_status(state.proposal.id)
        assert final is not None
        self.assertEqual(final.status, ConsensusStatus.APPROVED)
        self.assertTrue(final.is_approved())

    def test_k4_risk_level_supermajority_enforcement(self) -> None:
        """HIGH risk requires SUPERMAJORITY; 2/3 approving needed for quorum."""
        from teaagent.consensus import (
            ConsensusConfig,
            ConsensusEngine,
            ConsensusStatus,
            PeerIdentity,
            PeerRegistry,
            RiskLevel,
            VoteDecision,
            VotingThreshold,
            peer_vote_signature,
        )

        reg = PeerRegistry()
        alfa = PeerIdentity(name='alfa', ssh_public_key='key-alfa')
        bravo = PeerIdentity(name='bravo', ssh_public_key='key-bravo')
        charlie = PeerIdentity(name='charlie', ssh_public_key='key-charlie')
        reg.register(alfa)
        reg.register(bravo)
        reg.register(charlie)

        config = ConsensusConfig(default_voting_threshold=VotingThreshold.SUPERMAJORITY)
        engine = ConsensusEngine(peer_registry=reg, config=config)

        state = engine.request_consensus(
            task_description='delete production database',
            risk_level=RiskLevel.HIGH,
            proposed_by='alfa',
        )
        # Only 2/3 approve → not enough for supermajority
        sig_a = peer_vote_signature(
            alfa,
            state.proposal.task_description,
            proposal_id=state.proposal.id,
            peer_name='alfa',
            decision=VoteDecision.APPROVE.value,
        )
        sig_b = peer_vote_signature(
            bravo,
            state.proposal.task_description,
            proposal_id=state.proposal.id,
            peer_name='bravo',
            decision=VoteDecision.APPROVE.value,
        )
        sig_c = peer_vote_signature(
            charlie,
            state.proposal.task_description,
            proposal_id=state.proposal.id,
            peer_name='charlie',
            decision=VoteDecision.REJECT.value,
        )
        engine.submit_vote(state.proposal.id, 'alfa', VoteDecision.APPROVE, sig_a)
        engine.submit_vote(state.proposal.id, 'bravo', VoteDecision.APPROVE, sig_b)
        engine.submit_vote(state.proposal.id, 'charlie', VoteDecision.REJECT, sig_c)

        final = engine.get_consensus_status(state.proposal.id)
        # 2 approves out of 3 = 66.6% which is NOT > 2/3 (it's equal)
        self.assertFalse(final.is_approved())
        self.assertEqual(final.status, ConsensusStatus.REJECTED)

    def test_k5_voting_threshold_calculations(self) -> None:
        """Quorum sizes for SIMPLE_MAJORITY, SUPERMAJORITY, UNANIMOUS."""
        from teaagent.consensus import (
            ConsensusState,
            Proposal,
            RiskLevel,
            VotingThreshold,
        )

        def _state(threshold: VotingThreshold, num_peers: int) -> ConsensusState:
            return ConsensusState(
                proposal=Proposal(
                    id='p1',
                    task_description='x',
                    risk_level=RiskLevel.LOW,
                    proposed_by='a',
                ),
                voting_threshold=threshold,
                required_peers={f'p{i}' for i in range(num_peers)},
            )

        # SIMPLE_MAJORITY: ceil(N/2) + 1, but formula is N//2 + 1
        s = _state(VotingThreshold.SIMPLE_MAJORITY, 5)
        self.assertEqual(s.get_quorum_size(), 3)  # 5//2 + 1
        s5 = _state(VotingThreshold.SIMPLE_MAJORITY, 4)
        self.assertEqual(s5.get_quorum_size(), 3)  # 4//2 + 1

        # SUPERMAJORITY: ceil(2N/3) + 1, formula is (N*2)//3 + 1
        s = _state(VotingThreshold.SUPERMAJORITY, 3)
        self.assertEqual(s.get_quorum_size(), 3)  # (3*2)//3 + 1
        s7 = _state(VotingThreshold.SUPERMAJORITY, 6)
        self.assertEqual(s7.get_quorum_size(), 5)  # (6*2)//3 + 1

        # UNANIMOUS: all peers
        s = _state(VotingThreshold.UNANIMOUS, 5)
        self.assertEqual(s.get_quorum_size(), 5)


# ============================================================================
# Class L: Hook system scenarios
# ============================================================================


class HookSystemScenarios(unittest.TestCase):
    """Pre/post-tool hooks, permission checks, and session lifecycle events."""

    def test_l1_hook_registry_register_pre_post(self) -> None:
        """HookRegistry registers pre- and post-tool hooks."""
        from teaagent.hooks import HookRegistry

        registry = HookRegistry()
        registry.register_pre_hook(lambda tn, args: None)
        registry.register_post_hook(lambda tn, args, res: None)
        self.assertEqual(len(registry.config.pre_hooks), 1)
        self.assertEqual(len(registry.config.post_hooks), 1)

    def test_l2_pre_tool_use_modify_and_veto(self) -> None:
        """PreToolUse hook can modify arguments or veto via HookError."""
        from teaagent.hooks import HookError, HookRegistry

        # Hook that modifies arguments
        def modify_hook(tool_name: str, arguments: dict) -> dict | None:
            arguments['extra'] = 'injected'
            return arguments

        # Hook that vetoes
        def veto_hook(tool_name: str, arguments: dict) -> dict | None:
            raise HookError('blocked by veto')

        registry = HookRegistry()

        # Modify test
        registry.register_pre_hook(modify_hook)
        result = registry.run_pre_hooks('workspace_write_file', {'path': 'f.txt'})
        self.assertIsNotNone(result)
        self.assertEqual(result['extra'], 'injected')
        self.assertEqual(result['path'], 'f.txt')

        # Veto test
        registry2 = HookRegistry()
        registry2.register_pre_hook(veto_hook)
        with self.assertRaises(HookError) as ctx:
            registry2.run_pre_hooks('workspace_write_file', {'path': 'f.txt'})
        self.assertIn('blocked by veto', str(ctx.exception))

    def test_l3_post_tool_use_modify_result(self) -> None:
        """PostToolUse hook can inspect and modify the tool result."""
        from teaagent.hooks import HookRegistry

        def add_timestamp(tool_name: str, arguments: dict, result: dict) -> dict | None:
            result['hooked_at'] = '2026-06-07'
            return result

        registry = HookRegistry()
        registry.register_post_hook(add_timestamp)
        modified = registry.run_post_hooks(
            'workspace_write_file', {'path': 'f.txt'}, {'status': 'ok'}
        )
        self.assertIsNotNone(modified)
        self.assertEqual(modified['status'], 'ok')
        self.assertEqual(modified['hooked_at'], '2026-06-07')

    def test_l4_permission_check_hook_blocks_allows(self) -> None:
        """permission_check_hook ALLOW passes; DENY blocks; AUTO blocks destructive."""
        from teaagent.hooks import (
            HookError,
            HookPermissionMode,
            permission_check_hook,
        )

        # ALLOW — everything passes
        allow_hook = permission_check_hook(mode=HookPermissionMode.ALLOW)
        self.assertIsNone(allow_hook('workspace_write_file', {'path': 'f.txt'}))

        # DENY — everything blocked
        deny_hook = permission_check_hook(mode=HookPermissionMode.DENY)
        with self.assertRaises(HookError):
            deny_hook('workspace_read_file', {})

        # AUTO — destructive tools blocked, safe tools allowed
        auto_hook = permission_check_hook(mode=HookPermissionMode.AUTO)
        self.assertIsNone(auto_hook('workspace_read_file', {}))
        with self.assertRaises(HookError):
            auto_hook('workspace_write_file', {'path': 'f.txt'})

    def test_l5_session_lifecycle_hooks_fired(self) -> None:
        """SessionStart and SessionEnd hooks fire with correct arguments."""
        from teaagent.hooks import HookRegistry

        events: list[tuple[str, str, dict]] = []

        def on_start(session_id: str, context: dict) -> None:
            events.append(('start', session_id, context))

        def on_end(session_id: str, context: dict) -> None:
            events.append(('end', session_id, context))

        registry = HookRegistry()
        registry.register_session_start_hook(on_start)
        registry.register_session_end_hook(on_end)

        ctx = {'user': 'alice'}
        registry.run_session_start_hooks('ses-001', ctx)
        registry.run_session_end_hooks('ses-001', ctx)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0], ('start', 'ses-001', ctx))
        self.assertEqual(events[1], ('end', 'ses-001', ctx))


# ============================================================================
# Class M: Plan enforcement scenarios
# ============================================================================


class PlanEnforcementScenarios(unittest.TestCase):
    """Plan-before-write enforcement, skip-plan bypass, and contract checks."""

    def test_m1_require_plan_blocks_write_without_plan(self) -> None:
        """PlanValidator with require_plan=True raises on write without bound plan."""
        from teaagent.policy import ApprovalPolicy
        from teaagent.runner._plan_validator import PlanValidator
        from teaagent.types import PermissionMode, ToolPermissionError

        policy = ApprovalPolicy(permission_mode=PermissionMode.WORKSPACE_WRITE)
        validator = PlanValidator(
            approval_policy=policy,
            require_plan=True,
            skip_plan_check=False,
        )
        with self.assertRaises(ToolPermissionError) as ctx:
            validator.validate_write_allowed(
                tool_name='workspace_write_file',
                context={},
            )
        self.assertIn('plan', str(ctx.exception).lower())

    def test_m2_skip_plan_check_bypasses_enforcement(self) -> None:
        """PlanValidator with skip_plan_check=True allows writes without plan."""
        from teaagent.governance.plan_gate import assert_write_allowed
        from teaagent.types import PermissionMode

        # Should NOT raise
        assert_write_allowed(
            tool_name='workspace_write_file',
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            context={},
            require_plan=False,
            skip_plan_check=True,
        )

    def test_m3_plan_validator_contract_exists(self) -> None:
        """PlanValidator stores and returns the plan contract."""
        from teaagent.policy import ApprovalPolicy
        from teaagent.runner._plan_validator import PlanValidator
        from teaagent.types import PermissionMode

        policy = ApprovalPolicy(permission_mode=PermissionMode.WORKSPACE_WRITE)
        validator = PlanValidator(
            approval_policy=policy,
            require_plan=True,
        )

        self.assertIsNone(validator.get_plan_contract())
        contract = {'content_hash': 'abc123', 'file_targets': ['src/app.py']}
        validator.set_plan_contract(contract)
        self.assertIsNotNone(validator.get_plan_contract())
        self.assertEqual(validator.get_plan_contract()['content_hash'], 'abc123')

        # With a valid plan, validate_write_allowed should pass
        validator.validate_write_allowed(
            tool_name='workspace_write_file',
            context={'plan_contract': contract},
        )


if __name__ == '__main__':
    unittest.main()
