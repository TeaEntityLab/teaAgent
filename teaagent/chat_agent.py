from __future__ import annotations

import contextlib
import threading
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, cast, overload
from uuid import uuid4

from teaagent.audit import AuditLogger
from teaagent.auto_mode import AutoModeConfig
from teaagent.browser_tools import register_browser_tools
from teaagent.budget import RunBudget
from teaagent.code_analysis import (
    CodeAnalysisConfig,
    LSPServerManager,
    extract_candidate_paths,
    get_lsp_context,
    register_code_analysis_tools,
)
from teaagent.context import ContextCompactor
from teaagent.errors import ToolValidationError
from teaagent.heartbeat import Heartbeat
from teaagent.hooks import HookRegistry
from teaagent.integration.run_contract import build_run_budget
from teaagent.llm import (
    LLMAdapter,
    LLMMessage,
    LLMRequest,
)
from teaagent.llm._types import CostSource
from teaagent.memory import MemoryCatalog, memory_entries_to_prompt
from teaagent.policy import PermissionMode
from teaagent.prompt import (
    DECISION_JSON_SCHEMA,
    assemble_agent_prompt,
    load_project_instructions,
    parse_model_decision,
)
from teaagent.run_context import DecisionUsage
from teaagent.runner import (
    AgentRunner,
    ApprovalHandler,
    BudgetPromptHandler,
    Decision,
    FinalAnswer,
    RunResult,
)
from teaagent.skill_loader import (
    SkillContent,
    SkillIndexEntry,
    SkillSourceProfile,
    discover_skill_index,
    estimate_skill_prompt_tokens,
    load_skills_with_report,
)
from teaagent.subagents import SubagentManager, register_subagent_tools
from teaagent.tools import ToolRegistry
from teaagent.workspace_tools import (
    GitToolConfig,
    build_workspace_tool_registry,
    register_git_tools,
)


def _extract_tenant_id_from_argv() -> str:
    import sys

    for i, arg in enumerate(sys.argv):
        if arg == '--tenant-id':
            if i + 1 < len(sys.argv):
                return sys.argv[i + 1]
        elif arg.startswith('--tenant-id='):
            return arg.split('=', 1)[1]
    return 'default'


