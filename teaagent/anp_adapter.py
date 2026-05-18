from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Optional

from teaagent.agentcard import A2AClient


class ANPAdapterError(RuntimeError):
    """Raised when ANP adapter input or routing is invalid."""


LocalRunner = Callable[[str, dict[str, Any]], str]
OutboundTransport = Callable[[str, str, dict[str, Any]], dict[str, Any]]


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

    def __init__(self, *, transport: Optional[OutboundTransport] = None) -> None:
        self._transport = transport or self._default_transport

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
    ) -> ANPDelegationResult:
        payload = self._transport(endpoint, task, context or {})
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
