from __future__ import annotations

from dataclasses import dataclass

from teaagent.errors import BudgetExceededError
from teaagent.llm import estimate_cost_preflight


@dataclass(frozen=True)
class RunBudget:
    max_iterations: int = 25
    max_tool_calls: int = 25
    max_estimated_cost_cents: int = 100

    def validate(self) -> None:
        if self.max_iterations < 1:
            raise ValueError('max_iterations must be >= 1')
        if self.max_tool_calls < 0:
            raise ValueError('max_tool_calls must be >= 0')
        if self.max_estimated_cost_cents < 0:
            raise ValueError('max_estimated_cost_cents must be >= 0')

    def check_cost_preflight(
        self,
        provider: str,
        model: str,
        approx_input_chars: int,
        max_output_tokens: int,
    ) -> None:
        estimated = estimate_cost_preflight(
            provider, model, approx_input_chars, max_output_tokens
        )
        if estimated > self.max_estimated_cost_cents:
            raise BudgetExceededError(
                f'pre-flight cost estimate {estimated:.2f}c exceeds budget '
                f'{self.max_estimated_cost_cents}c'
            )
