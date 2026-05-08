from __future__ import annotations

import unittest

from teaagent import (
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


class P2PrimitiveTests(unittest.TestCase):
    def test_graph_rag_traverses_relations_to_documents(self) -> None:
        graph = KnowledgeGraph()
        graph.add_document(
            Document(
                doc_id='doc-1', text='Alice owns Acme in logistics', source='graph'
            )
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

        self.assertEqual(results[0].document.doc_id, 'doc-1')
        self.assertGreater(results[0].score, 0)

    def test_code_mode_executes_safe_subset(self) -> None:
        result = execute_code_mode(
            'total = sum(values)\ncount = len(values)',
            inputs={'values': [1, 2, 3]},
        )

        self.assertEqual(result.variables['total'], 6)
        self.assertEqual(result.variables['count'], 3)

    def test_code_mode_blocks_imports_and_unknown_calls(self) -> None:
        with self.assertRaises(UnsafeCodeError):
            execute_code_mode('import os\nvalue = 1')
        with self.assertRaises(UnsafeCodeError):
            execute_code_mode("value = open('x')")

    def test_stateless_mcp_request_executes_via_registry(self) -> None:
        request = StatelessMCPRequest.create(
            tool_name='sum_values',
            arguments={'a': 2, 'b': 5},
            client_capabilities={'stateless': True},
            shared_state={'tenant_id': 't1'},
        )

        response = handle_stateless_tool_request(request, build_registry())

        self.assertEqual(response.request_id, request.request_id)
        self.assertEqual(response.result['total'], 7)
        self.assertEqual(response.shared_state['tenant_id'], 't1')
        self.assertTrue(response.server_capabilities['stateless'])

    def test_managed_agent_readiness_flags_missing_hitl_for_destructive_tool(
        self,
    ) -> None:
        report = assess_managed_agent_readiness(
            registry=build_registry(destructive=True),
            has_external_state=False,
            has_audit_log=True,
            has_budget_limits=True,
            has_human_approval=False,
        )

        self.assertFalse(report.ready)
        self.assertTrue(
            any('needs HITL' in finding.message for finding in report.findings)
        )

    def test_provider_portability_reports_missing_capabilities(self) -> None:
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

        self.assertTrue(results[0].portable)
        self.assertFalse(results[1].portable)
        self.assertIn('tool_calling', results[1].missing_capabilities)
        self.assertTrue(results[1].warnings)


if __name__ == '__main__':
    unittest.main()
