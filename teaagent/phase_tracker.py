from __future__ import annotations

from dataclasses import dataclass, field

from teaagent.budget import Phase


@dataclass
class PhaseTracker:
    """Tracks phase transitions and per-phase consumption counters.

    The runner thread uses this to keep track of which phase is active and
    how many iterations, tool calls, and cost cents have been consumed within
    each phase since the last transition.
    """

    current_phase: Phase = Phase.PLAN
    _iterations: dict[Phase, int] = field(default_factory=dict)
    _tool_calls: dict[Phase, int] = field(default_factory=dict)
    _cost_start_cents: dict[Phase, float] = field(default_factory=dict)

    def record_iteration(self) -> None:
        phase = self.current_phase
        self._iterations[phase] = self._iterations.get(phase, 0) + 1

    def record_tool_call(self) -> None:
        phase = self.current_phase
        self._tool_calls[phase] = self._tool_calls.get(phase, 0) + 1

    def set_cost_start(self, total_cost_cents: float) -> None:
        """Snapshot the total cost at the start of the current phase."""
        self._cost_start_cents[self.current_phase] = total_cost_cents

    def phase_cost_cents(self, total_cost_cents: float) -> float:
        """Return cost consumed during the current phase."""
        start = self._cost_start_cents.get(self.current_phase, 0.0)
        return max(0.0, total_cost_cents - start)

    def phase_iterations(self) -> int:
        return self._iterations.get(self.current_phase, 0)

    def phase_tool_calls(self) -> int:
        return self._tool_calls.get(self.current_phase, 0)

    def transition(self, new_phase: Phase, total_cost_cents: float = 0.0) -> None:
        self.current_phase = new_phase
        self._iterations[new_phase] = 0
        self._tool_calls[new_phase] = 0
        self._cost_start_cents[new_phase] = total_cost_cents