@dataclass(frozen=True)
class ChatAgentConfig:
    root: Path
    tenant_id: str = 'default'
    max_iterations: int = 10
    max_tool_calls: int = 10
    max_estimated_cost_cents: int | None = 500
    allow_destructive: bool = False
    model: Optional[str] = None
    permission_mode: PermissionMode = PermissionMode.PROMPT
    memory_limit: int = 5
    approved_call_ids: frozenset[str] = frozenset()
    approved_payload_digests: frozenset[str] = frozenset()
    enable_subagent: bool = False
    max_subagent_depth: int = 1
    heartbeat_seconds: float = 0.0
    stream: bool = False
    on_chunk: Optional[Callable[[str], None]] = None
    stream_text_only: bool = True
    approval_handler: Optional[ApprovalHandler] = None
    budget_prompt_handler: Optional[BudgetPromptHandler] = None
    checkpoint_store: Any = None
    chat_messages: Optional[list[LLMMessage]] = None
    cancel_token: Optional[threading.Event] = None
    subagent_manager: Optional[SubagentManager] = None
    code_analysis_config: Optional[CodeAnalysisConfig] = None
    enable_git_tools: bool = False
    skill_search_dirs: Optional[list[str]] = None
    skill_source_profile: SkillSourceProfile = 'default'
    selected_skills: Optional[frozenset[str]] = None
    skill_prompt_mode: str = 'eager'
    hook_registry: Optional[HookRegistry] = None
    auto_mode_config: Optional[AutoModeConfig] = None
    use_approval_store: bool = True
    require_plan: bool = False
    skip_plan_check: bool = False
    validation_profile: Optional[str] = None

    def __post_init__(self) -> None:
        """Convert string permission_mode to PermissionMode enum.

        Callers may construct the dataclass directly with a string
        (e.g. ``ChatAgentConfig(root=…, permission_mode='allow')``),
        but the field is typed ``PermissionMode`` and downstream code
        calls ``.value`` on it.  A frozen dataclass requires
        ``object.__setattr__`` to coerce the value.
        """
        if isinstance(self.permission_mode, str):
            object.__setattr__(
                self, 'permission_mode', PermissionMode(self.permission_mode)
            )

    @classmethod
    def from_root(cls, root: str | Path, **kwargs: Any) -> 'ChatAgentConfig':  # noqa: C901
        from teaagent.config_loader import ConfigResolver
        from teaagent.policy import parse_permission_mode

        resolved_root = Path(root).resolve()
        rc = ConfigResolver(workspace_root=resolved_root).resolve()

        # Treat explicit None as "not provided" for optional overrides so callers
        # don't accidentally clobber dataclass defaults (e.g. memory_limit=5).
        if kwargs.get('memory_limit', 0) is None:
            kwargs.pop('memory_limit', None)

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
        if 'code_analysis_config' not in kwargs:
            ca_enabled = rc.get('code_analysis_enabled')
            if isinstance(ca_enabled, bool) and ca_enabled:
                profile_overrides['code_analysis_config'] = (
                    CodeAnalysisConfig.from_root(resolved_root, enabled=True)
                )
        if 'enable_git_tools' not in kwargs:
            git_enabled = rc.get('git_tools_enabled')
            if isinstance(git_enabled, bool) and git_enabled:
                profile_overrides['enable_git_tools'] = True
        if 'skill_search_dirs' not in kwargs:
            configured_skill_dirs = rc.get('skill_search_dirs')
            if isinstance(configured_skill_dirs, list):
                profile_overrides['skill_search_dirs'] = [
                    str(item) for item in configured_skill_dirs
                ]
        if 'skill_source_profile' not in kwargs:
            configured_profile = rc.get('skill_source_profile')
            if configured_profile in {'default', 'extended', 'custom'}:
                profile_overrides['skill_source_profile'] = configured_profile
        if 'tenant_id' not in kwargs:
            profile_overrides['tenant_id'] = _extract_tenant_id_from_argv()

        merged = {**profile_overrides, **kwargs}
        # Convert string permission_mode to enum — callers may pass the
        # string form directly (e.g. from_root(…, permission_mode='read-only')),
        # but the dataclass field is typed PermissionMode and downstream code
        # calls .value on it.
        if isinstance(merged.get('permission_mode'), str):
            merged['permission_mode'] = parse_permission_mode(merged['permission_mode'])
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
        stream_text_only: bool = True,
        chat_messages: Optional[list[LLMMessage]] = None,
        skills: Optional[list[SkillContent]] = None,
        skill_index: Optional[list[SkillIndexEntry]] = None,
    ) -> None:
        self.adapter = adapter
        self.registry = registry
        self.budget = budget
        self.project_instructions = project_instructions
        self.model = model
        self.task_spec = task_spec
        self.stream = stream
        self.on_chunk = on_chunk
        self.stream_text_only = stream_text_only
        self.chat_messages = chat_messages
        self.skills = skills
        self.skill_index = skill_index
        self.max_parse_retries = 2
        self.usage = DecisionUsage()

    def reset_usage(self) -> None:
        self.usage = DecisionUsage()

    def decide(self, context: dict) -> Decision:
        prompt = assemble_agent_prompt(
            task=context['task'],
            context=context,
            registry=self.registry,
            project_instructions=self.project_instructions,
            task_spec=self.task_spec,
            skills=self.skills,
            skill_index=self.skill_index,
            decision_summary=context.get('decision_summary', ''),
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
        on_chunk = self.on_chunk
        if self.stream and self.stream_text_only and on_chunk is not None:
            from teaagent.streaming.content_filter import DecisionContentStreamer

            on_chunk = DecisionContentStreamer(on_chunk).feed
        last_response_content = ''
        for attempt in range(self.max_parse_retries + 1):
            response = self.adapter.complete(
                LLMRequest(
                    system=prompt.system,
                    messages=messages,
                    model=self.model,
                    stream=self.stream and on_chunk is not None,
                    on_chunk=on_chunk,
                    response_format={
                        'type': 'json_schema',
                        'json_schema': {
                            'name': 'teaagent_decision',
                            'strict': True,
                            'schema': DECISION_JSON_SCHEMA,
                        },
                    },
                )
            )
            last_response_content = response.content
            g = response.governance
            assert g is not None
            if g.cost_source != CostSource.UNKNOWN:
                self.usage.cost_cents += float(response.estimated_cost_cents)
            self.usage.input_tokens += int(response.input_tokens)
            self.usage.output_tokens += int(response.output_tokens)
            context['_cost_cents'] = self.usage.cost_cents
            context['_input_tokens'] = self.usage.input_tokens
            context['_output_tokens'] = self.usage.output_tokens
            try:
                return parse_model_decision(response.content)
            except ToolValidationError as exc:
                if attempt >= self.max_parse_retries:
                    break
                messages.append(LLMMessage(role='assistant', content=response.content))
                messages.append(
                    LLMMessage(
                        role='user',
                        content=(
                            'Your last output was invalid JSON decision.\n'
                            f'Parser error: {exc}\n'
                            'Repair it and reply with exactly one valid JSON object '
                            'only.'
                        ),
                    )
                )
        fallback = _plain_text_answer_fallback(context, last_response_content)
        if fallback is not None:
            return fallback
        # For workspace tasks where fallback doesn't apply, raise explicit error
        # instead of masking as success with invalid_model_decision_json
        task = str(context.get('task', ''))
        if not _looks_like_simple_answer_task(task):
            # The model may have gathered information via tools and produced a
            # plain-text final answer that parse_model_decision couldn't extract
            # as JSON (common when the provider does not support response_format
            # and the model falls back to natural language for final answers).
            # Try to surface it as a final answer before failing hard.
            content = (last_response_content or '').strip()
            if content and len(content) >= 20 and not content.startswith('{'):
                return FinalAnswer(
                    content=content,
                    metadata={'decision_fallback': 'post_retry_plain_text'},
                )
            raise RuntimeError(
                f'Model decision JSON parsing failed after {self.max_parse_retries} attempts. '
                f'This indicates the model is not producing valid tool decisions for a workspace task. '
                f'Recovery hint: Check if the task is clear, try a simpler task, '
                f'or adjust the model/system prompt to ensure valid JSON output.'
            )
        # For simple tasks, keep the old behavior as fallback
        return FinalAnswer(
            content='{"status":"error","action":"wait","reason":"invalid_model_decision_json"}',
            metadata={'decision_fallback': 'invalid_model_decision_json'},
        )


def _plain_text_answer_fallback(
    context: dict, response_content: str
) -> Optional[FinalAnswer]:
    if context.get('observations'):
        return None
    task = str(context.get('task', ''))
    if not _looks_like_simple_answer_task(task):
        return None
    answer = response_content.strip()
    if not _looks_like_plain_text_answer(answer):
        return None
    return FinalAnswer(
        content=answer,
        metadata={'decision_fallback': 'plain_text_final_answer'},
    )


def _looks_like_simple_answer_task(task: str) -> bool:
    normalized = ' '.join(task.lower().strip().split())
    if not normalized:
        return False
    workspace_markers = (
        'file',
        'repo',
        'workspace',
        'project',
        'read ',
        'write ',
        'edit ',
        'modify ',
        'fix ',
        'debug ',
        'run ',
        'test ',
        'commit',
        'src/',
        'tests/',
        '.py',
        '.md',
        '.json',
        '.toml',
        '.yaml',
        '.yml',
    )
    if any(marker in normalized for marker in workspace_markers):
        return False
    question_starts = (
        'what ',
        'who ',
        'when ',
        'where ',
        'why ',
        'how ',
        'can you tell me',
        'could you tell me',
        'tell me ',
        'explain ',
        'describe ',
        'summarize ',
    )
    return normalized.endswith('?') or normalized.startswith(question_starts)


def _looks_like_plain_text_answer(answer: str) -> bool:
    if len(answer) < 20:
        return False
    stripped = answer.lstrip()
    if stripped.startswith(('{', '[', '```')):
        return False
    words = answer.split()
    return len(words) >= 4


@overload
def run_chat_agent(
    config: ChatAgentConfig,
    task: str,
    *,
    adapter: LLMAdapter | None = None,
    audit: Optional[AuditLogger] = None,
    registry: Optional[ToolRegistry] = None,
    task_spec: Optional[str] = None,
    depth: int = 0,
    initial_observations: Optional[list[dict[str, Any]]] = None,
    initial_context_extra: Optional[dict[str, Any]] = None,
    run_id: Optional[str] = None,
) -> RunResult: ...


@overload
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
    run_id: Optional[str] = None,
) -> RunResult: ...


