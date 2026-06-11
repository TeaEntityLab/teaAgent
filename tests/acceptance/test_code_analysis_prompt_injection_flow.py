"""Test module for LSP code analysis prompt injection.

This module tests that enabling code analysis injects LSP context into the model
user payload when the task mentions source-code paths. This ensures that code analysis
results are available to the model without requiring external LSP binaries.

Key concepts tested:
- Prompt Injection: Code analysis injects lsp_context into user payload
- Path Detection: Task mentions of source-code paths trigger code analysis
- Context Enrichment: LSP context enriches model with code understanding
- Configuration: CodeAnalysisConfig enables/disables code analysis
- Smoke Test: Validation without external LSP binaries

Acceptance Criteria:
- AC1: Enabling code analysis injects lsp_context into user payload
- AC2: Task mentions of source-code paths trigger code analysis
- AC3: lsp_context is included in the model request messages
- AC4: Code analysis works without external LSP binaries (smoke test)
- AC5: CodeAnalysisConfig.from_root with enabled=True enables code analysis

Technical Details:
- CodeAnalysisConfig controls code analysis feature
- lsp_context is injected into the user message content
- Path detection identifies Python/TS/JS paths in task text
- Code analysis uses tree-sitter for relation extraction
- Smoke test validates the injection mechanism without full LSP

References:
- Code analysis design: /docs/architecture/code_analysis.md
- LSP integration: /docs/integration/lsp.md
"""

from __future__ import annotations

from teaagent import ChatAgentConfig, CodeAnalysisConfig, run_chat_agent


class _Adapter:
    provider = 'stub'

    def __init__(self) -> None:
        self.requests = []

    def complete(self, request):
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
        ChatAgentConfig.from_root(
            tmp_path,
            code_analysis_config=CodeAnalysisConfig.from_root(tmp_path, enabled=True),
        ),
        'Inspect src/app.py and report warnings',
        adapter=adapter,
    )

    assert result.status == 'completed'
    assert adapter.requests, 'expected at least one model request'
    user_payload = adapter.requests[0].messages[0].content
    assert 'lsp_context' in user_payload
