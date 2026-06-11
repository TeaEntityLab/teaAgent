from __future__ import annotations

import sys

import pytest

from teaagent import (
    CodeModeResult,
    CodeModeSandbox,
    ContainerCodeModeBackend,
    Document,
    GraphEdge,
    KnowledgeGraph,
    ProviderProfile,
    StatelessMCPRequest,
    ToolAnnotations,
    ToolRegistry,
    UnsafeCodeError,
    assess_managed_agent_readiness,
    assess_provider_portability,
    execute_code_mode,
    graph_retrieve,
    handle_stateless_tool_request,
)


def build_registry(*, destructive: bool = False) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        name='sum_values',
        description='Sum integer values for portability and MCP tests.',
        input_schema={
            'type': 'object',
            'properties': {'a': {'type': 'integer'}, 'b': {'type': 'integer'}},
            'required': ['a', 'b'],
        },
        output_schema={
            'type': 'object',
            'properties': {'total': {'type': 'integer'}},
            'required': ['total'],
        },
        annotations=ToolAnnotations(
            read_only=not destructive, destructive=destructive, idempotent=True
        ),
        handler=lambda args: {'total': args['a'] + args['b']},
    )
    return registry


def test_graph_rag_traverses_relations_to_documents() -> None:
    graph = KnowledgeGraph()
    graph.add_document(
        Document(doc_id='doc-1', text='Alice owns Acme in logistics', source='graph')
    )
    graph.add_edge(
        GraphEdge(
            source='alice', relation='owns', target='acme', document_ids=('doc-1',)
        )
    )
    graph.add_edge(
        GraphEdge(
            source='acme',
            relation='operates',
            target='logistics',
            document_ids=('doc-1',),
        )
    )

    results = graph_retrieve('alice logistics', graph, max_depth=2)

    assert results[0].document.doc_id == 'doc-1'
    assert results[0].score > 0


def test_code_mode_executes_safe_subset() -> None:
    result = execute_code_mode(
        'total = sum(values)\ncount = len(values)',
        inputs={'values': [1, 2, 3]},
    )

    assert result.variables['total'] == 6
    assert result.variables['count'] == 3


def test_code_mode_blocks_imports_and_unknown_calls() -> None:
    with pytest.raises(UnsafeCodeError):
        execute_code_mode('import os\nvalue = 1')
    with pytest.raises(UnsafeCodeError):
        execute_code_mode("value = open('x')")


def test_code_mode_rejects_non_plain_inputs_and_outputs() -> None:
    with pytest.raises(UnsafeCodeError):
        execute_code_mode('value = len(items)', inputs={'items': object()})
    with pytest.raises(UnsafeCodeError):
        execute_code_mode('value = range(3)')


def test_code_mode_times_out_in_sandbox() -> None:
    with pytest.raises(UnsafeCodeError):
        execute_code_mode(
            'for index in range(100000000):\n    value = index',
            sandbox=CodeModeSandbox(timeout_seconds=0.01),
        )


def test_code_mode_accepts_backend_interface() -> None:
    class _Backend:
        def execute(
            self,
            code: str,
            inputs: dict[str, object],
            sandbox: CodeModeSandbox,
        ) -> CodeModeResult:
            return CodeModeResult(
                variables={
                    'code': code,
                    'value': inputs['value'],
                    'timeout': sandbox.timeout_seconds,
                }
            )

    result = execute_code_mode(
        'value = value + 1',
        inputs={'value': 4},
        sandbox=CodeModeSandbox(timeout_seconds=1.5),
        backend=_Backend(),
    )

    assert result.variables['value'] == 4
    assert result.variables['timeout'] == 1.5


