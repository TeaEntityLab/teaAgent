from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.llm import LLMAdapter, LLMMessage, LLMRequest
from teaagent.memory import MemoryCatalog, memory_entries_to_prompt
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.prompt import assemble_agent_prompt, load_project_instructions, parse_model_decision
from teaagent.runner import AgentRunner, Decision, RunResult
from teaagent.tools import ToolRegistry
from teaagent.workspace_tools import build_workspace_tool_registry


@dataclass(frozen=True)
class ChatAgentConfig:
    root: Path
    max_iterations: int = 10
    max_tool_calls: int = 10
    allow_destructive: bool = False
    model: Optional[str] = None
    permission_mode: PermissionMode = PermissionMode.PROMPT
    memory_limit: int = 5

    @classmethod
    def from_root(cls, root: str | Path, **kwargs) -> "ChatAgentConfig":
        return cls(root=Path(root).resolve(), **kwargs)


class ModelDecisionEngine:
    def __init__(
        self,
        *,
        adapter: LLMAdapter,
        registry: ToolRegistry,
        project_instructions: str = "",
        model: Optional[str] = None,
        task_spec: Optional[str] = None,
    ) -> None:
        self.adapter = adapter
        self.registry = registry
        self.project_instructions = project_instructions
        self.model = model
        self.task_spec = task_spec

    def decide(self, context: dict) -> Decision:
        prompt = assemble_agent_prompt(
            task=context["task"],
            context=context,
            registry=self.registry,
            project_instructions=self.project_instructions,
            task_spec=self.task_spec,
        )
        response = self.adapter.complete(
            LLMRequest(
                system=prompt.system,
                messages=[LLMMessage(role="user", content=prompt.user)],
                model=self.model,
            )
        )
        return parse_model_decision(response.content)


def run_chat_agent(
    *,
    task: str,
    adapter: LLMAdapter,
    config: ChatAgentConfig,
    audit: Optional[AuditLogger] = None,
    registry: Optional[ToolRegistry] = None,
    task_spec: Optional[str] = None,
) -> RunResult:
    tool_registry = registry or build_workspace_tool_registry(config.root)
    project_instructions = load_project_instructions(config.root)
    memories = memory_entries_to_prompt(MemoryCatalog(config.root).search(task, limit=config.memory_limit))
    engine = ModelDecisionEngine(
        adapter=adapter,
        registry=tool_registry,
        project_instructions=project_instructions,
        model=config.model,
        task_spec=task_spec,
    )
    runner = AgentRunner(
        registry=tool_registry,
        audit=audit or AuditLogger(),
        budget=RunBudget(max_iterations=config.max_iterations, max_tool_calls=config.max_tool_calls),
        approval_policy=ApprovalPolicy(
            allow_all_destructive=config.allow_destructive,
            permission_mode=config.permission_mode,
        ),
    )
    return runner.run(task=task, decide=lambda context: engine.decide(with_memories(context, memories)))


def with_memories(context: dict, memories: list[dict]) -> dict:
    if not memories:
        return context
    updated = dict(context)
    updated["memories"] = memories
    return updated
