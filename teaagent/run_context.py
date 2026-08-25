"""RunContext TypedDict — documents the implicit context protocol (ENG-02).

All known keys that ``AgentRunner.run()`` passes between the runner,
``ModelDecisionEngine``, ``ContextCompactor``, and related modules.

Usage::

    from teaagent.run_context import RunContext, make_initial_context

    ctx: RunContext = make_initial_context(
        task="do something",
        observations=[],
    )
    ctx["_cost_cents"] = 0.0  # typed — mypy catches typos
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict, cast


@dataclass
class DecisionUsage:
    """Authoritative LLM usage totals for a run (SEC-05).

    Tracked on ``ModelDecisionEngine`` and read by ``AgentRunner`` via
    ``usage_reader`` so budget enforcement does not trust mutable context keys.
    """

    cost_cents: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


class RunContext(TypedDict, total=False):
    """Typed dict for the agent-runner context protocol.

    All keys are optional (``NotRequired`` since ``total=False``).  Modules
    that read a key **must** use ``.get(key, default)`` — never bare indexing
    on keys that may be absent.

    Keys prefixed with ``_`` are side-channel protocol keys written by
    ``ModelDecisionEngine`` and read by ``AgentRunner``.
    """

    # -- Core protocol keys (set at init time) --

    task: str
    """The task string that the agent was asked to perform."""

    observations: list[dict[str, Any]]
    """Ordered list of observation dicts (tool results, system messages)."""

    tools: list[dict[str, Any]]
    """MCP tool metadata — registered tools as dicts."""

    workspace_root: str
    """Absolute path to the workspace root directory."""

    # -- Decision side-channel keys (written by ModelDecisionEngine) --

    _cost_cents: float
    """Running total of estimated cost in cents (side-channel)."""

    _input_tokens: int
    """Running total of input tokens (side-channel)."""

    _output_tokens: int
    """Running total of output tokens (side-channel)."""

    decision_summary: str
    """Injected summary from the decision log (if available)."""

    # -- Compaction keys (written by ContextCompactor) --

    compacted_summary: str
    """Semantic summary of compacted observations."""

    memory_keys: dict[str, Any]
    """Pinned memory keys preserved across compaction."""

    compaction_count: int
    """How many compactions have occurred (written by ContextCompactor)."""

    # -- Runtime-config keys (written by ManagedAgentRunner) --

    lsp_context: str
    """LSP analysis context string."""

    memories: list[dict[str, Any]]
    """Memory catalog entries injected into the prompt."""

    max_tokens: int
    """Maximum tokens for the model response."""

    user_id: str
    """User identifier for the current session."""

    session_id: str
    """Session identifier."""

    agent_module: str
    """Agent module name override."""

    agent: str
    """Agent name override."""

    project_id: str
    """Project identifier."""

    # -- Hook-injected keys --

    project_instructions: str
    """Project-level instructions injected by hooks."""

    # -- Durable effect keys (EFX-001) --

    pending_effect: dict[str, Any]
    """Unmatched mutating-tool start awaiting settlement."""

    unconfirmed_effects: list[str]
    """Payload digests of unmatched non-idempotent starts."""


def make_initial_context(
    task: str,
    observations: list[dict[str, Any]] | None = None,
    extras: dict[str, Any] | None = None,
) -> RunContext:
    """Build the initial context dict with known keys.

    This is a typed factory so callers don't have to repeat the cast::

        ctx = make_initial_context(task, observations, extras)
        # ctx is typed as RunContext
    """
    ctx: RunContext = {'task': task}
    if observations:
        ctx['observations'] = observations
    if extras:
        # Discard keys that are already set explicitly.
        for k, v in extras.items():
            if k not in ctx:
                cast(dict[str, Any], ctx)[k] = v
    return ctx
