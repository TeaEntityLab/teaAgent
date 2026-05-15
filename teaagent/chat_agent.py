from __future__ import annotations

import contextlib
import threading
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
from teaagent.skill_loader import SkillContent, load_skills
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
    checkpoint_store: Any = None
    chat_messages: Optional[list[LLMMessage]] = None
    cancel_token: Optional[threading.Event] = None

    @classmethod
    def from_root(cls, root: str | Path, **kwargs: Any) -> 'ChatAgentConfig':
        from teaagent.config_loader import ConfigResolver
        from teaagent.policy import parse_permission_mode

        resolved_root = Path(root).resolve()
        rc = ConfigResolver(workspace_root=resolved_root).resolve()

        # Apply workspace profile values only for keys NOT already in kwargs
        profile_overrides: dict[str, Any] = {}
        if 'permission_mode' not in kwargs:
            pm_str = rc.get('permission_mode')
            if pm_str:
                with contextlib.suppress(ValueError):
                    profile_overrides['permission_mode'] = parse_permission_mode(pm_str)
        if 'max_iterations' not in kwargs:
            mi = rc.get('max_iterations')
            if mi is not None:
                profile_overrides['max_iterations'] = int(mi)
        if 'max_tool_calls' not in kwargs:
            mc = rc.get('max_tool_calls')
            if mc is not None:
                profile_overrides['max_tool_calls'] = int(mc)
        if 'model' not in kwargs:
            m = rc.get('model')
            if m:
                profile_overrides['model'] = m

        merged = {**profile_overrides, **kwargs}
        return cls(root=resolved_root, **merged)


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
        chat_messages: Optional[list[LLMMessage]] = None,
        skills: Optional[list[SkillContent]] = None,
    ) -> None:
        self.adapter = adapter
        self.registry = registry
        self.budget = budget
        self.project_instructions = project_instructions
        self.model = model
        self.task_spec = task_spec
        self.stream = stream
        self.on_chunk = on_chunk
        self.chat_messages = chat_messages
        self.skills = skills

    def decide(self, context: dict) -> Decision:
        prompt = assemble_agent_prompt(
            task=context['task'],
            context=context,
            registry=self.registry,
            project_instructions=self.project_instructions,
            task_spec=self.task_spec,
            skills=self.skills,
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

        messages = list(self.chat_messages or [])
        messages.append(LLMMessage(role='user', content=prompt.user))

        response = self.adapter.complete(
            LLMRequest(
                system=prompt.system,
                messages=messages,
                model=self.model,
                stream=self.stream,
                on_chunk=self.on_chunk,
            )
        )
        previous_cost = context.get('_cost_cents', 0.0)
        context['_cost_cents'] = previous_cost + response.estimated_cost_cents
        context['_input_tokens'] = (
            context.get('_input_tokens', 0) + response.input_tokens
        )
        context['_output_tokens'] = (
            context.get('_output_tokens', 0) + response.output_tokens
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
    depth: int = 0,
    initial_observations: Optional[list[dict[str, Any]]] = None,
    initial_context_extra: Optional[dict[str, Any]] = None,
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
    active_skills = load_skills(config.root)
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
        chat_messages=config.chat_messages,
        skills=active_skills,
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
        checkpoint_store=config.checkpoint_store,
        cancel_token=config.cancel_token,
    )
    run_id = uuid4().hex
    heartbeat: Optional[Heartbeat] = None
    if config.heartbeat_seconds > 0:
        heartbeat = Heartbeat(
            audit_logger, run_id, interval_seconds=config.heartbeat_seconds
        )
        heartbeat.start()
    try:
        result = runner.run(
            task=task,
            decide=lambda context: engine.decide(with_memories(context, memories)),
            run_id=run_id,
            initial_observations=initial_observations,
            initial_context_extra=initial_context_extra,
        )
        _auto_curate_memory(
            root=config.root,
            task=task,
            result=result,
            audit_events=audit_logger.events,
        )
        return result
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


def _auto_curate_memory(
    *,
    root: Path,
    task: str,
    result: RunResult,
    audit_events: list[Any],
) -> None:
    if result.status != 'completed' or result.final_answer is None:
        return
    summary = _build_auto_curated_summary(
        task=task, final_answer=result.final_answer.content, audit_events=audit_events
    )
    if not summary:
        return
    catalog = MemoryCatalog(root)
    recent = catalog.list(limit=50)
    if any(entry.content == summary and 'auto-curated' in entry.tags for entry in recent):
        return
    catalog.add(summary, tags=('auto-curated', 'run-summary'))


def _build_auto_curated_summary(
    *, task: str, final_answer: str, audit_events: list[Any]
) -> str:
    clean_task = task.strip()
    clean_answer = final_answer.strip()
    if not clean_task or not clean_answer:
        return ''
    last_tool_name = ''
    for event in reversed(audit_events):
        if getattr(event, 'event_type', None) != 'tool_call_completed':
            continue
        payload = getattr(event, 'payload', {})
        if isinstance(payload, dict):
            tool_name = payload.get('tool_name')
            if isinstance(tool_name, str) and tool_name:
                last_tool_name = tool_name
                break
    if last_tool_name:
        return (
            f'Task: {clean_task}\n'
            f'Outcome: {clean_answer}\n'
            f'Last tool used: {last_tool_name}'
        )
    return f'Task: {clean_task}\nOutcome: {clean_answer}'