def run_chat_agent(*args: Any, **kwargs: Any) -> RunResult:
    """Run the chat agent.

    Primary (new) signature — positional ``config`` and ``task``::

        run_chat_agent(config, task, *, adapter=None, ...)

    Legacy (deprecated) signature — keyword-only::

        run_chat_agent(*, task=..., adapter=..., config=...)

    The keyword-only form emits a :class:`DeprecationWarning`.
    """
    if len(args) >= 2:
        config, task = args[0], args[1]
    elif len(args) == 1:
        config = args[0]
        task = kwargs.pop('task', None)
        if task is None:
            raise TypeError("run_chat_agent() missing required argument: 'task'")
        warnings.warn(
            'Calling run_chat_agent with keyword-only arguments is deprecated. '
            'Use positional: run_chat_agent(config, task, ...)',
            DeprecationWarning,
            stacklevel=2,
        )
    else:
        warnings.warn(
            'Calling run_chat_agent with keyword-only arguments is deprecated. '
            'Use positional: run_chat_agent(config, task, ...)',
            DeprecationWarning,
            stacklevel=2,
        )
        config = kwargs.pop('config', None)
        task = kwargs.pop('task', None)
        if config is None or task is None:
            raise TypeError("run_chat_agent() requires 'config' and 'task'")
    return _run_chat_agent_impl(
        config=config,
        task=task,
        **kwargs,
    )


