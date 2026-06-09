"""Integration tests for cockpit screens with real data (TASK-H4-001-02)."""

import unittest
from pathlib import Path

from teaagent.tui.cockpit_data_sources import CockpitDataManager
from teaagent.tui.cockpit_screens import CockpitTab, create_cockpit_renderer


class TestCockpitIntegration(unittest.TestCase):
    """Integration tests for cockpit screens."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = Path('.')
        self.data_manager = CockpitDataManager(self.root)
        self.renderer = create_cockpit_renderer()

    def test_workflows_screen_integration(self):
        """Test full integration of workflows screen."""
        # Get workflow data
        workflows = self.data_manager.get_workflows(limit=10)

        # Render the screen
        output = self.renderer.render_screen(
            CockpitTab.WORKFLOWS, {'workflows': workflows}
        )

        # Verify the output contains expected elements
        self.assertIn('TeaAgent Control Plane Cockpit', output)
        self.assertIn('Active Workflows', output)
        self.assertIn('*[Workflows]*', output)  # Current tab is highlighted

    def test_costs_screen_integration(self):
        """Test full integration of costs screen."""
        # Get cost data
        costs = self.data_manager.get_costs(limit=10)

        # Render the screen
        output = self.renderer.render_screen(CockpitTab.COSTS, {'costs': costs})

        # Verify the output contains expected elements
        self.assertIn('TeaAgent Control Plane Cockpit', output)
        self.assertIn('Cost Allocation', output)
        self.assertIn('*[Costs]*', output)  # Current tab is highlighted

    def test_memory_screen_integration(self):
        """Test full integration of memory screen."""
        # Get memory data
        memories = self.data_manager.get_memories(limit=10)

        # Render the screen
        output = self.renderer.render_screen(CockpitTab.MEMORY, {'memories': memories})

        # Verify the output contains expected elements
        self.assertIn('TeaAgent Control Plane Cockpit', output)
        self.assertIn('Memory Registry', output)
        self.assertIn('*[Memory]*', output)  # Current tab is highlighted

    def test_background_screen_integration(self):
        """Test full integration of background screen."""
        # Get background run data
        background_runs = self.data_manager.get_background_runs(limit=10)

        # Render the screen
        output = self.renderer.render_screen(
            CockpitTab.BACKGROUND, {'background_runs': background_runs}
        )

        # Verify the output contains expected elements
        self.assertIn('TeaAgent Control Plane Cockpit', output)
        self.assertIn('Background Runs', output)
        self.assertIn('*[Background]*', output)  # Current tab is highlighted

    def test_approvals_screen_integration(self):
        """Test full integration of approvals screen."""
        # Get approval data (currently returns empty list)
        approvals = self.data_manager.get_approvals(limit=10)

        # Render the screen
        output = self.renderer.render_screen(
            CockpitTab.APPROVALS, {'approvals': approvals}
        )

        # Verify the output contains expected elements
        self.assertIn('TeaAgent Control Plane Cockpit', output)
        self.assertIn('Pending Approvals', output)
        self.assertIn('*[Approvals]*', output)  # Current tab is highlighted

    def test_all_data_integration(self):
        """Test integration with all data sources."""
        # Get all data
        data = self.data_manager.get_all_data(limit=10)

        # Render each screen
        for tab in CockpitTab:
            output = self.renderer.render_screen(tab, data)
            self.assertIn('TeaAgent Control Plane Cockpit', output)
            self.assertIn(f'*[{tab.value.capitalize()}]*', output)

    def test_tenant_filtering(self):
        """Test tenant filtering in workflows screen."""
        # Get workflow data with tenant filter
        workflows = self.data_manager.get_workflows(limit=10, tenant_filter='default')

        # Render the screen with filter
        output = self.renderer.render_screen(
            CockpitTab.WORKFLOWS, {'workflows': workflows}, filter_value='default'
        )

        # Verify the output contains expected elements
        self.assertIn('Active Workflows', output)

    def test_status_filtering(self):
        """Test status filtering in workflows screen."""
        # Get workflow data with status filter
        workflows = self.data_manager.get_workflows(limit=10, status_filter='completed')

        # Render the screen
        output = self.renderer.render_screen(
            CockpitTab.WORKFLOWS, {'workflows': workflows}
        )

        # Verify the output contains expected elements
        self.assertIn('Active Workflows', output)


if __name__ == '__main__':
    unittest.main()
