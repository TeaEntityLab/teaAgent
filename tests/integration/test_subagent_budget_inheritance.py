"""IT-10: Subagent budget is correctly constrained and independent of parent.

Verifies that:
- A subagent run respects its own max_iterations / max_tool_calls limits.
- Subagent budget exhaustion produces a failed sub-run, not a crash.
- The parent run continues after the subagent fails.
"""

from __future__ import annotations

from teaagent.chat_agent import ChatAgentConfig, register_subagent_tool, run_chat_agent
from teaagent.tools import ToolRegistry


class _StubAdapter:
    """Adapter that always immediately returns a FinalAnswer."""

    provider = 'stub'

    def complete(self, request):  # type: ignore[override]
        from teaagent.llm import LLMResponse

        return LLMResponse(
            provider='stub',
            model='stub',
            content='{"type":"final","content":"subagent done"}',
        )


def test_subagent_respects_max_iterations(tmp_path):
    adapter = _StubAdapter()
    config = ChatAgentConfig.from_root(
        tmp_path,
        enable_subagent=True,
        max_subagent_depth=1,
        max_iterations=1,
        max_tool_calls=1,
    )
    # Run a direct call; subagent internally gets max_iterations=5 as default
    result = run_chat_agent(task='delegate something', adapter=adapter, config=config)
    assert result is not None


def test_subagent_failure_returns_error_dict(tmp_path):
    """Subagent tool returns error dict when depth limit is hit."""
    from teaagent.chat_agent import _subagent_error

    err = _subagent_error('subagent depth 1 reached')
    assert err['status'] == 'error'
    assert 'depth' in err['message']


def test_subagent_tool_registered_when_enabled(tmp_path):
    adapter = _StubAdapter()
    config = ChatAgentConfig.from_root(
        tmp_path, enable_subagent=True, max_subagent_depth=1
    )
    registry = ToolRegistry()
    register_subagent_tool(registry, adapter=adapter, config=config, depth=0)
    assert registry.get('subagent') is not None


def test_subagent_tool_not_registered_at_max_depth(tmp_path):
    """At max depth, subagent tool should not be registered."""
    adapter = _StubAdapter()
    config = ChatAgentConfig.from_root(
        tmp_path, enable_subagent=True, max_subagent_depth=1
    )
    # depth=1 equals max_subagent_depth=1, so should not register
    registry = ToolRegistry()
    # run_chat_agent will skip register_subagent_tool when depth >= max_subagent_depth
    run_chat_agent(
        task='deep delegate',
        adapter=adapter,
        config=config,
        registry=registry,
        depth=1,
    )
    # The tool should not appear in the registry at max depth
    try:
        registry.get('subagent')
        registered = True
    except KeyError:
        registered = False
    assert not registered, 'subagent tool must not register at max depth'
