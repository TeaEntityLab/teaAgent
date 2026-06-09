"""Control Plane Cockpit screens for H4 Durable Team Operations.

This module provides TUI screens for the operator control plane cockpit,
including workflows, approvals, costs, memory registry, and background
lifecycle management.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class CockpitTab(str, Enum):
    """Tabs available in the control plane cockpit."""

    WORKFLOWS = 'workflows'
    APPROVALS = 'approvals'
    COSTS = 'costs'
    MEMORY = 'memory'
    BACKGROUND = 'background'


@dataclass
class CockpitScreenConfig:
    """Configuration for cockpit screen rendering."""

    current_tab: CockpitTab = CockpitTab.WORKFLOWS
    width: int = 80
    height: int = 24
    show_help: bool = True


@dataclass
class WorkflowRow:
    """A single workflow row for the workflows screen."""

    tenant: str
    workflow_id: str
    status: str
    cost_cents: float
    progress: Optional[float] = None


@dataclass
class ApprovalRow:
    """A single approval row for the approvals screen."""

    tenant: str
    workflow_id: str
    action_id: str
    description: str
    required_consensus: str
    current_approvals: int
    status: str


@dataclass
class CostRow:
    """A single cost row for the costs screen."""

    tenant: str
    workflow_id: Optional[str]
    spent_cents: float
    limit_cents: Optional[float]
    period: str


@dataclass
class MemoryRow:
    """A single memory row for the memory registry screen."""

    memory_id: str
    scope: str
    source: str
    confidence: str
    content_preview: str
    quarantined: bool = False


@dataclass
class BackgroundRow:
    """A single background run row for the background lifecycle screen."""

    run_id: str
    status: str
    progress: float
    cost_cents: float
    can_attach: bool = False
    can_resume: bool = False
    can_stop: bool = False


class CockpitScreenRenderer:
    """Renderer for control plane cockpit screens."""

    def __init__(self, config: Optional[CockpitScreenConfig] = None) -> None:
        self.config = config or CockpitScreenConfig()

    def render_header(self) -> str:
        """Render the cockpit header with tab navigation."""
        tabs = [
            ('[Workflows]', self.config.current_tab == CockpitTab.WORKFLOWS),
            ('[Approvals]', self.config.current_tab == CockpitTab.APPROVALS),
            ('[Costs]', self.config.current_tab == CockpitTab.COSTS),
            ('[Memory]', self.config.current_tab == CockpitTab.MEMORY),
            ('[Background]', self.config.current_tab == CockpitTab.BACKGROUND),
        ]

        tab_line = ' '.join(f'*{tab[0]}*' if tab[1] else tab[0] for tab in tabs)

        header = f"""
┌─────────────────────────────────────────────────────────────┐
│ TeaAgent Control Plane Cockpit                              │
├─────────────────────────────────────────────────────────────┤
│ {tab_line:<65}│
├─────────────────────────────────────────────────────────────┤
"""
        return header

    def render_workflows_screen(
        self, workflows: list[WorkflowRow], tenant_filter: Optional[str] = None
    ) -> str:
        """Render the workflows screen."""
        # Apply tenant filter if specified
        if tenant_filter:
            workflows = [w for w in workflows if w.tenant == tenant_filter]

        # Build table header
        table = f"""
│ Active Workflows ({len(workflows)} total)                     │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ {'Tenant':<15} │ {'Workflow':<12} │ {'Status':<8} │ {'Cost':<10} ││
│ ├─────────────────────────────────────────────────────────┤│
"""

        # Build table rows
        for workflow in workflows[:10]:  # Show first 10
            cost_str = f'${workflow.cost_cents / 100:.2f}'
            table += f"""│ │ {workflow.tenant:<15} │ {workflow.workflow_id:<12} │ {workflow.status:<8} │ {cost_str:<10} ││
"""

        if len(workflows) > 10:
            remaining = len(workflows) - 10
            table += f"""│ │ ... and {remaining} more workflows                              ││
"""

        table += """│ └─────────────────────────────────────────────────────────┘│
│ [F]ilter by tenant  [A]ttach to workflow  [V]iew details   │
└─────────────────────────────────────────────────────────────┘
"""

        return self.render_header() + table

    def render_approvals_screen(
        self, approvals: list[ApprovalRow], tenant_filter: Optional[str] = None
    ) -> str:
        """Render the approvals screen."""
        # Apply tenant filter if specified
        if tenant_filter:
            approvals = [a for a in approvals if a.tenant == tenant_filter]

        # Build table header
        table = f"""
│ Pending Approvals ({len(approvals)} total)                     │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ {'Tenant':<15} │ {'Action':<20} │ {'Consensus':<12} │ {'Status':<8} ││
│ ├─────────────────────────────────────────────────────────┤│
"""

        # Build table rows
        for approval in approvals[:10]:  # Show first 10
            consensus_str = (
                f'{approval.current_approvals}/{approval.required_consensus}'
            )
            table += f"""│ │ {approval.tenant:<15} │ {approval.description[:20]:<20} │ {consensus_str:<12} │ {approval.status:<8} ││
"""

        if len(approvals) > 10:
            remaining = len(approvals) - 10
            table += f"""│ │ ... and {remaining} more approvals                              ││
"""

        table += """│ └─────────────────────────────────────────────────────────┘│
│ [A]pprove  [R]eject  [F]ilter by tenant  [V]iew details   │
└─────────────────────────────────────────────────────────────┘
"""

        return self.render_header() + table

    def render_costs_screen(
        self, costs: list[CostRow], tenant_filter: Optional[str] = None
    ) -> str:
        """Render the costs screen."""
        # Apply tenant filter if specified
        if tenant_filter:
            costs = [c for c in costs if c.tenant == tenant_filter]

        # Build table header
        table = f"""
