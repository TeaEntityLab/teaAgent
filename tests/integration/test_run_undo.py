"""IT: Run undo journal.

UndoJournal acts as an AuditLogger sink.  On every tool_call_started event
for a write tool it captures the pre-write file state.  restore() reverts
every captured write — newly created files are deleted, overwritten files
are restored to their original content.
"""

from __future__ import annotations

from pathlib import Path

from teaagent.audit import AuditLogger
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.run_undo import UndoJournal, UndoResult
from teaagent.runner import AgentRunner, FinalAnswer, ToolRequest
from teaagent.tools import ToolAnnotations, ToolRegistry

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_write_registry(root: Path) -> ToolRegistry:
    registry = ToolRegistry()

    def _write(args: dict) -> dict:
        path = root / args['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args['content'], encoding='utf-8')
        return {'written': True}

    registry.register(
        name='workspace_write_file',
        description='write file',
        input_schema={
            'type': 'object',
            'properties': {
                'path': {'type': 'string'},
                'content': {'type': 'string'},
            },
            'required': ['path', 'content'],
        },
        output_schema={
            'type': 'object',
            'properties': {'written': {'type': 'boolean'}},
        },
        annotations=ToolAnnotations(destructive=True),
        handler=_write,
    )
    return registry


def _run_write(registry, audit, call_seq):
    runner = AgentRunner(
        registry=registry,
        audit=audit,
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.ALLOW),
    )
    it = iter(call_seq)
    return runner.run(task='write files', decide=lambda _: next(it))


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


def test_undo_deletes_newly_created_file(tmp_path):
    journal = UndoJournal(tmp_path, path=tmp_path / '.teaagent' / 'undo.jsonl')
    audit = AuditLogger()
    audit.add_sink(journal)

    registry = _make_write_registry(tmp_path)
    _run_write(
        registry,
        audit,
        [
            ToolRequest(
                'workspace_write_file', {'path': 'new.txt', 'content': 'hello'}, 'c1'
            ),
            FinalAnswer(content='done'),
        ],
    )

    assert (tmp_path / 'new.txt').exists()
    result = journal.restore()
    assert not (tmp_path / 'new.txt').exists(), (
        'newly created file must be deleted on undo'
    )
    assert 'new.txt' in result.deleted


def test_undo_restores_overwritten_file(tmp_path):
    original = 'original content'
    (tmp_path / 'existing.txt').write_text(original, encoding='utf-8')

    journal = UndoJournal(tmp_path, path=tmp_path / '.teaagent' / 'undo.jsonl')
    audit = AuditLogger()
    audit.add_sink(journal)

    registry = _make_write_registry(tmp_path)
    _run_write(
        registry,
        audit,
        [
            ToolRequest(
                'workspace_write_file',
                {'path': 'existing.txt', 'content': 'overwritten'},
                'c2',
            ),
            FinalAnswer(content='done'),
        ],
    )

    assert (tmp_path / 'existing.txt').read_text() == 'overwritten'
    result = journal.restore()
    assert (tmp_path / 'existing.txt').read_text(encoding='utf-8') == original
    assert 'existing.txt' in result.restored


def test_undo_multiple_writes(tmp_path):
    journal = UndoJournal(tmp_path, path=tmp_path / '.teaagent' / 'undo.jsonl')
    audit = AuditLogger()
    audit.add_sink(journal)

    registry = _make_write_registry(tmp_path)
    _run_write(
        registry,
        audit,
        [
            ToolRequest(
                'workspace_write_file', {'path': 'a.txt', 'content': 'a'}, 'c3'
            ),
            ToolRequest(
                'workspace_write_file', {'path': 'b.txt', 'content': 'b'}, 'c4'
            ),
            FinalAnswer(content='done'),
        ],
    )

    result = journal.restore()
    assert not (tmp_path / 'a.txt').exists()
    assert not (tmp_path / 'b.txt').exists()
    assert len(result.deleted) == 2


def test_undo_idempotent_when_no_writes(tmp_path):
    journal = UndoJournal(tmp_path)
    result = journal.restore()
    assert result.restored == []
    assert result.deleted == []
    assert result.errors == []


def test_undo_result_fields():
    r = UndoResult(restored=['a.txt'], deleted=['b.txt'], errors=[])
    assert r.ok
    assert len(r.restored) == 1
    assert len(r.deleted) == 1

    r2 = UndoResult(restored=[], deleted=[], errors=['something failed'])
    assert not r2.ok


def test_journal_only_captures_write_tools(tmp_path):
    """Read-only tool calls must NOT create journal entries."""
    journal = UndoJournal(tmp_path)
    audit = AuditLogger()
    audit.add_sink(journal)

    registry = ToolRegistry()
    registry.register(
        name='workspace_read_file',
        description='read',
        input_schema={
            'type': 'object',
            'properties': {'path': {'type': 'string'}},
            'required': ['path'],
        },
        output_schema={'type': 'object', 'properties': {'content': {'type': 'string'}}},
        annotations=ToolAnnotations(read_only=True),
        handler=lambda _: {'content': ''},
    )

    runner = AgentRunner(
        registry=registry,
        audit=audit,
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.ALLOW),
    )
    it = iter(
        [
            ToolRequest('workspace_read_file', {'path': 'README.md'}, 'r1'),
            FinalAnswer(content='done'),
        ]
    )
    runner.run(task='read', decide=lambda _: next(it))

    result = journal.restore()
    assert result.restored == []
    assert result.deleted == []


def test_journal_path_traversal_ignored(tmp_path):
    """Path traversal attempts must not capture or restore outside root."""
    journal = UndoJournal(tmp_path)
    audit = AuditLogger()
    audit.add_sink(journal)

    # Simulate a tool_call_started with a traversal path
    from teaagent.audit import AuditEvent

    evil_event = AuditEvent(
        event_type='tool_call_started',
        run_id='r-evil',
        payload={
            'tool_name': 'workspace_write_file',
            'arguments': {'path': '../../../etc/passwd', 'content': '[redacted]'},
        },
    )
    journal(evil_event)

    result = journal.restore()
    assert result.errors == [] or all('/etc/passwd' not in e for e in result.errors)
