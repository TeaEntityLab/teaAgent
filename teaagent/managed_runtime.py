from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import secrets
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# Sentinel so callers can pass audit_logger=None without ambiguity.
_AUDIT_UNSET = object()


@runtime_checkable
class ManagedRuntimeAdapter(Protocol):
    def run_task(self, task: str, *, context: dict[str, Any]) -> str: ...

    def health_check(self) -> bool: ...


@dataclass(frozen=True)
class ManagedRunResult:
    output: str
    runtime: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ManagedRuntimeCapability:
    name: str
    runtime_class: str
    sdk_import: str
    install_hint: str
    status: str
    experimental: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'runtime_class': self.runtime_class,
            'sdk_import': self.sdk_import,
            'install_hint': self.install_hint,
            'status': self.status,
            'experimental': self.experimental,
        }


def managed_runtime_context(
    registry: Any,
    *,
    workspace_root: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    context = dict(extra or {})
    context['tools'] = registry.mcp_metadata()
    if workspace_root is not None:
        context['workspace_root'] = workspace_root
    return context


class ManagedAgentRunner:
    def __init__(
        self, adapter: ManagedRuntimeAdapter, *, runtime_name: str = ''
    ) -> None:
        self._adapter = adapter
        self._runtime_name = runtime_name or type(adapter).__name__

    def run(
        self,
        task: str,
        *,
        context: Optional[dict[str, Any]] = None,
        audit_logger: Any = _AUDIT_UNSET,
        run_id: str = '',
    ) -> ManagedRunResult:
        ctx = context or {}
        context_keys = sorted(ctx.keys())
        tools = ctx.get('tools', [])
        tool_count = len(tools) if isinstance(tools, list) else 0
        _log = None if audit_logger is _AUDIT_UNSET else audit_logger
        if _log is not None:
            _log.record(
                'managed_task_started',
                run_id,
                runtime=self._runtime_name,
                task=task,
                context_keys=context_keys,
                tool_count=tool_count,
            )
        try:
            output = self._adapter.run_task(task, context=ctx)
        except Exception as exc:
            if _log is not None:
                _log.record(
                    'managed_task_failed',
                    run_id,
                    runtime=self._runtime_name,
                    error=str(exc),
                    context_keys=context_keys,
                    tool_count=tool_count,
                )
            raise
        if _log is not None:
            _log.record(
                'managed_task_completed',
                run_id,
                runtime=self._runtime_name,
                output_length=len(output),
                context_keys=context_keys,
                tool_count=tool_count,
            )
        return ManagedRunResult(
            output=output,
            runtime=self._runtime_name,
            metadata={
                'run_id': run_id,
                'context_keys': context_keys,
                'tool_count': tool_count,
            },
        )

    def healthy(self) -> bool:
        return self._adapter.health_check()


# ---------------------------------------------------------------------------
# Provider stubs — each raises ImportError with install instructions when the
# required optional SDK is absent, matching the zero-dependency posture.
# ---------------------------------------------------------------------------

_INSTALL_ANTHROPIC = 'pip install anthropic'
_INSTALL_OPENAI = 'pip install openai'
_INSTALL_ADK = 'pip install google-adk'
_INSTALL_VERTEX = 'pip install google-cloud-aiplatform'

_RUNTIME_CAPABILITY_SPECS = (
    ('anthropic', 'AnthropicManagedRuntime', 'anthropic', _INSTALL_ANTHROPIC),
    ('openai', 'OpenAIManagedRuntime', 'openai', _INSTALL_OPENAI),
    ('google-adk', 'GoogleADKRuntime', 'google.adk', _INSTALL_ADK),
    (
        'vertex-agent-engine',
        'VertexAgentRuntime',
        'google.cloud.aiplatform',
        _INSTALL_VERTEX,
    ),
)


def managed_runtime_capabilities() -> list[dict[str, Any]]:
    """Return optional managed runtime adapter availability without importing SDKs."""

    capabilities: list[dict[str, Any]] = []
    for name, runtime_class, sdk_import, install_hint in _RUNTIME_CAPABILITY_SPECS:
        status = 'available' if _sdk_import_available(sdk_import) else 'missing_sdk'
        capabilities.append(
            ManagedRuntimeCapability(
                name=name,
                runtime_class=runtime_class,
                sdk_import=sdk_import,
                install_hint=install_hint,
                status=status,
            ).to_dict()
        )
    return capabilities


def _sdk_import_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False


def _format_vertex_output(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ('output', 'text', 'message', 'response', 'result', 'content'):
            if key in value:
                return _format_vertex_output(value[key])
        return json.dumps(value, default=str)
    if isinstance(value, list):
        return '\n'.join(_format_vertex_output(item) for item in value)
    return str(value)


def _adk_events_to_text(events: Iterable[Any]) -> str:
    parts: list[str] = []
    for event in events:
        if (
            hasattr(event, 'is_final_response')
            and callable(event.is_final_response)
            and not event.is_final_response()
        ):
            continue
        content = getattr(event, 'content', None)
        if content is None:
            continue
        for part in getattr(content, 'parts', None) or []:
            text = getattr(part, 'text', None)
            if text:
                parts.append(str(text))
    if parts:
        return '\n'.join(parts)
    return ''


def _load_adk_agent(*, agent_module: str, agent: Optional[Any] = None) -> Any:
    if agent is not None:
        return agent
    module = importlib.import_module(agent_module)
    loaded = getattr(module, 'root_agent', None)
    if loaded is None and hasattr(module, 'get_agent'):
        loaded = module.get_agent()
    if loaded is None:
        raise ValueError(
            f'Module {agent_module!r} must define root_agent or get_agent()'
        )
    return loaded


def _vertex_agent_resource_name(
    agent_id: str, *, project_id: str, location: str
) -> str:
    if agent_id.startswith('projects/'):
        return agent_id
    return f'projects/{project_id}/locations/{location}/reasoningEngines/{agent_id}'


def _vertex_query_engine(engine: Any, task: str, *, context: dict[str, Any]) -> Any:
    user_id = str(context.get('user_id', 'teaagent'))
    session_id = context.get('session_id')
    adk_kwargs: dict[str, Any] = {'message': task, 'user_id': user_id}
    if session_id is not None:
        adk_kwargs['session_id'] = session_id

    query = getattr(engine, 'query', None)
    if callable(query):
        for kwargs in (
            adk_kwargs,
            {'input': task},
            {'input': {'message': task, 'user_id': user_id}},
        ):
            try:
                return query(**kwargs)
            except TypeError:
                continue

    stream_query = getattr(engine, 'stream_query', None)
    if callable(stream_query):
        try:
            stream = stream_query(**adk_kwargs)
        except TypeError:
            stream = stream_query(input=task)
        return list(stream)

    raise RuntimeError(
        'Agent Engine does not expose a supported query or stream_query method'
    )


class AnthropicManagedRuntime:
    def __init__(
        self,
        *,
        agent_id: str,
        api_key: Optional[str] = None,
        model: str = 'claude-opus-4-5',
    ) -> None:
        try:
            import anthropic as _anthropic  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                f'AnthropicManagedRuntime requires the Anthropic SDK. '
                f'Install with: {_INSTALL_ANTHROPIC}'
            ) from exc
        self._agent_id = agent_id
        self._api_key = api_key
        self._model = model

    def run_task(
        self, task: str, *, context: dict[str, Any]
    ) -> str:  # pragma: no cover
        import anthropic

        client = anthropic.Anthropic(api_key=self._api_key)
        kwargs: dict[str, Any] = {
            'model': self._model,
            'max_tokens': context.get('max_tokens', 1024),
            'messages': [{'role': 'user', 'content': task}],
        }
        tools_list = context.get('tools', [])
        if tools_list:
            kwargs['tools'] = [
                {
                    'name': t['name'],
                    'description': t.get('description', ''),
                    'input_schema': t.get(
                        'input_schema', {'type': 'object', 'properties': {}}
                    ),
                }
                for t in tools_list
            ]
        response = client.messages.create(**kwargs)
        parts = []
        for block in response.content:
            if hasattr(block, 'text'):
                parts.append(block.text)
            elif getattr(block, 'type', None) == 'tool_use':
                parts.append(f'[tool_call:{block.name}:{block.id}]')
        return '\n'.join(filter(None, parts))

    def health_check(self) -> bool:  # pragma: no cover
        try:
            import anthropic

            anthropic.Anthropic(api_key=self._api_key).models.list()
            return True
        except (ImportError, OSError, ValueError, ConnectionError) as exc:
            logger.debug('Anthropic health check failed: %s', exc)
            return False


class OpenAIManagedRuntime:
    def __init__(
        self,
        *,
        assistant_id: str,
        api_key: Optional[str] = None,
        model: str = 'gpt-4o',
    ) -> None:
        try:
            import openai as _openai  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                f'OpenAIManagedRuntime requires the OpenAI SDK. '
                f'Install with: {_INSTALL_OPENAI}'
            ) from exc
        self._assistant_id = assistant_id
        self._api_key = api_key
        self._model = model

    def run_task(
        self, task: str, *, context: dict[str, Any]
    ) -> str:  # pragma: no cover
        import openai

        client = openai.OpenAI(api_key=self._api_key)
        thread = client.beta.threads.create()
        client.beta.threads.messages.create(
            thread_id=thread.id, role='user', content=task
        )
        run_kwargs: dict[str, Any] = {
            'thread_id': thread.id,
            'assistant_id': self._assistant_id,
        }
        tools_list = context.get('tools', [])
        if tools_list:
            run_kwargs['tools'] = [
                {
                    'type': 'function',
                    'function': {
                        'name': t['name'],
                        'description': t.get('description', ''),
                        'parameters': t.get(
                            'input_schema', {'type': 'object', 'properties': {}}
                        ),
                    },
                }
                for t in tools_list
            ]
        run = client.beta.threads.runs.create_and_poll(**run_kwargs)
        messages = client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id)
        for msg in messages.data:
            if msg.role == 'assistant':
                return ''.join(
                    block.text.value for block in msg.content if hasattr(block, 'text')
                )
        return ''

    def health_check(self) -> bool:  # pragma: no cover
        try:
            import openai

            openai.OpenAI(api_key=self._api_key).models.list()
            return True
        except (ImportError, OSError, ValueError, ConnectionError) as exc:
            logger.debug('OpenAI health check failed: %s', exc)
            return False


