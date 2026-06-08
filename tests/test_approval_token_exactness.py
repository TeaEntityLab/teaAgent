"""WS3-006 approval-token exactness for destructive tools."""

from __future__ import annotations

from tempfile import TemporaryDirectory

import pytest

from teaagent.ergonomics.approval_store import ApprovalPresetStore
from teaagent.policy import ApprovalPolicy
from teaagent.types import PermissionMode, ToolPermissionError


def _policy_with_store(tmp: str, run_id: str) -> ApprovalPolicy:
    root = f'{tmp}/.teaagent'
    store = ApprovalPresetStore(root=root)
    return ApprovalPolicy(
        permission_mode=PermissionMode.PROMPT,
        approval_store=store,
        approval_origin_run_id=run_id,
        workspace_root=tmp,
    )


def test_stale_scoped_token_cannot_be_reused() -> None:
    with TemporaryDirectory() as tmp:
        run_id = 'run-token-1'
        policy = _policy_with_store(tmp, run_id)
        store = policy.approval_store
        assert store is not None
        store.add_scoped_approval(
            run_id=run_id,
            call_id='call-a',
            tool_name='workspace_write_file',
            arguments={'path': 'a.txt', 'content': 'one'},
        )
        policy.assert_allowed(
            tool_name='workspace_write_file',
            call_id='call-a',
            destructive=True,
            arguments={'path': 'a.txt', 'content': 'one'},
        )
        with pytest.raises(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-a',
                destructive=True,
                arguments={'path': 'a.txt', 'content': 'one'},
            )


def test_mismatched_arguments_reject_scoped_token() -> None:
    with TemporaryDirectory() as tmp:
        run_id = 'run-token-2'
        policy = _policy_with_store(tmp, run_id)
        store = policy.approval_store
        assert store is not None
        store.add_scoped_approval(
            run_id=run_id,
            call_id='call-b',
            tool_name='workspace_write_file',
            arguments={'path': 'b.txt', 'content': 'approved'},
        )
        with pytest.raises(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-b',
                destructive=True,
                arguments={'path': 'b.txt', 'content': 'changed'},
            )


def test_wrong_call_id_cannot_reuse_scoped_approval() -> None:
    with TemporaryDirectory() as tmp:
        run_id = 'run-token-3'
        policy = _policy_with_store(tmp, run_id)
        store = policy.approval_store
        assert store is not None
        store.add_scoped_approval(
            run_id=run_id,
            call_id='call-c',
            tool_name='workspace_write_file',
            arguments={'path': 'c.txt', 'content': 'x'},
        )
        with pytest.raises(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-d',
                destructive=True,
                arguments={'path': 'c.txt', 'content': 'x'},
            )


# ── WS3-006 edge-case expansion ───────────────────────────────────────────


def test_cross_run_token_reuse_blocked() -> None:
    """WS3-006: Token scoped to run-1 cannot authorize a call in run-2.

    The store binds each scoped approval to a specific run_id.  A policy
    with a different approval_origin_run_id must not be able to consume it.
    """
    with TemporaryDirectory() as tmp:
        store = ApprovalPresetStore(root=f'{tmp}/.teaagent')
        store.add_scoped_approval(
            run_id='run-1',
            call_id='call-xrun',
            tool_name='workspace_write_file',
            arguments={'path': 'x.txt', 'content': 'data'},
        )
        # Policy bound to run-2 — must not consume run-1's token
        policy_run2 = ApprovalPolicy(
            permission_mode=PermissionMode.PROMPT,
            approval_store=store,
            approval_origin_run_id='run-2',
            workspace_root=tmp,
        )
        with pytest.raises(ToolPermissionError):
            policy_run2.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-xrun',
                destructive=True,
                arguments={'path': 'x.txt', 'content': 'data'},
            )


