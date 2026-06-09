"""Data sources for control plane cockpit screens.

This module provides data fetching and transformation for the various
cockpit screens, integrating with existing TeaAgent data stores.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from teaagent.run_store import RunStore, RunSummary

from .cockpit_screens import (
    ApprovalRow,
    BackgroundRow,
    CostRow,
    MemoryRow,
    WorkflowRow,
)


class WorkflowDataSource:
    """Data source for workflows screen.

    Fetches workflow data from the RunStore and converts it to
    WorkflowRow objects for display in the cockpit.
    """

    def __init__(self, root: str | Path, tenant_id: str = 'default') -> None:
        """Initialize the workflow data source.

        Args:
            root: Workspace root directory.
            tenant_id: Tenant ID for multi-tenant scenarios.
        """
        self.root = Path(root).resolve()
        self.tenant_id = tenant_id
        self._run_store = RunStore(self.root, tenant_id=tenant_id, readonly=True)

    def get_workflows(
        self,
        *,
        limit: int = 20,
        status_filter: Optional[str] = None,
        tenant_filter: Optional[str] = None,
    ) -> list[WorkflowRow]:
        """Get workflow data for the cockpit screen.

        Args:
            limit: Maximum number of workflows to return.
            status_filter: Optional status filter (e.g., 'running', 'pending').
            tenant_filter: Optional tenant filter for multi-tenant scenarios.

        Returns:
            List of WorkflowRow objects.
        """
        # Apply tenant filter if specified
        if tenant_filter and tenant_filter != self.tenant_id:
            # For multi-tenant scenarios, we'd need to query multiple stores
            # For now, just return empty if tenant doesn't match
            return []

        # Get runs from the store
        summaries = self._run_store.list_runs(limit=limit)

        # Convert to WorkflowRow objects
        workflows = []
        for summary in summaries:
            # Apply status filter if specified
            if status_filter and summary.status != status_filter:
                continue

            workflow = WorkflowRow(
                tenant=self.tenant_id,
                workflow_id=summary.run_id,
                status=summary.status,
                cost_cents=summary.cost_cents,
            )
            workflows.append(workflow)

        return workflows

    def get_workflow_count(self, *, status_filter: Optional[str] = None) -> int:
        """Get the total count of workflows.

        Args:
            status_filter: Optional status filter.

        Returns:
            Total count of workflows.
        """
        summaries = self._run_store.list_runs(limit=1000)  # Get all for counting
        if status_filter:
            return sum(1 for s in summaries if s.status == status_filter)
        return len(summaries)


class CostDataSource:
    """Data source for costs screen.

    Fetches cost data from the RunStore and converts it to
    CostRow objects for display in the cockpit.
    """

    def __init__(
        self,
        root: str | Path,
        tenant_id: str = 'default',
        budget_limit_cents: Optional[int] = None,
    ) -> None:
        """Initialize the cost data source.

        Args:
            root: Workspace root directory.
            tenant_id: Tenant ID for multi-tenant scenarios.
            budget_limit_cents: Optional budget limit in cents.
        """
        self.root = Path(root).resolve()
        self.tenant_id = tenant_id
        self.budget_limit_cents = budget_limit_cents
        self._run_store = RunStore(self.root, tenant_id=tenant_id, readonly=True)

    def get_costs(
        self,
        *,
        limit: int = 20,
        tenant_filter: Optional[str] = None,
    ) -> list[CostRow]:
        """Get cost data for the cockpit screen.

        Args:
            limit: Maximum number of cost entries to return.
            tenant_filter: Optional tenant filter for multi-tenant scenarios.

        Returns:
            List of CostRow objects.
        """
        # Apply tenant filter if specified
        if tenant_filter and tenant_filter != self.tenant_id:
            return []

        # Get runs from the store
        summaries = self._run_store.list_runs(limit=limit)

        # Convert to CostRow objects
        costs = []
        for summary in summaries:
            cost = CostRow(
                tenant=self.tenant_id,
                workflow_id=summary.run_id,
                spent_cents=summary.cost_cents,
                limit_cents=self.budget_limit_cents,
                period='today',  # TODO: Calculate actual period from timestamps
            )
            costs.append(cost)

        return costs

    def get_total_cost(self, *, tenant_filter: Optional[str] = None) -> float:
        """Get the total cost across all workflows.

        Args:
            tenant_filter: Optional tenant filter.

        Returns:
            Total cost in cents.
        """
        summaries = self._run_store.list_runs(limit=1000)
        if tenant_filter and tenant_filter != self.tenant_id:
            return 0.0
        return sum(s.cost_cents for s in summaries)

    def get_cost_trends(self, *, days: int = 7) -> list[dict[str, Any]]:
        """Get cost trends over time.

        Args:
            days: Number of days to analyze.

        Returns:
            List of daily cost summaries.
        """
        summaries = self._run_store.list_runs(limit=1000)

        # Group costs by day (simplified - uses updated_at timestamps)
        daily_costs = {}
        for summary in summaries:
            # Extract date from timestamp (simplified)
            date_str = (
                summary.updated_at[:10] if len(summary.updated_at) >= 10 else 'unknown'
            )
            if date_str not in daily_costs:
                daily_costs[date_str] = 0.0
            daily_costs[date_str] += summary.cost_cents

        # Convert to sorted list
        trends = [
            {'date': date, 'cost_cents': cost}
            for date, cost in sorted(daily_costs.items())
        ]

        return trends[-days:]  # Return last N days

    def get_budget_status(self) -> dict[str, Any]:
        """Get budget status including alerts.

        Returns:
            Dictionary with budget status information.
        """
        total_cost = self.get_total_cost()

        if self.budget_limit_cents is None:
            return {
                'status': 'unlimited',
                'spent_cents': total_cost,
                'limit_cents': None,
                'remaining_cents': None,
                'usage_percentage': 0.0,
                'alert_level': 'none',
            }

        remaining_cents = self.budget_limit_cents - total_cost
        usage_percentage = (
            (total_cost / self.budget_limit_cents) * 100
            if self.budget_limit_cents > 0
            else 0.0
        )

        # Determine alert level
        if usage_percentage >= 100:
            alert_level = 'critical'
            status = 'exceeded'
        elif usage_percentage >= 90:
            alert_level = 'warning'
            status = 'warning'
        elif usage_percentage >= 75:
            alert_level = 'info'
            status = 'ok'
        else:
            alert_level = 'none'
            status = 'ok'

        return {
            'status': status,
            'spent_cents': total_cost,
            'limit_cents': self.budget_limit_cents,
            'remaining_cents': max(0, remaining_cents),
            'usage_percentage': usage_percentage,
            'alert_level': alert_level,
        }


class MemoryDataSource:
    """Data source for memory registry screen.

    Fetches memory data from the MemoryCatalog and converts it to
    MemoryRow objects for display in the cockpit.
    """

    def __init__(self, root: str | Path, tenant_id: str = 'default') -> None:
        """Initialize the memory data source.

        Args:
            root: Workspace root directory.
            tenant_id: Tenant ID for multi-tenant scenarios.
        """
        self.root = Path(root).resolve()
        self.tenant_id = tenant_id

    def get_memories(
        self,
        *,
        limit: int = 20,
        scope_filter: Optional[str] = None,
    ) -> list[MemoryRow]:
        """Get memory data for the cockpit screen.

        Args:
            limit: Maximum number of memory entries to return.
            scope_filter: Optional scope filter (e.g., 'workspace', 'project').

        Returns:
            List of MemoryRow objects.
        """
        try:
            from teaagent.memory import MemoryCatalog

            catalog = MemoryCatalog(self.root, readonly=True)
            entries = catalog.list(limit=limit)

            # Convert to MemoryRow objects
            memories = []
            for entry in entries:
                # Apply scope filter if specified
                scope = (
                    entry.meta.scope if (entry.meta and entry.meta.scope) else 'auto'
                )
                if scope_filter and scope != scope_filter:
                    continue

                # Extract source and confidence
                source = (
                    entry.meta.owner if entry.meta else 'unknown'
                )  # Owner acts as source
                confidence_value = entry.meta.confidence if entry.meta else 0.0

                # Convert confidence to descriptive label
                if confidence_value >= 0.8:
                    confidence = 'high'
                elif confidence_value >= 0.5:
                    confidence = 'medium'
                else:
                    confidence = 'low'

                # Check quarantine status
                review_state = entry.meta.review_state if entry.meta else 'pending'
                quarantined = review_state == 'quarantined'

                memory = MemoryRow(
                    memory_id=entry.memory_id,
                    scope=scope,
                    source=source,
                    confidence=confidence,
                    content_preview=entry.content[:80],
                    quarantined=quarantined,
                )
                memories.append(memory)

            return memories
        except Exception:
            return []

    def get_memory_count(self, *, scope_filter: Optional[str] = None) -> int:
        """Get the total count of memory entries.

        Args:
            scope_filter: Optional scope filter.

        Returns:
            Total count of memory entries.
        """
        try:
            from teaagent.memory import MemoryCatalog

            catalog = MemoryCatalog(self.root, readonly=True)
            entries = catalog.list(limit=1000)

            if scope_filter:
                count = 0
                for entry in entries:
                    if entry.meta and entry.meta.scope == scope_filter:
                        count += 1
                return count
            return len(entries)
        except Exception:
            return 0

    def get_quarantined_memory_count(self) -> int:
        """Get the count of quarantined memory entries.

        Returns:
            Count of quarantined memory entries.
        """
        try:
            from teaagent.memory import MemoryCatalog

            catalog = MemoryCatalog(self.root, readonly=True)
            entries = catalog.list(limit=1000)

            count = 0
            for entry in entries:
                if entry.meta and entry.meta.review_state == 'quarantined':
                    count += 1
            return count
        except Exception:
            return 0


class ApprovalDataSource:
    """Data source for approvals screen.

    Fetches approval data from the approval system and converts it to
    ApprovalRow objects for display in the cockpit.
    """

    def __init__(self, root: str | Path, tenant_id: str = 'default') -> None:
        """Initialize the approval data source.

        Args:
            root: Workspace root directory.
            tenant_id: Tenant ID for multi-tenant scenarios.
        """
        self.root = Path(root).resolve()
        self.tenant_id = tenant_id

    def get_approvals(
        self,
        *,
        limit: int = 20,
        tenant_filter: Optional[str] = None,
    ) -> list[ApprovalRow]:
        """Get approval data for the cockpit screen.

        Args:
            limit: Maximum number of approvals to return.
            tenant_filter: Optional tenant filter for multi-tenant scenarios.

        Returns:
            List of ApprovalRow objects.
        """
        # Apply tenant filter if specified
        if tenant_filter and tenant_filter != self.tenant_id:
            return []

        approvals = []

        # Get memory quarantine approvals (pending/quarantined memory entries)
        try:
            from teaagent.memory import MemoryCatalog

            catalog = MemoryCatalog(self.root, readonly=True)
            entries = catalog.list(limit=100)  # Get more for filtering

            for entry in entries:
                # Check if entry has pending or quarantined review state
                review_state = entry.meta.review_state if entry.meta else 'pending'

                if review_state in ['pending', 'quarantined']:
                    approval = ApprovalRow(
                        tenant=self.tenant_id,
                        workflow_id=entry.meta.source_run_id
                        if (entry.meta and entry.meta.source_run_id)
                        else 'unknown',
                        action_id=entry.memory_id,
                        description=f'Memory entry: {entry.content[:40]}...',
                        required_consensus='1-of-1',  # Memory approvals are single-user
                        current_approvals=0,  # No approvals yet
                        status=review_state,
                    )
                    approvals.append(approval)

                    if len(approvals) >= limit:
                        break

        except Exception:
            # If memory catalog fails, continue with other sources
            pass

        # Get quarantine line count (from cockpit.py logic)
        try:
            quarantine_path = self.root / '.teaagent' / 'memory-quarantine.jsonl'
            if quarantine_path.is_file():
                quarantine_lines = len(
                    quarantine_path.read_text(encoding='utf-8').splitlines()
                )
                if quarantine_lines > 0:
                    # Add a summary approval for quarantine items
                    approval = ApprovalRow(
                        tenant=self.tenant_id,
                        workflow_id='quarantine',
                        action_id='quarantine-review',
                        description=f'{quarantine_lines} quarantined memory items',
                        required_consensus='1-of-1',
                        current_approvals=0,
                        status='pending',
                    )
                    approvals.append(approval)
        except Exception:
            pass

        return approvals

    def get_approval_count(self) -> int:
        """Get the total count of pending approvals.

        Returns:
            Total count of pending approvals.
        """
        try:
            # Count quarantine lines
            quarantine_path = self.root / '.teaagent' / 'memory-quarantine.jsonl'
            if quarantine_path.is_file():
                quarantine_lines = len(
                    quarantine_path.read_text(encoding='utf-8').splitlines()
                )
            else:
                quarantine_lines = 0

            # Count pending memory entries
            from teaagent.memory import MemoryCatalog

            catalog = MemoryCatalog(self.root, readonly=True)
            entries = catalog.list(limit=1000)

            pending_memory = 0
            for entry in entries:
                if entry.meta and entry.meta.review_state in ['pending', 'quarantined']:
                    pending_memory += 1

            return quarantine_lines + pending_memory

        except Exception:
            return 0


class BackgroundDataSource:
    """Data source for background lifecycle screen.

    Fetches background run data and converts it to
    BackgroundRow objects for display in the cockpit.
    """

    def __init__(self, root: str | Path, tenant_id: str = 'default') -> None:
        """Initialize the background data source.

        Args:
            root: Workspace root directory.
            tenant_id: Tenant ID for multi-tenant scenarios.
        """
        self.root = Path(root).resolve()
        self.tenant_id = tenant_id
        self._run_store = RunStore(self.root, tenant_id=tenant_id, readonly=True)

    def get_background_runs(
        self,
        *,
        limit: int = 20,
        status_filter: Optional[str] = None,
        tenant_filter: Optional[str] = None,
    ) -> list[BackgroundRow]:
        """Get background run data for the cockpit screen.

        Args:
            limit: Maximum number of background runs to return.
            status_filter: Optional status filter (e.g., 'running', 'suspended').
            tenant_filter: Optional tenant filter for multi-tenant scenarios.

        Returns:
            List of BackgroundRow objects.
        """
        # Apply tenant filter if specified
        if tenant_filter and tenant_filter != self.tenant_id:
            return []

        # Get runs from the store
        summaries = self._run_store.list_runs(limit=limit)

        # Convert to BackgroundRow objects
        background_runs = []
        for summary in summaries:
            # Apply status filter if specified
            if status_filter and summary.status != status_filter:
                continue

            # Determine if the run is background/resumable
            is_background = summary.resumable or summary.status in [
                'paused',
                'suspended',
                'running',
            ]
            if not is_background:
                continue

            # Calculate progress based on status
            progress = self._calculate_progress(summary)

            # Determine available actions
            can_attach = summary.resumable
            can_resume = summary.status in ['paused', 'suspended']
            can_stop = summary.status in ['running', 'paused', 'suspended']

            background_run = BackgroundRow(
                run_id=summary.run_id,
                status=summary.status,
                progress=progress,
                cost_cents=summary.cost_cents,
                can_attach=can_attach,
                can_resume=can_resume,
                can_stop=can_stop,
            )
            background_runs.append(background_run)

        return background_runs

    def _calculate_progress(self, summary: RunSummary) -> float:
        """Calculate progress estimate for a background run.

        Args:
            summary: Run summary to calculate progress for.

        Returns:
            Progress estimate between 0.0 and 1.0.
        """
        # Simple progress estimation based on status
        if summary.status == 'completed':
            return 1.0
        elif summary.status == 'failed':
            return 0.0
        elif summary.status in ['paused', 'suspended']:
            return 0.5  # Assume halfway if paused
        elif summary.status == 'running':
            return 0.75  # Assume mostly complete if still running
        else:
            return 0.0

    def get_background_run_count(self, *, status_filter: Optional[str] = None) -> int:
        """Get the total count of background runs.

        Args:
            status_filter: Optional status filter.

        Returns:
            Total count of background runs.
        """
        summaries = self._run_store.list_runs(limit=1000)
        count = 0
        for summary in summaries:
            is_background = summary.resumable or summary.status in [
                'paused',
                'suspended',
                'running',
            ]
            if is_background:
                if status_filter and summary.status != status_filter:
                    continue
                count += 1
        return count

    def get_background_run_status(self, run_id: str) -> Optional[dict[str, Any]]:
        """Get detailed status for a specific background run.

        Args:
            run_id: Run ID to get status for.

        Returns:
            Dictionary with run status details, or None if not found.
        """
        try:
            summaries = self._run_store.list_runs(limit=1000)
            for summary in summaries:
                if summary.run_id == run_id:
                    return {
                        'run_id': summary.run_id,
                        'status': summary.status,
                        'task': summary.task,
                        'cost_cents': summary.cost_cents,
                        'created_at': summary.created_at,
                        'updated_at': summary.updated_at,
                        'resumable': summary.resumable,
                        'progress': self._calculate_progress(summary),
                    }
            return None
        except Exception:
            return None


class CockpitDataManager:
    """Manager for all cockpit data sources.

    Provides a unified interface for fetching data for all cockpit screens.
    """

    def __init__(
        self,
        root: str | Path,
        tenant_id: str = 'default',
        budget_limit_cents: Optional[int] = None,
    ) -> None:
        """Initialize the cockpit data manager.

        Args:
            root: Workspace root directory.
            tenant_id: Tenant ID for multi-tenant scenarios.
            budget_limit_cents: Optional budget limit in cents for cost tracking.
        """
        self.root = Path(root).resolve()
        self.tenant_id = tenant_id
        self._workflow_source = WorkflowDataSource(self.root, tenant_id)
        self._cost_source = CostDataSource(self.root, tenant_id, budget_limit_cents)
        self._memory_source = MemoryDataSource(self.root, tenant_id)
        self._approval_source = ApprovalDataSource(self.root, tenant_id)
        self._background_source = BackgroundDataSource(self.root, tenant_id)

    def get_all_data(self, *, limit: int = 20) -> dict[str, Any]:
        """Get data for all cockpit screens.

        Args:
            limit: Maximum number of entries per screen.

        Returns:
            Dictionary with data for all screens.
        """
        return {
            'workflows': self._workflow_source.get_workflows(limit=limit),
            'costs': self._cost_source.get_costs(limit=limit),
            'memories': self._memory_source.get_memories(limit=limit),
            'approvals': self._approval_source.get_approvals(limit=limit),
            'background_runs': self._background_source.get_background_runs(limit=limit),
        }

    def get_workflows(self, **kwargs: Any) -> list[WorkflowRow]:
        """Get workflow data."""
        return self._workflow_source.get_workflows(**kwargs)

    def get_costs(self, **kwargs: Any) -> list[CostRow]:
        """Get cost data."""
        return self._cost_source.get_costs(**kwargs)

    def get_memories(self, **kwargs: Any) -> list[MemoryRow]:
        """Get memory data."""
        return self._memory_source.get_memories(**kwargs)

    def get_approvals(self, **kwargs: Any) -> list[ApprovalRow]:
        """Get approval data."""
        return self._approval_source.get_approvals(**kwargs)

    def get_background_runs(self, **kwargs: Any) -> list[BackgroundRow]:
        """Get background run data."""
        return self._background_source.get_background_runs(**kwargs)