def _setup_tool_registry(
    config: ChatAgentConfig,
    adapter: LLMAdapter,
    registry: Optional[ToolRegistry],
    task: str,
    task_spec: Optional[str],
    depth: int,
    initial_context_extra: Optional[dict[str, Any]],
) -> tuple[ToolRegistry, dict[str, Any]]:
    """Setup and configure the tool registry.

    Returns:
        Tuple of (tool_registry, context_extra)
    """
    tool_registry = registry or build_workspace_tool_registry(config.root)
    if config.hook_registry is not None and tool_registry.hook_registry is None:
        tool_registry.hook_registry = config.hook_registry
    manager = config.subagent_manager or SubagentManager(
        root=config.root, parent_config=config, parent_adapter=adapter
    )
    context_extra = dict(initial_context_extra or {})
    _registry_fresh = registry is None
    if _registry_fresh and config.code_analysis_config is not None:
        register_code_analysis_tools(tool_registry, config.code_analysis_config)
        lsp_manager = LSPServerManager(config.code_analysis_config)
        candidate_paths = extract_candidate_paths(task, task_spec or '')
        if candidate_paths:
            context_extra['lsp_context'] = get_lsp_context(
                candidate_paths=candidate_paths,
                manager=lsp_manager,
                max_files=config.code_analysis_config.max_files_for_context,
                diagnostic_severity_limit=config.code_analysis_config.diagnostic_severity_limit,
            )
    if config.enable_subagent and depth < config.max_subagent_depth:
        register_subagent_tools(
            tool_registry,
            adapter=adapter,
            config=config,
            depth=depth,
            manager=manager,
        )
    if _registry_fresh and config.enable_git_tools:
        register_git_tools(tool_registry, GitToolConfig(root=config.root))
    if _registry_fresh and 'browser_navigate' not in tool_registry.list_tools():
        register_browser_tools(tool_registry)
    from teaagent.mcp_trust import apply_mcp_trust_hooks

    apply_mcp_trust_hooks(tool_registry, config.root)
    return tool_registry, context_extra


