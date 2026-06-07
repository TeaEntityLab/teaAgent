"""TUI module — interactive terminal interface for TeaAgent."""

from teaagent.tui.core import TeaAgentTUI
from teaagent.tui.rendering import HELP_TEXT, run_tui
from teaagent.tui.state import (
    AdapterFactory,
    InputFn,
    OutputFn,
    _effort_level_for_budget,
    _format_budget_cents,
    _format_remaining_cents,
    default_adapter_factory,
)

__all__ = [
    'AdapterFactory',
    'HELP_TEXT',
    'InputFn',
    'OutputFn',
    'TeaAgentTUI',
    '_effort_level_for_budget',
    '_format_budget_cents',
    '_format_remaining_cents',
    'default_adapter_factory',
    'run_tui',
]