def test_hmac_argument_digest_rejects_tampered_store() -> None:
    """WS3-006: Tampered argument_digest in store is rejected.

    If an attacker modifies the stored argument_digest to a forged value
    the HMAC verification will fail because the on-the-fly digest computed
    from the actual arguments no longer matches the tampered record.
    """
    with TemporaryDirectory() as tmp:
        run_id = 'run-hmac'
        policy = _policy_with_store(tmp, run_id)
        store = policy.approval_store
        assert store is not None

        store.add_scoped_approval(
            run_id=run_id,
            call_id='call-hmac',
            tool_name='workspace_write_file',
            arguments={'path': 'h.txt', 'content': 'original'},
        )

        # Tamper with the stored digest directly — simulate store compromise
        data = store._load()
        for item in data.get('scoped_approvals', []):
            if isinstance(item, dict) and item.get('call_id') == 'call-hmac':
                item['argument_digest'] = '0' * 64  # forged digest
                break
        store._save(data)

        # Original arguments should now fail because digest no longer matches
        with pytest.raises(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-hmac',
                destructive=True,
                arguments={'path': 'h.txt', 'content': 'original'},
            )


def test_expired_token_rejected() -> None:
    """WS3-006: Expired approval token is rejected even when arguments match.

    Scoped approvals carry an expires_at timestamp.  Once the expiry has
    passed the record is skipped during consumption.
    """
    with TemporaryDirectory() as tmp:
        from datetime import datetime, timedelta, timezone

        run_id = 'run-exp'
        policy = _policy_with_store(tmp, run_id)
        store = policy.approval_store
        assert store is not None

        store.add_scoped_approval(
            run_id=run_id,
            call_id='call-exp',
            tool_name='workspace_write_file',
            arguments={'path': 'exp.txt', 'content': 'old'},
        )

        # Rewind expires_at to one hour in the past
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        data = store._load()
        for item in data.get('scoped_approvals', []):
            if isinstance(item, dict) and item.get('call_id') == 'call-exp':
                item['expires_at'] = past
                break
        store._save(data)

        with pytest.raises(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-exp',
                destructive=True,
                arguments={'path': 'exp.txt', 'content': 'old'},
            )


def test_allow_destructive_requires_full_access_mode() -> None:
    """WS3-006: Document ``allow_all_destructive`` interaction with scoped tokens.

    ``allow_all_destructive=True`` in PROMPT mode causes the enforcer to
    return a block reason *before* scoped approval is checked — the token
    is never reached.  The flag only takes effect in DANGER_FULL_ACCESS
    mode with ``full_access_acknowledged=True``.

    Scoped tokens work correctly in PROMPT mode *without* the flag.
    """
    with TemporaryDirectory() as tmp:
        run_id = 'run-wild'
        store = ApprovalPresetStore(root=f'{tmp}/.teaagent')
        args = {'path': 'w.txt', 'content': 'y'}

        store.add_scoped_approval(
            run_id=run_id,
            call_id='call-wild',
            tool_name='workspace_write_file',
            arguments=args,
        )

        # ── PROMPT + allow_all_destructive → blocked before scoped check ──
        policy_blocked = ApprovalPolicy(
            permission_mode=PermissionMode.PROMPT,
            approval_store=store,
            approval_origin_run_id=run_id,
            workspace_root=tmp,
            allow_all_destructive=True,
        )
        with pytest.raises(ToolPermissionError):
            policy_blocked.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-wild',
                destructive=True,
                arguments=args,
            )

        # ── DANGER_FULL_ACCESS + allow_all_destructive → passes immediately ──
        policy_danger = ApprovalPolicy(
            permission_mode=PermissionMode.DANGER_FULL_ACCESS,
            approval_store=store,
            approval_origin_run_id=run_id,
            workspace_root=tmp,
            allow_all_destructive=True,
            full_access_acknowledged=True,
        )
        # Must not raise — danger-full-access allows everything
        policy_danger.assert_allowed(
            tool_name='workspace_write_file',
            call_id='call-wild-2',
            destructive=True,
            arguments={'path': 'w2.txt', 'content': 'z'},
        )