def _load_skills_and_memory(
    config: ChatAgentConfig,
    task: str,
    run_id: str,
    audit_logger: AuditLogger,
) -> tuple[list[SkillIndexEntry], list[dict], list]:
    """Load skills and memory for the chat agent.

    Returns:
        Tuple of (skill_index_entries, memories, active_skills)
    """
    if config.skill_source_profile == 'custom' and not config.skill_search_dirs:
        raise ValueError('skill_source_profile=custom requires skill_search_dirs')
    skill_index_entries: list[SkillIndexEntry] = []
    if config.skill_prompt_mode == 'index_only':
        skill_index_entries = discover_skill_index(
            config.root,
            preferred_dirs=cast(Optional[list[str | Path]], config.skill_search_dirs),
            source_profile=config.skill_source_profile,
        )
        skill_report = load_skills_with_report(
            config.root,
            preferred_dirs=cast(Optional[list[str | Path]], config.skill_search_dirs),
            source_profile=config.skill_source_profile,
            selected_names=frozenset(),
        )
    else:
        skill_report = load_skills_with_report(
            config.root,
            preferred_dirs=cast(Optional[list[str | Path]], config.skill_search_dirs),
            source_profile=config.skill_source_profile,
            selected_names=config.selected_skills,
        )
    active_skills = skill_report.skills
    audit_logger.record(
        'skill_load',
        run_id,
        skill_prompt_mode=config.skill_prompt_mode,
        selected_skills=sorted(config.selected_skills or ()),
        skill_index_count=len(skill_index_entries),
        searched_dirs=[str(path) for path in skill_report.searched_dirs],
        loaded=[str(skill.path) for skill in active_skills],
        estimated_skill_tokens=estimate_skill_prompt_tokens(active_skills),
        skipped=[
            {
                'path': str(item.skill_path),
                'reason': item.reason,
                'findings': [
                    {
                        'severity': finding.severity,
                        'message': finding.message,
                    }
                    for finding in (item.review.findings if item.review else [])
                ],
            }
            for item in skill_report.skipped
        ],
        warnings=[
            {'path': str(warning.skill_path), 'message': warning.message}
            for warning in skill_report.warnings
        ],
    )
    memories = memory_entries_to_prompt(
        MemoryCatalog(config.root).search(task, limit=config.memory_limit)
    )
    return skill_index_entries, memories, active_skills


def _create_runner_and_engine(
    config: ChatAgentConfig,
    adapter: LLMAdapter,
    tool_registry: ToolRegistry,
    project_instructions: str,
    task_spec: Optional[str],
    active_skills: list,
    skill_index_entries: list[SkillIndexEntry],
    context_extra: dict[str, Any],
    run_id: str,
    audit_logger: AuditLogger,
) -> tuple[AgentRunner, ModelDecisionEngine]:
    """Create the AgentRunner and ModelDecisionEngine.

    Returns:
        Tuple of (runner, engine)
    """
    runner_budget = build_run_budget(
        max_iterations=config.max_iterations,
        max_tool_calls=config.max_tool_calls,
        max_estimated_cost_cents=config.max_estimated_cost_cents,
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
        stream_text_only=config.stream_text_only,
        chat_messages=config.chat_messages,
        skills=active_skills,
        skill_index=skill_index_entries or None,
    )
    # Load approval store if enabled
    from teaagent.integration.run_contract import RunSetupRequest, build_approval_policy

    approval_policy = build_approval_policy(
        RunSetupRequest(
            root=config.root,
            permission_mode=config.permission_mode,
            allow_destructive=config.allow_destructive,
            max_iterations=config.max_iterations,
            max_tool_calls=config.max_tool_calls,
            max_estimated_cost_cents=config.max_estimated_cost_cents,
            approved_call_ids=config.approved_call_ids,
            approved_payload_digests=config.approved_payload_digests,
            use_approval_store=config.use_approval_store,
            run_id=run_id,
            resumed_from=context_extra.get('resumed_from'),
            load_plugins=False,
            tenant_id=config.tenant_id,
        ),
        approval_origin_run_id=context_extra.get('resumed_from') or run_id,
    )

    runner = AgentRunner(
        registry=tool_registry,
        audit=audit_logger,
        budget=runner_budget,
        approval_policy=approval_policy,
        approval_handler=config.approval_handler,
        budget_prompt_handler=config.budget_prompt_handler,
        compactor=ContextCompactor(memory_keys=('task_spec', 'memories')),
        checkpoint_store=config.checkpoint_store,
        cancel_token=config.cancel_token,
        auto_mode_config=config.auto_mode_config,
        require_plan=config.require_plan,
        skip_plan_check=config.skip_plan_check,
        usage_reader=lambda: (
            engine.usage.cost_cents,
            engine.usage.input_tokens,
            engine.usage.output_tokens,
        ),
    )
    return runner, engine


