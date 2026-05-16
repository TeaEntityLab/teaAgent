"""AC-NEW: LSP prompt-injection smoke without external LSP binaries.

Verifies that enabling code analysis injects `lsp_context` into the model user
payload when the task mentions source-code paths.
"""

from __future__ import annotations

from teaagent import ChatAgentConfig, CodeAnalysisConfig, run_chat_agent


class _Adapter:
    provider = 'stub'

    def __init__(self) -> None:
        self.requests = []

    def complete(self, request):  # type: ignore[override]
        from teaagent.llm import LLMResponse

        self.requests.append(request)
        return LLMResponse(
            provider='stub',
            model='stub',
            content='{"type":"final","content":"ok"}',
        )


def test_code_analysis_prompt_injection_smoke(tmp_path):
    adapter = _Adapter()
    result = run_chat_agent(
        task='Inspect src/app.py and report warnings',
        adapter=adapter,
        config=ChatAgentConfig.from_root(
            tmp_path,
            code_analysis_config=CodeAnalysisConfig.from_root(tmp_path, enabled=True),
        ),
    )

    assert result.status == 'completed'
    assert adapter.requests, 'expected at least one model request'
    user_payload = adapter.requests[0].messages[0].content
    assert 'lsp_context' in user_payload
