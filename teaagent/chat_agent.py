from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.context import ContextCompactor
from teaagent.heartbeat import Heartbeat
from teaagent.llm import (
    LLMAdapter,
    LLMMessage,
    LLMRequest,
)
from teaagent.memory import MemoryCatalog, memory_entries_to_prompt
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.prompt import (
    assemble_agent_prompt,
    load_project_instructions,
    parse_model_decision,
)
from teaagent.run_store import RunStore
from teaagent.runner import AgentRunner, ApprovalHandler, Decision, RunResult
from teaagent.tools import ToolAnnotations, ToolRegistry
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
    approved_call_ids: frozenset[str] = frozenset()
    enable_subagent: bool = False
    max_subagent_depth: int = 1
    heartbeat_seconds: float = 0.0
    stream: bool = False
    on_chunk: Optional[Callable[[str], None]] = None
    approval_handler: Optional[ApprovalHandler] = None

    @classmethod
    def from_root(cls, root: str | Path, **kwargs: Any) -> 'ChatAgentConfig':
        return cls(root=Path(root).resolve(), **kwargs)


class ModelDecisionEngine:
    def __init__(
        self,
        *,
        adapter: LLMAdapter,
        registry: ToolRegistry,
        budget: Optional[RunBudget] = None,
        project_instructions: str = '',
        model: Optional[str] = None,
        task_spec: Optional[str] = None,
        stream: bool = False,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.adapter = adapter
        self.registry = registry
        self.budget = budget
        self.project_instructions = project_instructions
        self.model = model
        self.task_spec = task_spec
        self.stream = stream
        self.on_chunk = on_chunk

    def decide(self, context: dict) -> Decision:
        prompt = assemble_agent_prompt(
            task=context['task'],
            context=context,
            registry=self.registry,
            project_instructions=self.project_instructions,
            task_spec=self.task_spec,
        )

        if self.budget is not None and self.model:
            resolved_model = self.model
            approx_input = len(prompt.system) + len(prompt.user)
            self.budget.check_cost_preflight(
                provider=self.adapter.provider,
                model=resolved_model,
                approx_input_chars=approx_input,
                max_output_tokens=1024,
            )

        response = self.adapter.complete(
            LLMRequest(
                system=prompt.system,
                messages=[LLMMessage(role='user', content=prompt.user)],
                model=self.model,
                stream=self.stream,
                on_chunk=self.on_chunk,
            )
        )
        previous_cost = context.get('_cost_cents', 0.0)
        context['_cost_cents'] = previous_cost + response.estimated_cost_cents
        return parse_model_decision(response.content)


def run_chat_agent(
    *,
    task: str,
    adapter: LLMAdapter,
    config: ChatAgentConfig,
    audit: Optional[AuditLogger] = None,
    registry: Optional[ToolRegistry] = None,
    task_spec: Optional[str] = None,
    depth: int = 0,
    initial_observations: Optional[list[dict[str, Any]]] = None,
) -> RunResult:
    tool_registry = registry or build_workspace_tool_registry(config.root)
    if config.enable_subagent and depth < config.max_subagent_depth:
        register_subagent_tool(
            tool_registry, adapter=adapter, config=config, depth=depth
        )
    project_instructions = load_project_instructions(config.root)
    memories = memory_entries_to_prompt(
        MemoryCatalog(config.root).search(task, limit=config.memory_limit)
    )
    runner_budget = RunBudget(
        max_iterations=config.max_iterations, max_tool_calls=config.max_tool_calls
    )
    engine = ModelDecisionEngine(
        adapter=adapter,
        registry=tool_registry,
        budget=runner_budget,
        project_instructions=project_instructions,
        model=config.model,
        task_spec=task_spec,
        stream=config.stream,
        on_chunk=config.on_chunk,
    )
    audit_logger = audit or AuditLogger()
    runner = AgentRunner(
        registry=tool_registry,
        audit=audit_logger,
        budget=runner_budget,
        approval_policy=ApprovalPolicy(
            approved_call_ids=config.approved_call_ids,
            allow_all_destructive=config.allow_destructive,
            permission_mode=config.permission_mode,
        ),
        approval_handler=config.approval_handler,
        compactor=ContextCompactor(memory_keys=('task_spec', 'memories')),
    )
    run_id = uuid4().hex
    heartbeat: Optional[Heartbeat] = None
    if config.heartbeat_seconds > 0:
        heartbeat = Heartbeat(
            audit_logger, run_id, interval_seconds=config.heartbeat_seconds
        )
        heartbeat.start()
    try:
        return runner.run(
            task=task,
            decide=lambda context: engine.decide(with_memories(context, memories)),
            run_id=run_id,
            initial_observations=initial_observations,
        )
    finally:
        if heartbeat is not None:
            heartbeat.stop()


def with_memories(context: dict, memories: list[dict]) -> dict:
    if not memories:
        return context
    updated = dict(context)
    updated['memories'] = memories
    return updated


def register_subagent_tool(
    registry: ToolRegistry,
    *,
    adapter: LLMAdapter,
    config: ChatAgentConfig,
    depth: int,
) -> None:
    def execute(args: dict[str, Any]) -> dict[str, Any]:
        if depth >= config.max_subagent_depth:
            return _subagent_error(
                f'subagent depth {config.max_subagent_depth} reached'
            )
        task = args.get('task')
        if not isinstance(task, str) or not task.strip():
            return _subagent_error("subagent requires non-empty 'task'")
        sub_config = replace(
            config,
            max_iterations=int(args.get('max_iterations', 5)),
            max_tool_calls=int(args.get('max_tool_calls', 5)),
        )
        store = RunStore(config.root)
        sub_audit = store.audit_logger()
        sub_result = run_chat_agent(
            task=task,
            adapter=adapter,
            config=sub_config,
            audit=sub_audit,
            depth=depth + 1,
        )
        store.logger_for_result(sub_result, sub_audit)
        return {
            'run_id': sub_result.run_id,
            'status': sub_result.status,
            'iterations': sub_result.iterations,
            'tool_calls': sub_result.tool_calls,
            'final_answer': sub_result.final_answer.content
            if sub_result.final_answer
            else '',
            'message': '',
        }

    registry.register(
        name='subagent',
        description='Delegate one focused sub-task to a fresh agent run sharing tools and policy.',
        input_schema={
            'type': 'object',
            'properties': {
                'task': {'type': 'string'},
                'max_iterations': {'type': 'integer'},
                'max_tool_calls': {'type': 'integer'},
            },
            'required': ['task'],
        },
        output_schema={
            'type': 'object',
            'properties': {
                'run_id': {'type': 'string'},
                'status': {'type': 'string'},
                'iterations': {'type': 'integer'},
                'tool_calls': {'type': 'integer'},
                'final_answer': {'type': 'string'},
                'message': {'type': 'string'},
            },
            'required': ['status'],
        },
        annotations=ToolAnnotations(
            read_only=False, destructive=False, idempotent=False
        ),
        handler=execute,
    )


def _subagent_error(message: str) -> dict[str, Any]:
    return {
        'run_id': '',
        'status': 'error',
        'iterations': 0,
        'tool_calls': 0,
        'final_answer': '',
        'message': message,
    }
