from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class ManagedRuntimeAdapter(Protocol):
    def run_task(self, task: str, *, context: dict[str, Any]) -> str: ...

    def health_check(self) -> bool: ...


@dataclass(frozen=True)
class ManagedRunResult:
    output: str
    runtime: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ManagedAgentRunner:
    def __init__(
        self, adapter: ManagedRuntimeAdapter, *, runtime_name: str = ''
    ) -> None:
        self._adapter = adapter
        self._runtime_name = runtime_name or type(adapter).__name__

    def run(
        self, task: str, *, context: Optional[dict[str, Any]] = None
    ) -> ManagedRunResult:
        output = self._adapter.run_task(task, context=context or {})
        return ManagedRunResult(output=output, runtime=self._runtime_name)

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
        response = client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{'role': 'user', 'content': task}],
        )
        return response.content[0].text if response.content else ''

    def health_check(self) -> bool:  # pragma: no cover
        try:
            import anthropic

            anthropic.Anthropic(api_key=self._api_key).models.list()
            return True
        except Exception:
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
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id, assistant_id=self._assistant_id
        )
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
        except Exception:
            return False


class GoogleADKRuntime:
    def __init__(
        self,
        *,
        agent_name: str,
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
        self._project_id = project_id
        self._location = location

    def run_task(
        self, task: str, *, context: dict[str, Any]
    ) -> str:  # pragma: no cover
        raise NotImplementedError(
            'GoogleADKRuntime.run_task: wire to google.adk runner'
        )

    def health_check(self) -> bool:  # pragma: no cover
        return False


class VertexAgentRuntime:
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

    def run_task(
        self, task: str, *, context: dict[str, Any]
    ) -> str:  # pragma: no cover
        raise NotImplementedError(
            'VertexAgentRuntime.run_task: wire to Vertex Agent Engine'
        )

    def health_check(self) -> bool:  # pragma: no cover
        return False