│ Cost Allocation ({len(costs)} entries)                     │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ {'Tenant':<15} │ {'Workflow':<12} │ {'Spent':<10} │ {'Limit':<10} ││
│ ├─────────────────────────────────────────────────────────┤│
"""

        # Build table rows
        for cost in costs[:10]:  # Show first 10
            spent_str = f'${cost.spent_cents / 100:.2f}'
            limit_str = (
                f'${cost.limit_cents / 100:.2f}' if cost.limit_cents else 'unlimited'
            )
            workflow_str = cost.workflow_id[:12] if cost.workflow_id else 'N/A'
            table += f"""│ │ {cost.tenant:<15} │ {workflow_str:<12} │ {spent_str:<10} │ {limit_str:<10} ││
"""

        if len(costs) > 10:
            remaining = len(costs) - 10
            table += f"""│ │ ... and {remaining} more cost entries                             ││
"""

        table += """│ └─────────────────────────────────────────────────────────┘│
│ [F]ilter by tenant  [S]et budget alert  [E]xport report   │
└─────────────────────────────────────────────────────────────┘
"""

        return self.render_header() + table

    def render_memory_screen(
        self, memories: list[MemoryRow], scope_filter: Optional[str] = None
    ) -> str:
        """Render the memory registry screen."""
        # Apply scope filter if specified
        if scope_filter:
            memories = [m for m in memories if m.scope == scope_filter]

        # Build table header
        table = f"""
│ Memory Registry ({len(memories)} entries)                     │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ {'ID':<12} │ {'Scope':<10} │ {'Source':<10} │ {'Confidence':<12} │ {'Q':<2} ││
│ ├─────────────────────────────────────────────────────────┤│
"""

        # Build table rows
        for memory in memories[:10]:  # Show first 10
            quarantined_str = 'Y' if memory.quarantined else 'N'
            table += f"""│ │ {memory.memory_id[:12]:<12} │ {memory.scope:<10} │ {memory.source:<10} │ {memory.confidence:<12} │ {quarantined_str:<2} ││
"""

        if len(memories) > 10:
            remaining = len(memories) - 10
            table += f"""│ │ ... and {remaining} more memory entries                           ││
"""

        table += """│ └─────────────────────────────────────────────────────────┘│
│ [F]ilter by scope  [V]iew content  [Q]uarantine management │
└─────────────────────────────────────────────────────────────┘
"""

        return self.render_header() + table

    def render_background_screen(
        self, background_runs: list[BackgroundRow], status_filter: Optional[str] = None
    ) -> str:
        """Render the background lifecycle screen."""
        # Apply status filter if specified
        if status_filter:
            background_runs = [b for b in background_runs if b.status == status_filter]

        # Build table header
        table = f"""
│ Background Runs ({len(background_runs)} total)                     │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ {'Run ID':<12} │ {'Status':<10} │ {'Progress':<10} │ {'Cost':<10} │ {'Action':<10} ││
│ ├─────────────────────────────────────────────────────────┤│
"""

        # Build table rows
        for run in background_runs[:10]:  # Show first 10
            progress_str = f'{run.progress * 100:.1f}%'
            cost_str = f'${run.cost_cents / 100:.2f}'

            # Determine available actions
            actions = []
            if run.can_attach:
                actions.append('Attach')
            elif run.can_resume:
                actions.append('Resume')
            elif run.can_stop:
                actions.append('Stop')
            else:
                actions.append('View')

            action_str = '/'.join(actions)[:10]
            table += f"""│ │ {run.run_id[:12]:<12} │ {run.status:<10} │ {progress_str:<10} │ {cost_str:<10} │ {action_str:<10} ││
"""

        if len(background_runs) > 10:
            remaining = len(background_runs) - 10
            table += f"""│ │ ... and {remaining} more background runs                         ││
"""

        table += """│ └─────────────────────────────────────────────────────────┘│
│ [F]ilter by status  [A]ttach  [R]esume  [S]top  [V]iew logs  │
└─────────────────────────────────────────────────────────────┘
"""

        return self.render_header() + table

    def render_screen(
        self,
        current_tab: CockpitTab,
        data: dict[str, Any],
        filter_value: Optional[str] = None,
    ) -> str:
        """Render the current screen based on tab and data."""
        self.config.current_tab = current_tab

        if current_tab == CockpitTab.WORKFLOWS:
            workflows = data.get('workflows', [])
            return self.render_workflows_screen(workflows, filter_value)
        elif current_tab == CockpitTab.APPROVALS:
            approvals = data.get('approvals', [])
            return self.render_approvals_screen(approvals, filter_value)
        elif current_tab == CockpitTab.COSTS:
            costs = data.get('costs', [])
            return self.render_costs_screen(costs, filter_value)
        elif current_tab == CockpitTab.MEMORY:
            memories = data.get('memories', [])
            return self.render_memory_screen(memories, filter_value)
        elif current_tab == CockpitTab.BACKGROUND:
            background_runs = data.get('background_runs', [])
            return self.render_background_screen(background_runs, filter_value)
        else:
            return (
                self.render_header()
                + '│ Unknown tab                                                │\n└─────────────────────────────────────────────────────────────┘\n'
            )


def create_cockpit_renderer() -> CockpitScreenRenderer:
    """Factory function to create a cockpit screen renderer."""
    return CockpitScreenRenderer()
