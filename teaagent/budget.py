from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from teaagent.errors import BudgetExceededError
from teaagent.llm import estimate_cost_preflight


class Phase(str, Enum):
    """Phases of the SCL (Specify-Construct-Learn) agent loop."""

    PLAN = 'plan'
    EXECUTE = 'execute'
    REVIEW = 'review'
    SYNTHESIS = 'synthesis'


@dataclass(frozen=True)
class PhaseBudget:
    """Budget caps for a specific phase of the agent run.

    When a phase budget is configured, the runner enforces these limits
    independently of the overall ``RunBudget``.  Any field set to ``None``
    inherits the corresponding overall budget field at enforcement time.
    """

    phase: Phase
    max_iterations: int
    max_tool_calls: int
    max_estimated_cost_cents: int | None = None


@dataclass(frozen=True)
class RunBudget:
    """Hard limits for a single agent run.

    The runner checks these on every iteration.  When any limit is exceeded
    a ``BudgetExceededError`` is raised.

    Phase-level budgets (``phase_budgets``) are checked before the overall
    budget.  When a phase has no configured budget the overall defaults apply.
    """

    max_iterations: int = 25
    max_tool_calls: int = 25
    max_estimated_cost_cents: int | None = 500
    phase_budgets: dict[Phase, PhaseBudget] = field(default_factory=dict)

    def validate(self) -> None:
        if self.max_iterations < 1:
            raise ValueError('max_iterations must be >= 1')
        if self.max_tool_calls < 0:
            raise ValueError('max_tool_calls must be >= 0')
        if (
            self.max_estimated_cost_cents is not None
            and self.max_estimated_cost_cents < 0
        ):
            raise ValueError('max_estimated_cost_cents must be >= 0')
        for pb in self.phase_budgets.values():
            if pb.max_iterations < 1:
                raise ValueError(
                    f'max_iterations must be >= 1 for phase {pb.phase.value}'
                )
            if pb.max_tool_calls < 0:
                raise ValueError(
                    f'max_tool_calls must be >= 0 for phase {pb.phase.value}'
                )
            if (
                pb.max_estimated_cost_cents is not None
                and pb.max_estimated_cost_cents < 0
            ):
                raise ValueError(
                    f'max_estimated_cost_cents must be >= 0 for phase {pb.phase.value}'
                )

    def check_cost_preflight(
        self,
        provider: str,
        model: str,
        approx_input_chars: int,
        max_output_tokens: int,
    ) -> None:
        if self.max_estimated_cost_cents is None:
            return
        estimated = estimate_cost_preflight(
            provider, model, approx_input_chars, max_output_tokens
        )
        if estimated > self.max_estimated_cost_cents:
            raise BudgetExceededError(
                f'pre-flight cost estimate {estimated:.2f}c exceeds budget '
                f'{self.max_estimated_cost_cents}c'
            )

    def phase_budget_for(self, phase: Phase) -> PhaseBudget:
        """Return the phase-specific budget or a fallback from overall defaults.

        When no ``PhaseBudget`` is registered for *phase*, the returned object
        uses the overall ``RunBudget`` limits for every dimension.
        """
        if phase in self.phase_budgets:
            return self.phase_budgets[phase]
        return PhaseBudget(
            phase=phase,
            max_iterations=self.max_iterations,
            max_tool_calls=self.max_tool_calls,
            max_estimated_cost_cents=self.max_estimated_cost_cents,
        )
