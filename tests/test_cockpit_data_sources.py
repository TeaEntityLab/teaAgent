"""Tests for cockpit data sources (TASK-H4-001-02)."""

import unittest
from pathlib import Path

from teaagent.tui.cockpit_data_sources import (
    ApprovalDataSource,
    BackgroundDataSource,
    CockpitDataManager,
    CostDataSource,
    MemoryDataSource,
    WorkflowDataSource,
)
from teaagent.tui.cockpit_screens import WorkflowRow


class TestWorkflowDataSource(unittest.TestCase):
    """Test the workflow data source."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = Path('.')
        self.source = WorkflowDataSource(self.root)

    def test_get_workflows(self):
        """Test getting workflow data."""
        workflows = self.source.get_workflows(limit=10)
        self.assertIsInstance(workflows, list)
        for workflow in workflows:
            self.assertIsInstance(workflow, WorkflowRow)

    def test_get_workflows_with_status_filter(self):
        """Test getting workflow data with status filter."""
        # Test with a status that might not exist
        workflows = self.source.get_workflows(limit=10, status_filter='running')
        self.assertIsInstance(workflows, list)
        for workflow in workflows:
            self.assertEqual(workflow.status, 'running')

    def test_get_workflow_count(self):
        """Test getting workflow count."""
        count = self.source.get_workflow_count()
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    def test_get_workflow_count_with_status_filter(self):
        """Test getting workflow count with status filter."""
        count = self.source.get_workflow_count(status_filter='completed')
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)


class TestCostDataSource(unittest.TestCase):
    """Test the cost data source."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = Path('.')
        self.source = CostDataSource(self.root)

    def test_get_costs(self):
        """Test getting cost data."""
        costs = self.source.get_costs(limit=10)
        self.assertIsInstance(costs, list)

    def test_get_total_cost(self):
        """Test getting total cost."""
        total_cost = self.source.get_total_cost()
        self.assertIsInstance(total_cost, float)
        self.assertGreaterEqual(total_cost, 0.0)

    def test_get_cost_trends(self):
        """Test getting cost trends."""
        trends = self.source.get_cost_trends(days=7)
        self.assertIsInstance(trends, list)
        for trend in trends:
            self.assertIn('date', trend)
            self.assertIn('cost_cents', trend)
            self.assertIsInstance(trend['cost_cents'], float)

    def test_get_budget_status_no_limit(self):
        """Test getting budget status with no limit."""
        source = CostDataSource(self.root, budget_limit_cents=None)
        status = source.get_budget_status()
        self.assertEqual(status['status'], 'unlimited')
        self.assertIsNone(status['limit_cents'])
        self.assertEqual(status['alert_level'], 'none')

    def test_get_budget_status_with_limit(self):
        """Test getting budget status with limit."""
        source = CostDataSource(self.root, budget_limit_cents=1000)  # $10.00
        status = source.get_budget_status()
        self.assertIn('status', status)
        self.assertIn('spent_cents', status)
        self.assertEqual(status['limit_cents'], 1000)
        self.assertIn('usage_percentage', status)
        self.assertIn('alert_level', status)

    def test_get_budget_status_alert_levels(self):
        """Test budget status alert levels."""
        # Test with different budget scenarios
        total_cost = self.source.get_total_cost()

        # Critical alert (exceeded budget)
        source = CostDataSource(self.root, budget_limit_cents=int(total_cost * 0.5))
        status = source.get_budget_status()
        self.assertEqual(status['alert_level'], 'critical')

        # Warning alert (90%+ usage)
        source = CostDataSource(self.root, budget_limit_cents=int(total_cost * 1.1))
        status = source.get_budget_status()
        self.assertIn(status['alert_level'], ['warning', 'critical'])

        # No alert (low usage)
        source = CostDataSource(self.root, budget_limit_cents=int(total_cost * 10))
        status = source.get_budget_status()
        self.assertEqual(status['alert_level'], 'none')


class TestMemoryDataSource(unittest.TestCase):
    """Test the memory data source."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = Path('.')
        self.source = MemoryDataSource(self.root)

    def test_get_memories(self):
        """Test getting memory data."""
        memories = self.source.get_memories(limit=10)
        self.assertIsInstance(memories, list)

    def test_get_memory_count(self):
        """Test getting memory count."""
        count = self.source.get_memory_count()
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    def test_get_memory_count_with_scope_filter(self):
        """Test getting memory count with scope filter."""
        count = self.source.get_memory_count(scope_filter='workspace')
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    def test_get_quarantined_memory_count(self):
        """Test getting quarantined memory count."""
        count = self.source.get_quarantined_memory_count()
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)


class TestBackgroundDataSource(unittest.TestCase):
    """Test the background data source."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = Path('.')
        self.source = BackgroundDataSource(self.root)

    def test_get_background_runs(self):
        """Test getting background run data."""
        background_runs = self.source.get_background_runs(limit=10)
        self.assertIsInstance(background_runs, list)

    def test_get_background_run_count(self):
        """Test getting background run count."""
        count = self.source.get_background_run_count()
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    def test_get_background_run_status(self):
        """Test getting detailed background run status."""
        # Get background runs first
        runs = self.source.get_background_runs(limit=1)
        if runs:
            status = self.source.get_background_run_status(runs[0].run_id)
            self.assertIsNotNone(status)
            self.assertIn('run_id', status)
            self.assertIn('status', status)
        else:
            # If no runs, test with non-existent ID
            status = self.source.get_background_run_status('non-existent')
            self.assertIsNone(status)


class TestApprovalDataSource(unittest.TestCase):
    """Test the approval data source."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = Path('.')
        self.source = ApprovalDataSource(self.root)

    def test_get_approvals(self):
        """Test getting approval data."""
        approvals = self.source.get_approvals(limit=10)
        self.assertIsInstance(approvals, list)

    def test_get_approval_count(self):
        """Test getting approval count."""
        count = self.source.get_approval_count()
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)


class TestCockpitDataManager(unittest.TestCase):
    """Test the cockpit data manager."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = Path('.')
        self.manager = CockpitDataManager(self.root)

    def test_get_all_data(self):
        """Test getting data for all screens."""
        data = self.manager.get_all_data(limit=10)
        self.assertIn('workflows', data)
        self.assertIn('costs', data)
        self.assertIn('memories', data)
        self.assertIn('approvals', data)
        self.assertIn('background_runs', data)

        # Check that all data are lists
        for _key, value in data.items():
            self.assertIsInstance(value, list)

    def test_get_workflows(self):
        """Test getting workflow data through manager."""
        workflows = self.manager.get_workflows(limit=10)
        self.assertIsInstance(workflows, list)

    def test_get_costs(self):
        """Test getting cost data through manager."""
        costs = self.manager.get_costs(limit=10)
        self.assertIsInstance(costs, list)

    def test_get_memories(self):
        """Test getting memory data through manager."""
        memories = self.manager.get_memories(limit=10)
        self.assertIsInstance(memories, list)

    def test_get_approvals(self):
        """Test getting approval data through manager."""
        approvals = self.manager.get_approvals(limit=10)
        self.assertIsInstance(approvals, list)

    def test_get_background_runs(self):
        """Test getting background run data through manager."""
        background_runs = self.manager.get_background_runs(limit=10)
        self.assertIsInstance(background_runs, list)


if __name__ == '__main__':
    unittest.main()