class GoogleADKRuntime:
    """Run an ADK agent locally via ``google.adk.runners.Runner``."""

    def __init__(
        self,
        *,
        agent_name: str,
        agent: Optional[Any] = None,
        agent_module: Optional[str] = None,
        project_id: Optional[str] = None,
        location: str = 'us-central1',
    ) -> None:
        try:
            import google.adk as _adk  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                f'GoogleADKRuntime requires the Google ADK. '
                f'Install with: {_INSTALL_ADK}'
            ) from exc
        self._agent_name = agent_name
        self._agent = agent
        self._agent_module = agent_module
        self._project_id = project_id
        self._location = location

    def run_task(self, task: str, *, context: dict[str, Any]) -> str:
        from google.adk.runners import Runner
        from google.adk.sessions.in_memory_session_service import (
            InMemorySessionService,
        )
        from google.genai import types

        agent_module = context.get('agent_module', self._agent_module)
        agent = context.get('agent', self._agent)
        if agent is None and not agent_module:
            raise ValueError(
                'GoogleADKRuntime requires an agent: pass agent= or '
                'agent_module= at construction, or provide agent/agent_module '
                'in the run context'
            )
        if agent is None:
            assert agent_module is not None
            agent = _load_adk_agent(agent_module=str(agent_module), agent=None)

        session_service = InMemorySessionService()
        runner = Runner(
            app_name=self._agent_name,
            agent=agent,
            session_service=session_service,
        )
        user_id = str(context.get('user_id', 'teaagent'))
        session_id = str(context.get('session_id', secrets.token_hex(8)))
        message = types.Content(
            role='user',
            parts=[types.Part(text=task)],
        )
        events = runner.run(
            user_id=user_id,
            session_id=session_id,
            new_message=message,
        )
        output = _adk_events_to_text(events)
        if output:
            return output
        return ''

    def health_check(self) -> bool:
        try:
            if self._agent is not None or self._agent_module:
                if self._agent_module:
                    _load_adk_agent(agent_module=self._agent_module, agent=self._agent)
                return True
            import google.adk  # noqa: F401

            return True
        except (ImportError, OSError, ValueError, TypeError) as exc:
            logger.debug('Google ADK health check failed: %s', exc)
            return False