def test_container_code_mode_backend_builds_isolated_command() -> None:
    backend = ContainerCodeModeBackend(image='python:3.12-alpine', runtime='podman')

    command = backend._build_command(
        CodeModeSandbox(memory_bytes=32 * 1024 * 1024, cpu_seconds=3)
    )

    assert command[:5] == ['podman', 'run', '--rm', '--network', 'none']
    assert '--read-only' in command
    assert '--cap-drop=ALL' in command
    assert '--security-opt=no-new-privileges' in command
    assert '--user=65534:65534' in command
    assert '--tmpfs=/tmp:rw,size=16m' in command
    assert '--memory' in command
    assert '32m' in command
    assert '--memory-swap' in command
    assert '--ulimit' in command
    assert 'cpu=3:3' in command
    assert '--pids-limit' in command


def test_container_code_mode_backend_rejects_empty_image() -> None:
    with pytest.raises(UnsafeCodeError):
        ContainerCodeModeBackend(image='')


def test_container_code_mode_backend_can_require_image_digest() -> None:
    with pytest.raises(UnsafeCodeError, match='pinned by digest'):
        ContainerCodeModeBackend(image='python:3.12-alpine', require_image_digest=True)

    backend = ContainerCodeModeBackend(
        image='python@sha256:' + 'a' * 64,
        require_image_digest=True,
    )

    assert backend.image == 'python@sha256:' + 'a' * 64


def test_container_code_mode_backend_can_restrict_allowed_images() -> None:
    with pytest.raises(UnsafeCodeError, match='allowlist'):
        ContainerCodeModeBackend(
            image='python:3.12-alpine',
            allowed_images=frozenset({'python@sha256:' + 'a' * 64}),
        )

    image = 'python@sha256:' + 'a' * 64
    backend = ContainerCodeModeBackend(
        image=image,
        allowed_images=frozenset({image}),
    )

    assert backend.image == image


def test_container_code_mode_backend_enforces_streaming_output_limit() -> None:
    class _LocalBackend(ContainerCodeModeBackend):
        def _build_command(self, sandbox: CodeModeSandbox) -> list[str]:
            return [
                sys.executable,
                '-c',
                "import sys; sys.stdin.read(); sys.stdout.write('x' * 1024); sys.stdout.flush()",
            ]

    backend = _LocalBackend(image='local-test')

    with pytest.raises(UnsafeCodeError, match='exceeded output limit'):
        backend.execute(
            'value = 1',
            {},
            CodeModeSandbox(timeout_seconds=2, max_output_bytes=16),
        )


def test_stateless_mcp_request_executes_via_registry() -> None:
    request = StatelessMCPRequest.create(
        tool_name='sum_values',
        arguments={'a': 2, 'b': 5},
        client_capabilities={'stateless': True},
        shared_state={'tenant_id': 't1'},
    )

    response = handle_stateless_tool_request(request, build_registry())

    assert response.request_id == request.request_id
    assert response.result['total'] == 7
    assert response.shared_state['tenant_id'] == 't1'
    assert response.server_capabilities['stateless']


def test_managed_agent_readiness_flags_missing_hitl_for_destructive_tool() -> None:
    report = assess_managed_agent_readiness(
        registry=build_registry(destructive=True),
        has_external_state=False,
        has_audit_log=True,
        has_budget_limits=True,
        has_human_approval=False,
    )

    assert not report.ready
    assert any('needs HITL' in finding.message for finding in report.findings)


def test_provider_portability_reports_missing_capabilities() -> None:
    results = assess_provider_portability(
        [
            ProviderProfile(
                name='portable',
                model='model-a',
                capabilities=frozenset(
                    {
                        'tool_calling',
                        'structured_output',
                        'system_prompt',
                        'prompt_caching',
                    }
                ),
                limits={'max_context_tokens': 200000},
            ),
            ProviderProfile(
                name='limited',
                model='model-b',
                capabilities=frozenset({'system_prompt'}),
                limits={'max_context_tokens': 32000},
            ),
        ]
    )

    assert results[0].portable
    assert not results[1].portable
    assert 'tool_calling' in results[1].missing_capabilities
    assert results[1].warnings
