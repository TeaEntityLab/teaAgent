"""Tests for cockpit screen rendering (TASK-H4-001-01)."""

import pytest

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


@pytest.fixture
def renderer():
    """Set up test fixtures."""
    return create_cockpit_renderer()


def test_render_header(renderer):
    """Test that the header renders correctly."""
    header = renderer.render_header()
    assert 'TeaAgent Control Plane Cockpit' in header
    assert '[Workflows]' in header
    assert '[Approvals]' in header
    assert '[Costs]' in header
    assert '[Memory]' in header
    assert '[Background]' in header


def test_render_workflows_screen(renderer):
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

    output = renderer.render_workflows_screen(workflows)
    assert 'Active Workflows' in output
    assert 'acme-corp' in output
    assert 'deploy-prod' in output
    assert 'startup-inc' in output
    assert 'feature-x' in output
    assert '$12.34' in output
    assert '$5.67' in output


def test_render_workflows_screen_with_filter(renderer):
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

    output = renderer.render_workflows_screen(workflows, tenant_filter='acme-corp')
    assert 'acme-corp' in output
    assert 'startup-inc' not in output


def test_render_approvals_screen(renderer):
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

    output = renderer.render_approvals_screen(approvals)
    assert 'Pending Approvals' in output
    assert 'acme-corp' in output
    assert 'Production deploymen' in output  # Truncated to 20 chars
    assert '1/2-of-3' in output


def test_render_costs_screen(renderer):
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

    output = renderer.render_costs_screen(costs)
    assert 'Cost Allocation' in output
    assert 'acme-corp' in output
    assert '$12.34' in output
    assert '$100.00' in output
    assert 'unlimited' in output


def test_render_memory_screen(renderer):
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

    output = renderer.render_memory_screen(memories)
    assert 'Memory Registry' in output
    assert 'mem-001' in output
    assert 'workspace' in output
    assert 'user' in output
    assert 'Y' in output  # Quarantined flag


def test_render_background_screen(renderer):
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

    output = renderer.render_background_screen(background_runs)
    assert 'Background Runs' in output
    assert 'bg-001' in output
    assert '67.0%' in output
    assert '$8.90' in output
    assert 'Attach' in output
    assert 'Resume' in output


def test_render_screen_with_tabs(renderer):
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
    output = renderer.render_screen(CockpitTab.WORKFLOWS, {'workflows': workflows})
    assert 'Active Workflows' in output

    # Test approvals tab
    output = renderer.render_screen(CockpitTab.APPROVALS, {'approvals': []})
    assert 'Pending Approvals' in output

    # Test costs tab
    output = renderer.render_screen(CockpitTab.COSTS, {'costs': []})
    assert 'Cost Allocation' in output

    # Test memory tab
    output = renderer.render_screen(CockpitTab.MEMORY, {'memories': []})
    assert 'Memory Registry' in output

    # Test background tab
    output = renderer.render_screen(CockpitTab.BACKGROUND, {'background_runs': []})
    assert 'Background Runs' in output


def test_cockpit_tab_enum():
    """Test the CockpitTab enum."""
    assert CockpitTab.WORKFLOWS.value == 'workflows'
    assert CockpitTab.APPROVALS.value == 'approvals'
    assert CockpitTab.COSTS.value == 'costs'
    assert CockpitTab.MEMORY.value == 'memory'
    assert CockpitTab.BACKGROUND.value == 'background'


def test_cockpit_screen_config():
    """Test the CockpitScreenConfig dataclass."""
    config = CockpitScreenConfig(
        current_tab=CockpitTab.APPROVALS, width=120, height=30, show_help=False
    )
    assert config.current_tab == CockpitTab.APPROVALS
    assert config.width == 120
    assert config.height == 30
    assert not config.show_help


def test_create_cockpit_renderer_factory():
    """Test the factory function."""
    renderer = create_cockpit_renderer()
    assert isinstance(renderer, CockpitScreenRenderer)
    assert isinstance(renderer.config, CockpitScreenConfig)
