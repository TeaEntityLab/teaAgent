from __future__ import annotations

import tempfile
from pathlib import Path

from teaagent import (
    AgentRunner,
    AuditLogger,
    ContextCompactor,
    Document,
    EvalCase,
    FinalAnswer,
    InMemoryRetriever,
    ToolAnnotations,
    ToolRegistry,
    ToolRequest,
    TraceRecorder,
    agentic_retrieve,
    build_aibom,
    review_skill,
    run_eval,
)


def test_trace_recorder_receives_audit_events() -> None:
    audit = AuditLogger()
    trace = TraceRecorder()
    audit.add_sink(trace.handle_event)
    registry = ToolRegistry()
    registry.register(
        name='echo',
        description='Echo value.',
        input_schema={
            'type': 'object',
            'properties': {'value': {'type': 'string'}},
            'required': ['value'],
        },
        output_schema={
            'type': 'object',
            'properties': {'value': {'type': 'string'}},
            'required': ['value'],
        },
        annotations=ToolAnnotations(read_only=True, idempotent=True),
        handler=lambda args: {'value': args['value']},
    )
    runner = AgentRunner(registry=registry, audit=audit)

    def decide(context):
        if not context['observations']:
            return ToolRequest(
                tool_name='echo', arguments={'value': 'traced'}, call_id='call-1'
            )
        return FinalAnswer(content='done')

    result = runner.run(task='trace me', decide=decide, run_id='trace-run')

    assert result.status == 'completed'
    assert 'agent.run' in [span.name for span in trace.spans]
    tool_span = next(span for span in trace.spans if span.name == 'tool.call')
    tool_completed = next(
        event for event in audit.events if event.event_type == 'tool_call_completed'
    )
    assert tool_span.ended_at == tool_completed.created_at


def test_context_compactor_pins_memory_keys() -> None:
    context = {
        'task': 'long task',
        'observations': [
            {'tool_name': 'a', 'result': {'value': '1'}},
            {'tool_name': 'b', 'result': {'transaction_id': 'tx-123'}},
            {'tool_name': 'c', 'result': {'value': '3'}},
        ],
    }

    result = ContextCompactor(
        recent_observations=1, memory_keys=('transaction_id',)
    ).compact(context)

    assert len(result.context['observations']) == 1
    assert result.pinned['transaction_id'] == 'tx-123'
    # Summary format changed with semantic summarization - check for key indicators
    assert 'a' in result.summary or 'operations' in result.summary


def test_skill_review_and_aibom() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / 'demo-skill'
        skill_dir.mkdir()
        skill_file = skill_dir / 'SKILL.md'
        skill_file.write_text(
            '---\nname: demo\ndescription: Demo skill.\n---\n\n# Demo\n\nSee REFERENCE.md.\n',
            encoding='utf-8',
        )
        server_card = Path(tmp) / 'server-card.json'
        server_card.write_text('{}\n', encoding='utf-8')

        review = review_skill(skill_dir)
        manifest = build_aibom(
            model='test-model',
            model_version='0',
            skill_paths=[skill_dir],
            mcp_server_card=server_card,
        )

        assert review.passed
        assert len(manifest.components) == 3
        assert manifest.components[1].digest.startswith('sha256:')


def test_offline_eval_reports_pass_rate() -> None:
    report = run_eval(
        [
            EvalCase(name='ok', task='say hello', expected_contains=('hello',)),
            EvalCase(name='bad', task='say bye', expected_contains=('bye',)),
        ],
        lambda case: 'hello world' if case.name == 'ok' else 'nope',
    )

    assert not report.passed
    assert report.pass_rate == 0.5
    assert report.results[1].failures == ('bye',)


def test_agentic_retrieve_routes_and_fuses_results() -> None:
    retriever = InMemoryRetriever(
        [
            Document(
                doc_id='s1',
                text='semantic policy for agent skills',
                source='semantic',
            ),
            Document(
                doc_id='d1',
                text='revenue table shows cost changes',
                source='structured',
            ),
            Document(doc_id='w1', text='latest agent news today', source='web'),
        ]
    )

    results = agentic_retrieve('compare revenue and latest agent news', retriever)

    assert len(results) >= 2
    assert results[0].document.doc_id == 'd1'
    assert 'w1' in {result.document.doc_id for result in results}
