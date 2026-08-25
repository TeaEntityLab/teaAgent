"""EFX-001: unmatched mutating dispatch is UNKNOWN and not blindly retried."""

from __future__ import annotations

import multiprocessing
import os
from pathlib import Path

from teaagent.audit import AuditLogger
from teaagent.checkpoint import SQLiteCheckpointStore
from teaagent.policy import (
    ApprovalPolicy,
    PermissionMode,
    compute_scoped_payload_digest,
)
from teaagent.runner import AgentRunner, FinalAnswer, ToolRequest
from teaagent.tools import ToolAnnotations, ToolRegistry


def _mutate_registry(marker: Path, *, idempotent: bool) -> ToolRegistry:
    registry = ToolRegistry()

    def handler(args: dict[str, object]) -> dict[str, object]:
        del args
        existing = marker.read_text(encoding='utf-8') if marker.exists() else ''
        marker.write_text(existing + 'x', encoding='utf-8')
        return {'written': True}

    registry.register(
        name='mutate_marker',
        description='append to a local marker file',
        input_schema={
            'type': 'object',
            'properties': {'path': {'type': 'string'}},
            'required': ['path'],
        },
        output_schema={
            'type': 'object',
            'properties': {'written': {'type': 'boolean'}},
        },
        annotations=ToolAnnotations(
            destructive=True, idempotent=idempotent, external_effect=True
        ),
        handler=handler,
    )
    return registry


def _crash_after_mutate(
    marker: str, checkpoint: str, audit: str, workspace: str
) -> None:
    def handler(args: dict[str, object]) -> dict[str, object]:
        del args
        path = Path(marker)
        existing = path.read_text(encoding='utf-8') if path.exists() else ''
        path.write_text(existing + 'x', encoding='utf-8')
        os._exit(73)
        return {'written': True}

    registry = ToolRegistry()
    registry.register(
        name='mutate_marker',
        description='append then crash',
        input_schema={
            'type': 'object',
            'properties': {'path': {'type': 'string'}},
            'required': ['path'],
        },
        output_schema={
            'type': 'object',
            'properties': {'written': {'type': 'boolean'}},
        },
        annotations=ToolAnnotations(
            destructive=True, idempotent=False, external_effect=True
        ),
        handler=handler,
    )
    workspace_root = Path(workspace)
    runner = AgentRunner(
        registry=registry,
        audit=AuditLogger(path=Path(audit)),
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.ALLOW),
        checkpoint_store=SQLiteCheckpointStore(checkpoint),
        workspace_root=workspace_root,
    )
    runner.run(
        task='mutate',
        run_id='efx001-crash',
        decide=lambda _: ToolRequest(
            tool_name='mutate_marker',
            arguments={'path': 'marker.txt'},
            call_id='call-crash',
        ),
    )


def test_process_death_leaves_unknown_and_refuses_blind_retry(
    tmp_path: Path,
) -> None:
    marker = tmp_path / 'marker.txt'
    checkpoint = tmp_path / 'ckpt.sqlite'
    audit = tmp_path / 'audit.jsonl'
    ctx = multiprocessing.get_context('spawn')
    proc = ctx.Process(
        target=_crash_after_mutate,
        args=(str(marker), str(checkpoint), str(audit), str(tmp_path)),
    )
    proc.start()
    proc.join(timeout=30)
    assert proc.exitcode == 73
    assert marker.read_text(encoding='utf-8') == 'x'

    store = SQLiteCheckpointStore(checkpoint)
    saved = store.load('efx001-crash')
    assert saved is not None
    pending = saved.get('pending_effect')
    assert isinstance(pending, dict)
    assert pending.get('outcome') == 'OUTCOME_UNKNOWN'
    assert pending.get('retry_safe') is False
    events = [
        line for line in audit.read_text(encoding='utf-8').splitlines() if line.strip()
    ]
    assert any('"tool_call_started"' in line for line in events)
    assert not any('"tool_call_completed"' in line for line in events)

    registry = _mutate_registry(marker, idempotent=False)
    calls = iter(
        [
            ToolRequest(
                tool_name='mutate_marker',
                arguments={'path': 'marker.txt'},
                call_id='call-crash',
            ),
            FinalAnswer(content='done'),
        ]
    )
    runner = AgentRunner(
        registry=registry,
        audit=AuditLogger(),
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.ALLOW),
        checkpoint_store=store,
        workspace_root=tmp_path,
    )
    result = runner.run(
        task='mutate',
        run_id='efx001-crash',
        decide=lambda _: next(calls),
        initial_observations=saved.get('observations', []),
        initial_context_extra={
            k: v for k, v in saved.items() if k not in {'task', 'observations'}
        },
    )
    assert result.status == 'completed'
    assert marker.read_text(encoding='utf-8') == 'x'
    unknown = [
        obs
        for obs in (store.load('efx001-crash') or {}).get('observations', [])
        if obs.get('error') == 'OUTCOME_UNKNOWN'
    ]
    assert unknown
    assert unknown[0].get('retry_safe') is False


def test_idempotent_unmatched_start_may_reddispatch(tmp_path: Path) -> None:
    marker = tmp_path / 'marker.txt'
    registry = _mutate_registry(marker, idempotent=True)
    store = SQLiteCheckpointStore(tmp_path / 'ckpt.sqlite')
    digest = compute_scoped_payload_digest('mutate_marker', {'path': 'marker.txt'})
    extra = {
        'pending_effect': {
            'call_id': 'call-1',
            'tool_name': 'mutate_marker',
            'payload_digest': digest,
            'idempotent': True,
            'retry_safe': True,
            'outcome': 'OUTCOME_UNKNOWN',
        }
    }
    calls = iter(
        [
            ToolRequest(
                tool_name='mutate_marker',
                arguments={'path': 'marker.txt'},
                call_id='call-1',
            ),
            FinalAnswer(content='done'),
        ]
    )
    runner = AgentRunner(
        registry=registry,
        audit=AuditLogger(),
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.ALLOW),
        checkpoint_store=store,
        workspace_root=tmp_path,
    )
    result = runner.run(
        task='mutate',
        decide=lambda _: next(calls),
        initial_context_extra=extra,
    )
    assert result.status == 'completed'
    assert marker.read_text(encoding='utf-8') == 'x'