def _setup_heartbeat(
    config: ChatAgentConfig,
    audit_logger: AuditLogger,
    run_id: str,
) -> Optional[Heartbeat]:
    """Setup heartbeat monitoring if configured.

    Returns:
        Heartbeat instance or None
    """
    heartbeat: Optional[Heartbeat] = None
    if config.heartbeat_seconds > 0:
        heartbeat = Heartbeat(
            audit_logger,
            run_id,
            interval_seconds=config.heartbeat_seconds,
            liveness_root=config.root,
        )
        heartbeat.start()
    return heartbeat


def _apply_plan_contract(
    runner: AgentRunner,
    context_extra: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """Apply plan contract to runner if present in context.

    Returns:
        run_started_extra dict or None
    """
    run_started_extra: Optional[dict[str, Any]] = None
    plan_contract = context_extra.get('plan_contract')
    if isinstance(plan_contract, dict):
        run_started_extra = {
            'plan_path': plan_contract.get('rel_path'),
            'plan_content_hash': plan_contract.get('content_hash'),
        }
    if plan_contract and isinstance(plan_contract, dict):
        from teaagent.plan import PlanContract

        # Reconstruct PlanContract for the validator that enforces write scope.
        contract = PlanContract(
            path=Path(plan_contract.get('path', '')),
            rel_path=plan_contract.get('rel_path', ''),
            content_hash=plan_contract.get('content_hash', ''),
            task=plan_contract.get('task', ''),
            file_targets=frozenset(plan_contract.get('file_targets', [])),
        )
        runner.plan_validator.set_plan_contract(contract)
        object.__setattr__(runner, '_plan_contract', contract)
    return run_started_extra


def _run_chat_agent_impl(
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
    run_id: Optional[str] = None,
) -> RunResult:
    run_id = run_id or uuid4().hex
    project_instructions = load_project_instructions(config.root)
    audit_logger = audit or AuditLogger()

    tool_registry, context_extra = _setup_tool_registry(
        config, adapter, registry, task, task_spec, depth, initial_context_extra
    )
    skill_index_entries, memories, active_skills = _load_skills_and_memory(
        config, task, run_id, audit_logger
    )
    runner, engine = _create_runner_and_engine(
        config,
        adapter,
        tool_registry,
        project_instructions,
        task_spec,
        active_skills,
        skill_index_entries,
        context_extra,
        run_id,
        audit_logger,
    )
    heartbeat = _setup_heartbeat(config, audit_logger, run_id)
    run_started_extra = _apply_plan_contract(runner, context_extra) or {}
    run_started_extra = {
        **run_started_extra,
        'provider': str(context_extra.get('provider', '') or ''),
        'model': str(context_extra.get('model', '') or config.model or ''),
        'permission_mode': config.permission_mode.value,
    }

    try:
        engine.reset_usage()
        result = runner.run(
            task=task,
            decide=lambda context: engine.decide(with_memories(context, memories)),
            run_id=run_id,
            initial_observations=initial_observations,
            initial_context_extra=(context_extra or None),
            run_started_extra=run_started_extra,
        )
        _auto_curate_memory(
            root=config.root,
            task=task,
            result=result,
            audit_events=audit_logger.events,
            run_id=run_id,
            audit=audit_logger,
        )
        return result
    finally:
        if heartbeat is not None:
            heartbeat.stop()
            from teaagent.ergonomics.run_liveness import clear_liveness

            clear_liveness(config.root, run_id)


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
    manager = config.subagent_manager or SubagentManager(
        root=config.root, parent_config=config, parent_adapter=adapter
    )
    if config.code_analysis_config is not None:
        register_code_analysis_tools(registry, config.code_analysis_config)
    register_subagent_tools(
        registry,
        adapter=adapter,
        config=config,
        depth=depth,
        manager=manager,
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
    run_id: str,
    audit: AuditLogger,
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
    quarantined_recent = catalog.list_quarantined(limit=50)
    if any(
        entry.content == summary and 'auto-curated' in entry.tags
        for entry in recent + quarantined_recent
    ):
        return
    catalog.add_quarantined(
        summary,
        tags=('auto-curated', 'run-summary'),
        provenance={
            'source_kind': 'agent_run',
            'run_id': run_id,
            'reason': 'auto_curated_agent_memory',
        },
        run_id=run_id,
        audit_logger=audit,
    )


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
