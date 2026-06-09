"""Tests for cockpit screen rendering (TASK-H4-001-01)."""

import unittest

from teaagent.tui.cockpit_screens import (
    ApprovalRow,
    BackgroundRow,
    CockpitScreenConfig,
    CockpitScreenRenderer,
    CockpitTab,
    CostRow,
    MemoryRow,
    WorkflowRow,
    create_cockpit_renderer,
)


class TestCockpitScreenRenderer(unittest.TestCase):
    """Test the cockpit screen renderer."""

    def setUp(self):
        """Set up test fixtures."""
        self.renderer = create_cockpit_renderer()

    def test_render_header(self):
        """Test that the header renders correctly."""
        header = self.renderer.render_header()
        self.assertIn('TeaAgent Control Plane Cockpit', header)
        self.assertIn('[Workflows]', header)
        self.assertIn('[Approvals]', header)
        self.assertIn('[Costs]', header)
        self.assertIn('[Memory]', header)
        self.assertIn('[Background]', header)

    def test_render_workflows_screen(self):
        """Test rendering the workflows screen."""
        workflows = [
            WorkflowRow(
                tenant='acme-corp',
                workflow_id='deploy-prod',
                status='running',
                cost_cents=1234,
            ),
            WorkflowRow(
                tenant='startup-inc',
                workflow_id='feature-x',
                status='pending',
                cost_cents=567,
            ),
        ]

        output = self.renderer.render_workflows_screen(workflows)
        self.assertIn('Active Workflows', output)
        self.assertIn('acme-corp', output)
        self.assertIn('deploy-prod', output)
        self.assertIn('startup-inc', output)
        self.assertIn('feature-x', output)
        self.assertIn('$12.34', output)
        self.assertIn('$5.67', output)

    def test_render_workflows_screen_with_filter(self):
        """Test rendering the workflows screen with tenant filter."""
        workflows = [
            WorkflowRow(
                tenant='acme-corp',
                workflow_id='deploy-prod',
                status='running',
                cost_cents=1234,
            ),
            WorkflowRow(
                tenant='startup-inc',
                workflow_id='feature-x',
                status='pending',
                cost_cents=567,
            ),
        ]

        output = self.renderer.render_workflows_screen(
            workflows, tenant_filter='acme-corp'
        )
        self.assertIn('acme-corp', output)
        self.assertNotIn('startup-inc', output)

    def test_render_approvals_screen(self):
        """Test rendering the approvals screen."""
        approvals = [
            ApprovalRow(
                tenant='acme-corp',
                workflow_id='deploy-prod',
                action_id='act-001',
                description='Production deployment',
                required_consensus='2-of-3',
                current_approvals=1,
                status='pending',
            ),
        ]

        output = self.renderer.render_approvals_screen(approvals)
        self.assertIn('Pending Approvals', output)
        self.assertIn('acme-corp', output)
        self.assertIn('Production deploymen', output)  # Truncated to 20 chars
        self.assertIn('1/2-of-3', output)

    def test_render_costs_screen(self):
        """Test rendering the costs screen."""
        costs = [
            CostRow(
                tenant='acme-corp',
                workflow_id='deploy-prod',
                spent_cents=1234,
                limit_cents=10000,
                period='today',
            ),
            CostRow(
                tenant='startup-inc',
                workflow_id='feature-x',
                spent_cents=567,
                limit_cents=None,
                period='today',
            ),
        ]

        output = self.renderer.render_costs_screen(costs)
        self.assertIn('Cost Allocation', output)
        self.assertIn('acme-corp', output)
        self.assertIn('$12.34', output)
        self.assertIn('$100.00', output)
        self.assertIn('unlimited', output)

    def test_render_memory_screen(self):
        """Test rendering the memory registry screen."""
        memories = [
            MemoryRow(
                memory_id='mem-001',
                scope='workspace',
                source='user',
                confidence='high',
                content_preview='Important context',
                quarantined=False,
            ),
            MemoryRow(
                memory_id='mem-002',
                scope='project',
                source='agent',
                confidence='medium',
                content_preview='Agent observation',
                quarantined=True,
            ),
        ]

        output = self.renderer.render_memory_screen(memories)
        self.assertIn('Memory Registry', output)
        self.assertIn('mem-001', output)
        self.assertIn('workspace', output)
        self.assertIn('user', output)
        self.assertIn('Y', output)  # Quarantined flag

    def test_render_background_screen(self):
        """Test rendering the background lifecycle screen."""
        background_runs = [
            BackgroundRow(
                run_id='bg-001',
                status='running',
                progress=0.67,
                cost_cents=890,
                can_attach=True,
                can_resume=False,
                can_stop=True,
            ),
            BackgroundRow(
                run_id='bg-002',
                status='suspended',
                progress=0.45,
                cost_cents=321,
                can_attach=False,
                can_resume=True,
                can_stop=True,
            ),
        ]

        output = self.renderer.render_background_screen(background_runs)
        self.assertIn('Background Runs', output)
        self.assertIn('bg-001', output)
        self.assertIn('67.0%', output)
        self.assertIn('$8.90', output)
        self.assertIn('Attach', output)
        self.assertIn('Resume', output)

    def test_render_screen_with_tabs(self):
        """Test the render_screen method with different tabs."""
        workflows = [
            WorkflowRow(
                tenant='acme-corp',
                workflow_id='deploy-prod',
                status='running',
                cost_cents=1234,
            ),
        ]

        # Test workflows tab
        output = self.renderer.render_screen(
            CockpitTab.WORKFLOWS, {'workflows': workflows}
        )
        self.assertIn('Active Workflows', output)

        # Test approvals tab
        output = self.renderer.render_screen(CockpitTab.APPROVALS, {'approvals': []})
        self.assertIn('Pending Approvals', output)

        # Test costs tab
        output = self.renderer.render_screen(CockpitTab.COSTS, {'costs': []})
        self.assertIn('Cost Allocation', output)

        # Test memory tab
        output = self.renderer.render_screen(CockpitTab.MEMORY, {'memories': []})
        self.assertIn('Memory Registry', output)

        # Test background tab
        output = self.renderer.render_screen(
            CockpitTab.BACKGROUND, {'background_runs': []}
        )
        self.assertIn('Background Runs', output)

    def test_cockpit_tab_enum(self):
        """Test the CockpitTab enum."""
        self.assertEqual(CockpitTab.WORKFLOWS.value, 'workflows')
        self.assertEqual(CockpitTab.APPROVALS.value, 'approvals')
        self.assertEqual(CockpitTab.COSTS.value, 'costs')
        self.assertEqual(CockpitTab.MEMORY.value, 'memory')
        self.assertEqual(CockpitTab.BACKGROUND.value, 'background')

    def test_cockpit_screen_config(self):
        """Test the CockpitScreenConfig dataclass."""
        config = CockpitScreenConfig(
            current_tab=CockpitTab.APPROVALS, width=120, height=30, show_help=False
        )
        self.assertEqual(config.current_tab, CockpitTab.APPROVALS)
        self.assertEqual(config.width, 120)
        self.assertEqual(config.height, 30)
        self.assertFalse(config.show_help)

    def test_create_cockpit_renderer_factory(self):
        """Test the factory function."""
        renderer = create_cockpit_renderer()
        self.assertIsInstance(renderer, CockpitScreenRenderer)
        self.assertIsInstance(renderer.config, CockpitScreenConfig)


if __name__ == '__main__':
    unittest.main()