class VertexAgentRuntime:
    """Query a deployed Vertex AI Agent Engine (reasoning engine)."""

    def __init__(
        self,
        *,
        agent_id: str,
        project_id: Optional[str] = None,
        location: str = 'us-central1',
    ) -> None:
        try:
            import google.cloud.aiplatform as _vertex  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                f'VertexAgentRuntime requires the Vertex AI SDK. '
                f'Install with: {_INSTALL_VERTEX}'
            ) from exc
        self._agent_id = agent_id
        self._project_id = project_id
        self._location = location
        self._engine: Any = None

    def _resolve_project_id(self, context: dict[str, Any]) -> str:
        project_id = context.get('project_id', self._project_id)
        if not project_id:
            raise ValueError(
                'VertexAgentRuntime requires project_id at construction or '
                'in the run context'
            )
        return str(project_id)

    def _get_engine(self, *, context: Optional[dict[str, Any]] = None) -> Any:
        if self._engine is not None:
            return self._engine
        import vertexai
        from vertexai import agent_engines

        ctx = context or {}
        project_id = self._resolve_project_id(ctx)
        location = str(ctx.get('location', self._location))
        vertexai.init(project=project_id, location=location)
        resource_name = _vertex_agent_resource_name(
            self._agent_id,
            project_id=project_id,
            location=location,
        )
        self._engine = agent_engines.get(resource_name)
        return self._engine

    def run_task(self, task: str, *, context: dict[str, Any]) -> str:
        engine = self._get_engine(context=context)
        raw = _vertex_query_engine(engine, task, context=context)
        if isinstance(raw, list):
            return '\n'.join(_format_vertex_output(item) for item in raw)
        return _format_vertex_output(raw)

    def health_check(self) -> bool:
        try:
            engine = self._get_engine()
            return bool(getattr(engine, 'resource_name', None))
        except (ImportError, OSError, ValueError, ConnectionError) as exc:
            logger.debug('Vertex AI health check failed: %s', exc)
            return False
