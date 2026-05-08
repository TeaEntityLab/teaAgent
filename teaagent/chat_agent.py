from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.llm import LLMAdapter, LLMMessage, LLMRequest
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
    ) -> None:
        self.adapter = adapter
        self.registry = registry
        self.project_instructions = project_instructions
        self.model = model

    def decide(self, context: dict) -> Decision:
        prompt = assemble_agent_prompt(
            task=context["task"],
            context=context,
            registry=self.registry,
            project_instructions=self.project_instructions,
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
) -> RunResult:
    tool_registry = registry or build_workspace_tool_registry(config.root)
    project_instructions = load_project_instructions(config.root)
    engine = ModelDecisionEngine(
        adapter=adapter,
        registry=tool_registry,
        project_instructions=project_instructions,
        model=config.model,
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
    return runner.run(task=task, decide=engine.decide)
