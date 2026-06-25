"""CG-16 TUI test boundary helpers — real RunStore/controller, mock LLM only."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from typing import Iterator
from unittest.mock import MagicMock, patch

from teaagent.tui import TeaAgentTUI
from teaagent.types import FinalAnswer, RunResult


def completed_run_result(
    *,
    run_id: str = 'test-run',
    cost_cents: float = 0.0,
    content: str = 'ok',
    iterations: int = 1,
    tool_calls: int = 0,
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> RunResult:
    """Build a completed ``RunResult`` for boundary-patched TUI/controller tests."""
    return RunResult(
        run_id=run_id,
        status='completed',
        iterations=iterations,
        tool_calls=tool_calls,
        cost_cents=cost_cents,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        final_answer=FinalAnswer(content=content),
        metadata={},
        error_message=None,
    )


@contextmanager
def patch_run_chat_agent(
    *,
    run_result: RunResult | None = None,
    patch_show_run: bool = True,
) -> Iterator[MagicMock]:
    """Patch LLM transport boundaries used by controller-backed TUI paths."""
    result = run_result or completed_run_result()
    patches = [
        patch(
            'teaagent.chat_session_controller.run_chat_agent',
            return_value=result,
        ),
        patch('teaagent.tui.state.create_llm_adapter'),
    ]
    if patch_show_run:
        patches.append(patch('teaagent.tui.core.RunStore.show_run', return_value=[]))

    with ExitStack() as stack:
        mock_run = stack.enter_context(patches[0])
        for item in patches[1:]:
            stack.enter_context(item)
        yield mock_run


@contextmanager
def command_path_boundary(
    *,
    run_result: RunResult | None = None,
    patch_show_run: bool = True,
) -> Iterator[None]:
    """Headless command-path boundary without TUI lifecycle patches."""
    with patch_run_chat_agent(
        run_result=run_result,
        patch_show_run=patch_show_run,
    ):
        yield


@contextmanager
def ask_run_patches(
    tui: TeaAgentTUI,
    *,
    run_result: RunResult | None = None,
    patch_show_run: bool = True,
) -> Iterator[None]:
    """Boundary for ask/run/resume command-path tests that spy on the controller."""
    with (
        patch.object(tui, '_start_file_watcher'),
        patch.object(tui, '_load_tui_state'),
        patch.object(tui, '_save_tui_state'),
        command_path_boundary(run_result=run_result, patch_show_run=patch_show_run),
    ):
        yield


@contextmanager
def cost_run_boundary(
    tui: TeaAgentTUI,
    *,
    run_result: RunResult | None = None,
    patch_show_run: bool = True,
) -> Iterator[MagicMock]:
    """Boundary for cost-accumulation tests that may reconfigure ``run_chat_agent``."""
    with ExitStack() as stack:
        stack.enter_context(patch.object(tui, '_start_file_watcher'))
        stack.enter_context(patch.object(tui, '_load_tui_state'))
        stack.enter_context(patch.object(tui, '_save_tui_state'))
        mock_run = stack.enter_context(
            patch_run_chat_agent(
                run_result=run_result,
                patch_show_run=patch_show_run,
            )
        )
        yield mock_run


@contextmanager
def patch_run_agent_task_boundary(
    *,
    run_result: RunResult | None = None,
    patch_show_run: bool = True,
) -> Iterator[MagicMock]:
    """Boundary patches for ``TeaAgentTUI._run_agent_task`` integration tests."""
    with patch_run_chat_agent(
        run_result=run_result,
        patch_show_run=patch_show_run,
    ) as mock_run:
        yield mock_run
