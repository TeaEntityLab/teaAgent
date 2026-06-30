"""Tests for cockpit data sources (TASK-H4-001-02)."""

from pathlib import Path

import pytest

from teaagent.run_store import RunSummary
from teaagent.tui.cockpit_data_sources import (
    ApprovalDataSource,
    BackgroundDataSource,
    CockpitDataManager,
    CostDataSource,
    MemoryDataSource,
    WorkflowDataSource,
)
from teaagent.tui.cockpit_screens import WorkflowRow


@pytest.fixture
def root_path():
    """Fixture for root path."""
    return Path('.')


def test_workflow_data_source_get_workflows(root_path):
    """Test getting workflow data."""
    source = WorkflowDataSource(root_path)
    workflows = source.get_workflows(limit=10)
    assert isinstance(workflows, list)
    for workflow in workflows:
        assert isinstance(workflow, WorkflowRow)


def test_workflow_data_source_get_workflows_with_status_filter(root_path):
    """Test getting workflow data with status filter."""
    source = WorkflowDataSource(root_path)
    # Test with a status that might not exist
    workflows = source.get_workflows(limit=10, status_filter='running')
    assert isinstance(workflows, list)
    for workflow in workflows:
        assert workflow.status == 'running'


def test_workflow_data_source_get_workflow_count(root_path):
    """Test getting workflow count."""
    source = WorkflowDataSource(root_path)
    count = source.get_workflow_count()
    assert isinstance(count, int)
    assert count >= 0


def test_workflow_data_source_get_workflow_count_with_status_filter(root_path):
    """Test getting workflow count with status filter."""
    source = WorkflowDataSource(root_path)
    count = source.get_workflow_count(status_filter='completed')
    assert isinstance(count, int)
    assert count >= 0


def test_cost_data_source_get_costs(root_path):
    """Test getting cost data."""
    source = CostDataSource(root_path)
    costs = source.get_costs(limit=10)
    assert isinstance(costs, list)


def test_cost_data_source_get_costs_uses_run_timestamp_period(root_path):
    """Cost rows should not label every run as today's period."""

    class FakeRunStore:
        def list_runs(self, *, limit: int):
            return [
                RunSummary(
                    run_id='old-run',
                    task='old task',
                    status='completed',
                    created_at='2026-06-28T01:02:03Z',
                    updated_at='2026-06-29T04:05:06Z',
                    path=root_path,
                    cost_cents=123.0,
                ),
                RunSummary(
                    run_id='unknown-run',
                    task='unknown task',
                    status='completed',
                    created_at='',
                    updated_at='',
                    path=root_path,
                    cost_cents=45.0,
                ),
            ]

    source = CostDataSource(root_path)
    source._run_store = FakeRunStore()

    costs = source.get_costs(limit=10)

    assert [cost.period for cost in costs] == ['2026-06-29', 'unknown']


def test_cost_data_source_get_total_cost(root_path):
    """Test getting total cost."""
    source = CostDataSource(root_path)
    total_cost = source.get_total_cost()
    assert isinstance(total_cost, float)
    assert total_cost >= 0.0


def test_cost_data_source_get_cost_trends(root_path):
    """Test getting cost trends."""
    source = CostDataSource(root_path)
    trends = source.get_cost_trends(days=7)
    assert isinstance(trends, list)
    for trend in trends:
        assert 'date' in trend
        assert 'cost_cents' in trend
        assert isinstance(trend['cost_cents'], float)


def test_cost_data_source_get_budget_status_no_limit(root_path):
    """Test getting budget status with no limit."""
    source = CostDataSource(root_path, budget_limit_cents=None)
    status = source.get_budget_status()
    assert status['status'] == 'unlimited'
    assert status['limit_cents'] is None
    assert status['alert_level'] == 'none'


def test_cost_data_source_get_budget_status_with_limit(root_path):
    """Test getting budget status with limit."""
    source = CostDataSource(root_path, budget_limit_cents=1000)  # $10.00
    status = source.get_budget_status()
    assert 'status' in status
    assert 'spent_cents' in status
    assert status['limit_cents'] == 1000
    assert 'usage_percentage' in status
    assert 'alert_level' in status


