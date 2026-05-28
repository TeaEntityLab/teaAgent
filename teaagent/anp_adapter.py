from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional
from uuid import uuid4

from teaagent.agentcard import A2AClient
from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.errors import BudgetExceededError
from teaagent.policy import ApprovalPolicy
from teaagent.runner import AgentRunner
from teaagent.runner._types import ApprovalHandler, FinalAnswer, ToolRequest
from teaagent.tools import ToolRegistry


class ANPAdapterError(RuntimeError):
    """Raised when ANP adapter input or routing is invalid."""


LocalRunner = Callable[[str, dict[str, Any]], str]
OutboundTransport = Callable[[str, str, dict[str, Any]], dict[str, Any]]


def _federation_audit_fields(
    *,
    correlation_id: str,
    direction: Literal['inbound', 'outbound'],
    peer_endpoint: str = '',
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'anp_correlation_id': correlation_id,
        'federation_direction': direction,
        'peer_endpoint': peer_endpoint,
    }
    payload.update(extra)
    return payload


@dataclass(frozen=True)
class ANPDelegationResult:
    output: str
    agent_name: str = ''


@dataclass(frozen=True)
class ANPRoutingResult:
    output: str
    source: Literal['local', 'remote']
    fallback_used: bool = False
    agent_name: str = ''


class ANPInboundAdapter:
    """Normalize inbound ANP task payloads into local execution calls."""

    def __init__(self, executor: LocalRunner) -> None:
        self._executor = executor

    def handle_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = str(payload.get('task') or '').strip()
        if not task:
            raise ANPAdapterError('task is required')
        context = payload.get('context') or {}
        if not isinstance(context, dict):
            raise ANPAdapterError('context must be an object')
        output = self._executor(task, context)
        return {'status': 'ok', 'output': output}

    def try_handle_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.handle_task(payload)
        except Exception as exc:
            return {'status': 'error', 'error': str(exc)}


