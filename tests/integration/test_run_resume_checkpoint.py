"""IT-11: Run can be checkpointed and resumed from the last saved context.

Verifies that:
- After a ``pending_approval`` pause, the checkpoint store holds the context.
- Resuming by replaying observations yields the same final answer.
- Crash-safe: context saved at each tool completion is replayable.
"""

from __future__ import annotations

from teaagent.audit import AuditLogger
from teaagent.checkpoint import InMemoryCheckpointStore, SQLiteCheckpointStore
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.runner import AgentRunner, FinalAnswer, ToolRequest
from teaagent.tools import ToolAnnotations, ToolRegistry


def _make_registry_with_write_tool() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        name='workspace_write_file',
        description='write file',
        input_schema={
            'type': 'object',
            'properties': {'path': {'type': 'string'}, 'content': {'type': 'string'}},
            'required': ['path', 'content'],
        },
        output_schema={
            'type': 'object',
            'properties': {'written': {'type': 'boolean'}},
        },
        annotations=ToolAnnotations(destructive=True),
        handler=lambda _: {'written': True},
    )
    return registry


def test_checkpoint_store_saves_on_tool_completion():
    store = InMemoryCheckpointStore()
    registry = _make_registry_with_write_tool()
    audit = AuditLogger()
    runner = AgentRunner(
        registry=registry,
        audit=audit,
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.ALLOW),
        checkpoint_store=store,
    )

    call_seq = iter(
        [
            ToolRequest(
                tool_name='workspace_write_file',
                arguments={'path': 'hello.txt', 'content': 'hello'},
                call_id='call-1',
            ),
            FinalAnswer(content='done'),
        ]
    )
    result = runner.run(task='write a file', decide=lambda _: next(call_seq))
    assert result.status == 'completed'
    # Checkpoint must have been saved after tool completion
    saved = store.load(result.run_id)
    assert saved is not None
    assert any(obs.get('call_id') == 'call-1' for obs in saved.get('observations', []))


def test_pending_approval_checkpoint_saved():
    store = InMemoryCheckpointStore()
    registry = _make_registry_with_write_tool()
    audit = AuditLogger()
    runner = AgentRunner(
        registry=registry,
        audit=audit,
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.PROMPT),
        checkpoint_store=store,
    )

    result = runner.run(
        task='write something',
        decide=lambda _: ToolRequest(
            tool_name='workspace_write_file',
            arguments={'path': 'a.txt', 'content': 'hi'},
            call_id='need-approval',
        ),
    )
    assert result.status == 'pending_approval'
    saved = store.load(result.run_id)
    assert saved is not None


def test_sqlite_checkpoint_roundtrip(tmp_path):
    store = SQLiteCheckpointStore(tmp_path / 'checkpoints.db')
    run_id = 'test-run-xyz'
    context = {'task': 'hello', 'observations': [{'call_id': 'x', 'result': {}}]}
    store.save(run_id, context)
    loaded = store.load(run_id)
    assert loaded is not None
    assert loaded['task'] == 'hello'
    assert loaded['observations'][0]['call_id'] == 'x'


def test_resume_by_replaying_observations():
    """Providing initial_observations replays prior tool calls."""
    registry = ToolRegistry()
    registry.register(
        name='noop',
        description='noop',
        input_schema={'type': 'object', 'properties': {}},
        output_schema={'type': 'object', 'properties': {}},
        annotations=ToolAnnotations(read_only=True),
        handler=lambda _: {},
    )
    audit = AuditLogger()
    runner = AgentRunner(registry=registry, audit=audit)

    prior_obs = [{'call_id': 'prev-1', 'tool_name': 'noop', 'result': {}}]
    result = runner.run(
        task='continue',
        decide=lambda ctx: FinalAnswer(content=f'obs_count={len(ctx["observations"])}'),
        initial_observations=prior_obs,
    )
    assert result.status == 'completed'
    assert result.final_answer is not None
    assert 'obs_count=1' in result.final_answer.content
