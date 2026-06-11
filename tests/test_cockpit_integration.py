"""Integration tests for cockpit screens with real data (TASK-H4-001-02)."""

from pathlib import Path

import pytest

from teaagent.tui.cockpit_data_sources import CockpitDataManager
from teaagent.tui.cockpit_screens import CockpitTab, create_cockpit_renderer


@pytest.fixture
def cockpit_fixtures():
    """Set up test fixtures."""
    root = Path('.')
    data_manager = CockpitDataManager(root)
    renderer = create_cockpit_renderer()
    return data_manager, renderer


def test_workflows_screen_integration(cockpit_fixtures):
    """Test full integration of workflows screen."""
    data_manager, renderer = cockpit_fixtures
    # Get workflow data
    workflows = data_manager.get_workflows(limit=10)

    # Render the screen
    output = renderer.render_screen(CockpitTab.WORKFLOWS, {'workflows': workflows})

    # Verify the output contains expected elements
    assert 'TeaAgent Control Plane Cockpit' in output
    assert 'Active Workflows' in output
    assert '*[Workflows]*' in output  # Current tab is highlighted


def test_costs_screen_integration(cockpit_fixtures):
    """Test full integration of costs screen."""
    data_manager, renderer = cockpit_fixtures
    # Get cost data
    costs = data_manager.get_costs(limit=10)

    # Render the screen
    output = renderer.render_screen(CockpitTab.COSTS, {'costs': costs})

    # Verify the output contains expected elements
    assert 'TeaAgent Control Plane Cockpit' in output
    assert 'Cost Allocation' in output
    assert '*[Costs]*' in output  # Current tab is highlighted


def test_memory_screen_integration(cockpit_fixtures):
    """Test full integration of memory screen."""
    data_manager, renderer = cockpit_fixtures
    # Get memory data
    memories = data_manager.get_memories(limit=10)

    # Render the screen
    output = renderer.render_screen(CockpitTab.MEMORY, {'memories': memories})

    # Verify the output contains expected elements
    assert 'TeaAgent Control Plane Cockpit' in output
    assert 'Memory Registry' in output
    assert '*[Memory]*' in output  # Current tab is highlighted


def test_background_screen_integration(cockpit_fixtures):
    """Test full integration of background screen."""
    data_manager, renderer = cockpit_fixtures
    # Get background run data
    background_runs = data_manager.get_background_runs(limit=10)

    # Render the screen
    output = renderer.render_screen(
        CockpitTab.BACKGROUND, {'background_runs': background_runs}
    )

    # Verify the output contains expected elements
    assert 'TeaAgent Control Plane Cockpit' in output
    assert 'Background Runs' in output
    assert '*[Background]*' in output  # Current tab is highlighted


def test_approvals_screen_integration(cockpit_fixtures):
    """Test full integration of approvals screen."""
    data_manager, renderer = cockpit_fixtures
    # Get approval data (currently returns empty list)
    approvals = data_manager.get_approvals(limit=10)

    # Render the screen
    output = renderer.render_screen(CockpitTab.APPROVALS, {'approvals': approvals})

    # Verify the output contains expected elements
    assert 'TeaAgent Control Plane Cockpit' in output
    assert 'Pending Approvals' in output
    assert '*[Approvals]*' in output  # Current tab is highlighted


def test_all_data_integration(cockpit_fixtures):
    """Test integration with all data sources."""
    data_manager, renderer = cockpit_fixtures
    # Get all data
    data = data_manager.get_all_data(limit=10)

    # Render each screen
    for tab in CockpitTab:
        output = renderer.render_screen(tab, data)
        assert 'TeaAgent Control Plane Cockpit' in output
        assert f'*[{tab.value.capitalize()}]*' in output


def test_tenant_filtering(cockpit_fixtures):
    """Test tenant filtering in workflows screen."""
    data_manager, renderer = cockpit_fixtures
    # Get workflow data with tenant filter
    workflows = data_manager.get_workflows(limit=10, tenant_filter='default')

    # Render the screen with filter
    output = renderer.render_screen(
        CockpitTab.WORKFLOWS, {'workflows': workflows}, filter_value='default'
    )

    # Verify the output contains expected elements
    assert 'Active Workflows' in output


def test_status_filtering(cockpit_fixtures):
    """Test status filtering in workflows screen."""
    data_manager, renderer = cockpit_fixtures
    # Get workflow data with status filter
    workflows = data_manager.get_workflows(limit=10, status_filter='completed')

    # Render the screen
    output = renderer.render_screen(CockpitTab.WORKFLOWS, {'workflows': workflows})

    # Verify the output contains expected elements
    assert 'Active Workflows' in output
