from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from teaagent.budget import RunBudget

logger = logging.getLogger(__name__)


class BudgetAction(str, Enum):
    """Action suggested by the budget monitor at threshold crossings."""

    NONE = 'none'
    WARN = 'warn'
    PROMPT_CONFIRM = 'prompt_confirm'
    SUGGEST_READ_ONLY = 'suggest_read_only'


_ACTION_ORDER: dict[BudgetAction, int] = {
    BudgetAction.NONE: 0,
    BudgetAction.WARN: 1,
    BudgetAction.PROMPT_CONFIRM: 2,
    BudgetAction.SUGGEST_READ_ONLY: 3,
}


def _action_priority(action: BudgetAction) -> int:
    return _ACTION_ORDER.get(action, 0)


@dataclass
class BudgetMonitor:
    """Emits proactive warnings at configured budget thresholds.

    Thresholds: 50 %, 80 %, 90 %, 100 %
    - 50 %: log warning + optional TUI status callback
    - 80 %: log warning + optional TUI status callback
    - 90 %: prompt user for confirmation (if interactive); cancel otherwise
    - 100 %: suggest switching to read-only mode

    Callbacks accept payloads matching the existing ``BudgetPromptHandler``
    signature so that existing integration points continue to work.
    """

    budget: RunBudget
    thresholds: tuple[float, ...] = (50.0, 80.0, 90.0, 100.0)
    interactive: bool = True

    on_status: Optional[Callable[[str], None]] = None
    on_prompt: Optional[Callable[[dict[str, Any]], bool]] = None

    _emitted_levels: set[int] = field(default_factory=set)
    _prompted: bool = False

    @classmethod
    def from_env(cls, budget: RunBudget) -> 'BudgetMonitor':
        """Create a ``BudgetMonitor`` respecting environment variables.

        Non-interactive when ``TEAAGENT_NO_SUMMARY=1`` or
        ``TEAAGENT_INTERACTIVE=0``.  The ``--no-summary`` CLI flag and
        the TUI both set these variables before constructing the runner.
        """
        interactive = (
            os.environ.get('TEAAGENT_NO_SUMMARY', '').lower()
            not in ('1', 'true', 'yes')
            and os.environ.get('TEAAGENT_INTERACTIVE', '').lower() != '0'
        )
        return cls(budget=budget, interactive=interactive)

    def check(self, *, run_id: str, cost_cents: float) -> BudgetAction:
        """Check budget consumption and return the highest-priority action.

        Returns ``BudgetAction.NONE`` when no new threshold was crossed.
        Each threshold fires at most once per monitor instance (idempotent).
        """
        max_cost = float(self.budget.max_estimated_cost_cents)
        if max_cost <= 0:
            return BudgetAction.NONE

        percent = (cost_cents / max_cost) * 100.0
        highest_action = BudgetAction.NONE

        for level in sorted(self.thresholds):
            if percent < level or int(level) in self._emitted_levels:
                continue

            self._emitted_levels.add(int(level))
            action = self._handle_threshold(
                level=int(level),
                percent=percent,
                cost_cents=cost_cents,
                max_cost=max_cost,
                run_id=run_id,
            )
            if _action_priority(action) > _action_priority(highest_action):
                highest_action = action

        return highest_action

    def check_at_threshold(
        self, *, run_id: str, cost_cents: float, threshold: int
    ) -> BudgetAction:
        """Force-check a specific threshold (useful in tests)."""
        max_cost = float(self.budget.max_estimated_cost_cents)
        if max_cost <= 0:
            return BudgetAction.NONE
        percent = (cost_cents / max_cost) * 100.0
        if threshold not in self._emitted_levels:
            self._emitted_levels.add(threshold)
            return self._handle_threshold(
                level=threshold,
                percent=percent,
                cost_cents=cost_cents,
                max_cost=max_cost,
                run_id=run_id,
            )
        return BudgetAction.NONE

    def reset(self) -> None:
        """Reset emitted tracking for a new run re-using the monitor."""
        self._emitted_levels.clear()
        self._prompted = False

    def _handle_threshold(
        self,
        *,
        level: int,
        percent: float,
        cost_cents: float,
        max_cost: float,
        run_id: str,
    ) -> BudgetAction:
        logger.warning(
            'Budget at %.0f%%: %.1fc / %.0fc (run_id=%s)',
            percent,
            cost_cents,
            max_cost,
            run_id,
        )

        if self.on_status:
            self.on_status(
                f'Budget: {percent:.0f}% ({cost_cents:.1f}c/{max_cost:.0f}c)'
            )

        if level in (50, 80):
            return BudgetAction.WARN

        if level == 90:
            if not self.interactive:
                logger.warning(
                    'Budget at 90%% -- auto-continuing (non-interactive mode)'
                )
                return BudgetAction.WARN
            if self.on_prompt and not self._prompted:
                self._prompted = True
                approved = self.on_prompt(
                    {
                        'run_id': run_id,
                        'percent': percent,
                        'cost_cents': cost_cents,
                        'max_cost_cents': max_cost,
                    }
                )
                if not approved:
                    return BudgetAction.PROMPT_CONFIRM
            return BudgetAction.WARN

        if level >= 100:
            logger.warning(
                'Budget exhausted (%.0f%%). '
                'Consider switching to read-only mode for the remaining session.',
                percent,
            )
            return BudgetAction.SUGGEST_READ_ONLY

        return BudgetAction.NONE