class ANPOutboundClient:
    """Delegate tasks to ANP peers through a pluggable transport."""

    def __init__(
        self,
        *,
        transport: Optional[OutboundTransport] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        self._transport = transport or self._default_transport
        self._timeout_seconds = timeout_seconds

    @property
    def transport(self) -> OutboundTransport:
        return self._transport

    @staticmethod
    def _default_transport(
        endpoint: str, task: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        result = A2AClient(endpoint).delegate(task=task, context=context)
        return {'output': result.output, 'agent_name': result.agent_name}

    def delegate(
        self,
        *,
        endpoint: str,
        task: str,
        context: Optional[dict[str, Any]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> ANPDelegationResult:
        effective_timeout = (
            timeout_seconds if timeout_seconds is not None else self._timeout_seconds
        )
        ctx = context or {}

        def _invoke() -> dict[str, Any]:
            return self._transport(endpoint, task, ctx)

        if effective_timeout is not None:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_invoke)
                try:
                    payload = future.result(timeout=effective_timeout)
                except FuturesTimeoutError as exc:
                    raise ANPAdapterError(
                        f'outbound delegation timed out after {effective_timeout}s'
                    ) from exc
        else:
            payload = _invoke()

        return ANPDelegationResult(
            output=str(payload.get('output', '')),
            agent_name=str(payload.get('agent_name') or ''),
        )


class ANPBidirectionalRouter:
    """Route task execution local-first, optionally with remote fallback."""

    def __init__(
        self,
        *,
        local_runner: LocalRunner,
        outbound_client: Optional[ANPOutboundClient] = None,
    ) -> None:
        self._local_runner = local_runner
        self._outbound = outbound_client or ANPOutboundClient()

    def route(
        self,
        *,
        task: str,
        route: Literal['auto', 'local', 'remote'] = 'auto',
        context: Optional[dict[str, Any]] = None,
        remote_endpoint: Optional[str] = None,
    ) -> ANPRoutingResult:
        task = task.strip()
        if not task:
            raise ANPAdapterError('task is required')
        payload = context or {}

        if route == 'local':
            return ANPRoutingResult(
                output=self._local_runner(task, payload),
                source='local',
                fallback_used=False,
            )

        if route == 'remote':
            if not remote_endpoint:
                raise ANPAdapterError('remote_endpoint is required for route=remote')
            remote = self._outbound.delegate(
                endpoint=remote_endpoint, task=task, context=payload
            )
            return ANPRoutingResult(
                output=remote.output,
                source='remote',
                fallback_used=False,
                agent_name=remote.agent_name,
            )

        try:
            local_output = self._local_runner(task, payload)
            return ANPRoutingResult(output=local_output, source='local')
        except Exception:
            if not remote_endpoint:
                raise
            remote = self._outbound.delegate(
                endpoint=remote_endpoint, task=task, context=payload
            )
            return ANPRoutingResult(
                output=remote.output,
                source='remote',
                fallback_used=True,
                agent_name=remote.agent_name,
            )


@dataclass(frozen=True)
class ANPGovernedInboundResult:
    status: Literal['ok', 'error', 'pending_approval']
    correlation_id: str
    output: str = ''
    error: str = ''
    run_id: str = ''
    approval: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'status': self.status,
            'correlation_id': self.correlation_id,
        }
        if self.output:
            payload['output'] = self.output
        if self.error:
            payload['error'] = self.error
        if self.run_id:
            payload['run_id'] = self.run_id
        if self.approval:
            payload['approval'] = self.approval
        return payload


class ANPGovernedService:
    """Execute ANP federation through ToolRegistry, ApprovalPolicy, Audit, and budgets.

    Coordinates federated agent operations with full governance oversight.
    """

    def __init__(
        self,
        *,
        registry: ToolRegistry,
        audit: AuditLogger,
        budget: Optional[RunBudget] = None,
        approval_policy: Optional[ApprovalPolicy] = None,
        approval_handler: Optional[ApprovalHandler] = None,
        outbound_client: Optional[ANPOutboundClient] = None,
        outbound_timeout_seconds: Optional[float] = None,
        local_runner: Optional[LocalRunner] = None,
    ) -> None:
        self.registry = registry
        self.audit = audit
        self.budget = budget or RunBudget()
        self.budget.validate()
        self.approval_policy = approval_policy or ApprovalPolicy()
        self.approval_handler = approval_handler
        self._local_runner = local_runner or (lambda task, _context: f'task:{task}')
        self._outbound_timeout = outbound_timeout_seconds
        self._outbound_delegations = 0
        self._inbound = ANPInboundAdapter(self._local_runner)
        base_outbound = outbound_client or ANPOutboundClient(
            timeout_seconds=outbound_timeout_seconds
        )
        effective_timeout = (
            outbound_timeout_seconds
            if outbound_timeout_seconds is not None
            else base_outbound._timeout_seconds
        )
        governed_transport = self._wrap_outbound_transport(base_outbound.transport)
        self._router = ANPBidirectionalRouter(
            local_runner=self._local_runner,
            outbound_client=ANPOutboundClient(
                transport=governed_transport,
                timeout_seconds=effective_timeout,
            ),
        )

    def _wrap_outbound_transport(
        self, transport: OutboundTransport
    ) -> OutboundTransport:
        def governed(
            endpoint: str, task: str, context: dict[str, Any]
        ) -> dict[str, Any]:
            self._assert_outbound_budget()
            self._record_outbound_delegation()
            return transport(endpoint, task, context)

        return governed

    @staticmethod
    def _correlation_id(payload: dict[str, Any]) -> str:
        correlation_id = str(payload.get('correlation_id') or '').strip()
        return correlation_id or uuid4().hex

    @staticmethod
    def _peer_endpoint(payload: dict[str, Any]) -> str:
        return str(payload.get('peer_endpoint') or payload.get('remote_endpoint') or '')

    def _assert_outbound_budget(self) -> None:
        if self._outbound_delegations >= self.budget.max_tool_calls:
            raise BudgetExceededError('ANP outbound delegation budget exceeded')

    def _record_outbound_delegation(self) -> None:
        self._outbound_delegations += 1

    def handle_inbound(self, payload: dict[str, Any]) -> dict[str, Any]:
        correlation_id = self._correlation_id(payload)
        peer = self._peer_endpoint(payload)
        task = str(payload.get('task') or '').strip()
        if not task:
            raise ANPAdapterError('task is required')
        context = payload.get('context') or {}
        if not isinstance(context, dict):
            raise ANPAdapterError('context must be an object')

        self.audit.record(
            'anp_inbound_received',
            correlation_id,
            **_federation_audit_fields(
                correlation_id=correlation_id,
                direction='inbound',
                peer_endpoint=peer,
                task=task,
            ),
        )

        tool_request = payload.get('tool_request')
        if isinstance(tool_request, dict):
            governed = self._handle_inbound_tool(
                task=task,
                context=context,
                tool_request=tool_request,
                correlation_id=correlation_id,
                peer=peer,
            )
            return governed.to_dict()

        result = self._inbound.try_handle_task(payload)
        self.audit.record(
            'anp_inbound_completed',
            correlation_id,
            **_federation_audit_fields(
                correlation_id=correlation_id,
                direction='inbound',
                peer_endpoint=peer,
                status=result.get('status'),
            ),
        )
        return {**result, 'correlation_id': correlation_id}

    def _handle_inbound_tool(
        self,
        *,
        task: str,
        context: dict[str, Any],
        tool_request: dict[str, Any],
        correlation_id: str,
        peer: str,
    ) -> ANPGovernedInboundResult:
        tool_name = str(tool_request.get('tool_name') or '').strip()
        if not tool_name:
            raise ANPAdapterError('tool_request.tool_name is required')
        arguments = tool_request.get('arguments') or {}
        if not isinstance(arguments, dict):
            raise ANPAdapterError('tool_request.arguments must be an object')
        call_id = str(tool_request.get('call_id') or uuid4().hex)

        runner = AgentRunner(
            registry=self.registry,
            audit=self.audit,
            budget=self.budget,
            approval_policy=self.approval_policy,
            approval_handler=self.approval_handler,
        )

        def decide(run_context: dict[str, Any]) -> ToolRequest | FinalAnswer:
            if not run_context['observations']:
                return ToolRequest(
                    tool_name=tool_name,
                    arguments=arguments,
                    call_id=call_id,
                )
            observation = run_context['observations'][0]
            if 'error' in observation:
                return FinalAnswer(
                    content='',
                    metadata={'error': observation['error']},
                )
            return FinalAnswer(content=str(observation.get('result', '')))

        run_result = runner.run(
            task=task,
            decide=decide,
            run_id=correlation_id,
            initial_context_extra={
                'anp_correlation_id': correlation_id,
                'federation_direction': 'inbound',
                **context,
            },
        )

        approval = run_result.metadata.get('approval', {})
        approval_required = run_result.status == 'pending_approval'
        self.audit.record(
            'anp_inbound_completed',
            correlation_id,
            **_federation_audit_fields(
                correlation_id=correlation_id,
                direction='inbound',
                peer_endpoint=peer,
                status='pending_approval' if approval_required else run_result.status,
                approval_required=approval_required,
                tool_name=tool_name,
            ),
        )

        if approval_required:
            return ANPGovernedInboundResult(
                status='pending_approval',
                correlation_id=correlation_id,
                run_id=run_result.run_id,
                approval=approval if isinstance(approval, dict) else {},
            )

        if run_result.status != 'completed' or run_result.final_answer is None:
            return ANPGovernedInboundResult(
                status='error',
                correlation_id=correlation_id,
                run_id=run_result.run_id,
                error=run_result.error_message or run_result.status,
            )

        return ANPGovernedInboundResult(
            status='ok',
            correlation_id=correlation_id,
            run_id=run_result.run_id,
            output=run_result.final_answer.content,
        )

    def route(
        self,
        *,
        task: str,
        route: Literal['auto', 'local', 'remote'] = 'auto',
        context: Optional[dict[str, Any]] = None,
        remote_endpoint: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> dict[str, Any]:
        cid = correlation_id or uuid4().hex
        peer = remote_endpoint or ''
        payload = context or {}

        self.audit.record(
            'anp_outbound_started',
            cid,
            **_federation_audit_fields(
                correlation_id=cid,
                direction='outbound',
                peer_endpoint=peer,
                route=route,
                task=task,
            ),
        )

        try:
            routing = self._router.route(
                task=task,
                route=route,
                context=payload,
                remote_endpoint=remote_endpoint,
            )
        except Exception as exc:
            self.audit.record(
                'anp_outbound_failed',
                cid,
                **_federation_audit_fields(
                    correlation_id=cid,
                    direction='outbound',
                    peer_endpoint=peer,
                    error=str(exc),
                ),
            )
            raise

        self.audit.record(
            'anp_route_completed',
            cid,
            **_federation_audit_fields(
                correlation_id=cid,
                direction='outbound',
                peer_endpoint=peer,
                source=routing.source,
                fallback_used=routing.fallback_used,
                agent_name=routing.agent_name,
            ),
        )
        return {
            'correlation_id': cid,
            'output': routing.output,
            'source': routing.source,
            'fallback_used': routing.fallback_used,
            'agent_name': routing.agent_name,
        }