def test_cost_data_source_get_budget_status_alert_levels(root_path):
    """Test budget status alert levels."""
    source = CostDataSource(root_path)
    # Test with different budget scenarios
    total_cost = source.get_total_cost()

    # Critical alert (exceeded budget)
    source = CostDataSource(root_path, budget_limit_cents=int(total_cost * 0.5))
    status = source.get_budget_status()
    assert status['alert_level'] == 'critical'

    # Warning alert (90%+ usage)
    source = CostDataSource(root_path, budget_limit_cents=int(total_cost * 1.1))
    status = source.get_budget_status()
    assert status['alert_level'] in ['warning', 'critical']

    # No alert (low usage)
    source = CostDataSource(root_path, budget_limit_cents=int(total_cost * 10))
    status = source.get_budget_status()
    assert status['alert_level'] == 'none'


def test_memory_data_source_get_memories(root_path):
    """Test getting memory data."""
    source = MemoryDataSource(root_path)
    memories = source.get_memories(limit=10)
    assert isinstance(memories, list)


def test_memory_data_source_get_memory_count(root_path):
    """Test getting memory count."""
    source = MemoryDataSource(root_path)
    count = source.get_memory_count()
    assert isinstance(count, int)
    assert count >= 0


def test_memory_data_source_get_memory_count_with_scope_filter(root_path):
    """Test getting memory count with scope filter."""
    source = MemoryDataSource(root_path)
    count = source.get_memory_count(scope_filter='workspace')
    assert isinstance(count, int)
    assert count >= 0


def test_memory_data_source_get_quarantined_memory_count(root_path):
    """Test getting quarantined memory count."""
    source = MemoryDataSource(root_path)
    count = source.get_quarantined_memory_count()
    assert isinstance(count, int)
    assert count >= 0


def test_background_data_source_get_background_runs(root_path):
    """Test getting background run data."""
    source = BackgroundDataSource(root_path)
    background_runs = source.get_background_runs(limit=10)
    assert isinstance(background_runs, list)


def test_background_data_source_get_background_run_count(root_path):
    """Test getting background run count."""
    source = BackgroundDataSource(root_path)
    count = source.get_background_run_count()
    assert isinstance(count, int)
    assert count >= 0


def test_background_data_source_get_background_run_status(root_path):
    """Test getting detailed background run status."""
    source = BackgroundDataSource(root_path)
    # Get background runs first
    runs = source.get_background_runs(limit=1)
    if runs:
        status = source.get_background_run_status(runs[0].run_id)
        assert status is not None
        assert 'run_id' in status
        assert 'status' in status
    else:
        # If no runs, test with non-existent ID
        status = source.get_background_run_status('non-existent')
        assert status is None


def test_approval_data_source_get_approvals(root_path):
    """Test getting approval data."""
    source = ApprovalDataSource(root_path)
    approvals = source.get_approvals(limit=10)
    assert isinstance(approvals, list)


def test_approval_data_source_get_approval_count(root_path):
    """Test getting approval count."""
    source = ApprovalDataSource(root_path)
    count = source.get_approval_count()
    assert isinstance(count, int)
    assert count >= 0


def test_cockpit_data_manager_get_all_data(root_path):
    """Test getting data for all screens."""
    manager = CockpitDataManager(root_path)
    data = manager.get_all_data(limit=10)
    assert 'workflows' in data
    assert 'costs' in data
    assert 'memories' in data
    assert 'approvals' in data
    assert 'background_runs' in data

    # Check that all data are lists
    for _key, value in data.items():
        assert isinstance(value, list)


def test_cockpit_data_manager_get_workflows(root_path):
    """Test getting workflow data through manager."""
    manager = CockpitDataManager(root_path)
    workflows = manager.get_workflows(limit=10)
    assert isinstance(workflows, list)


def test_cockpit_data_manager_get_costs(root_path):
    """Test getting cost data through manager."""
    manager = CockpitDataManager(root_path)
    costs = manager.get_costs(limit=10)
    assert isinstance(costs, list)


def test_cockpit_data_manager_get_memories(root_path):
    """Test getting memory data through manager."""
    manager = CockpitDataManager(root_path)
    memories = manager.get_memories(limit=10)
    assert isinstance(memories, list)


def test_cockpit_data_manager_get_approvals(root_path):
    """Test getting approval data through manager."""
    manager = CockpitDataManager(root_path)
    approvals = manager.get_approvals(limit=10)
    assert isinstance(approvals, list)


def test_cockpit_data_manager_get_background_runs(root_path):
    """Test getting background run data through manager."""
    manager = CockpitDataManager(root_path)
    background_runs = manager.get_background_runs(limit=10)
    assert isinstance(background_runs, list)