def test_concurrent_token_consumption_is_exclusive() -> None:
    """WS3-006: File-locked consumption prevents double-use from concurrent calls.

    Two threads racing to consume the same scoped approval must result in
    exactly one success and one ToolPermissionError.  The store-level
    ``file_lock`` ensures the consume-once invariant holds under concurrency.

    NOTE: This test documents the file-locking safety net.  If it flakes due
    to OS scheduling it indicates the lock is NOT providing the expected
    mutual exclusion.
    """
    import threading

    with TemporaryDirectory() as tmp:
        run_id = 'run-conc'
        store = ApprovalPresetStore(root=f'{tmp}/.teaagent')
        store.add_scoped_approval(
            run_id=run_id,
            call_id='call-conc',
            tool_name='workspace_write_file',
            arguments={'path': 'c.txt', 'content': 'concurrent'},
        )
        # Disable JIT prompting so both threads follow the exact same code path
        policy = ApprovalPolicy(
            permission_mode=PermissionMode.PROMPT,
            approval_store=store,
            approval_origin_run_id=run_id,
            workspace_root=tmp,
            enable_jit_prompt=False,
        )

        results: dict[str, bool | Exception] = {}
        barrier = threading.Barrier(2)

        def try_consume(label: str) -> None:
            barrier.wait()  # release both threads simultaneously
            try:
                policy.assert_allowed(
                    tool_name='workspace_write_file',
                    call_id='call-conc',
                    destructive=True,
                    arguments={'path': 'c.txt', 'content': 'concurrent'},
                )
                results[label] = True
            except Exception as exc:
                results[label] = exc

        t1 = threading.Thread(target=try_consume, args=('t1',))
        t2 = threading.Thread(target=try_consume, args=('t2',))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        successes = sum(1 for v in results.values() if v is True)
        failures = sum(1 for v in results.values() if isinstance(v, Exception))
        assert successes == 1, f'expected 1 success, got {successes}'
        assert failures == 1, f'expected 1 failure, got {failures}'
        # The failure must be a ToolPermissionError (not a crash)
        failed = [v for v in results.values() if isinstance(v, Exception)]
        assert isinstance(failed[0], ToolPermissionError)


def test_whitespace_in_arguments_produces_different_digest() -> None:
    """WS3-006: JSON canonicalisation is whitespace-sensitive.

    ``json.dumps(sort_keys=True, separators=(',', ':'))`` produces
    identical output for logically equal dicts, but trailing whitespace
    *inside* string values changes the payload and therefore the digest.
    """
    with TemporaryDirectory() as tmp:
        run_id = 'run-ws'
        policy = _policy_with_store(tmp, run_id)
        store = policy.approval_store
        assert store is not None

        store.add_scoped_approval(
            run_id=run_id,
            call_id='call-ws',
            tool_name='workspace_write_file',
            arguments={'path': 'ws.txt', 'content': 'hello'},
        )

        # Trailing whitespace inside a value → different JSON → different digest
        with pytest.raises(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-ws',
                destructive=True,
                arguments={'path': 'ws.txt', 'content': 'hello '},
            )

        # Leading whitespace in path
        with pytest.raises(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-ws',
                destructive=True,
                arguments={'path': ' ws.txt', 'content': 'hello'},
            )

        # Extra whitespace-only key would also change the digest
        with pytest.raises(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-ws',
                destructive=True,
                arguments={'path': 'ws.txt', 'content': 'hello', '  ': ''},
            )


def test_null_and_empty_arguments_rejected() -> None:
    """WS3-006: Empty or absent arguments cannot match a scoped token.

    - ``arguments={}`` produces ``{}`` via JSON, which differs from any
      non-empty arguments dict → digest mismatch.
    - ``arguments=None`` skips scoped-approval checking entirely in the
      approval manager, so the call falls through to the JIT gate and fails.
    """
    with TemporaryDirectory() as tmp:
        run_id = 'run-null'
        policy = _policy_with_store(tmp, run_id)
        store = policy.approval_store
        assert store is not None

        store.add_scoped_approval(
            run_id=run_id,
            call_id='call-null',
            tool_name='workspace_write_file',
            arguments={'path': 'n.txt', 'content': 'stuff'},
        )

        # Empty dict → digest of {} ≠ digest of {'path': 'n.txt', ...}
        with pytest.raises(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-null',
                destructive=True,
                arguments={},
            )

        # None → scoped-approval path is skipped entirely, falls to JIT fail
        with pytest.raises(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-null',
                destructive=True,
                arguments=None,
            )
