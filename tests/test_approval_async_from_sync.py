from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from teaagent.async_bridge import run_coroutine_sync
from teaagent.policy import ApprovalPolicy, PermissionMode


def test_run_coroutine_sync_from_running_loop_leaves_loop_usable() -> None:
    async def inner() -> int:
        await asyncio.sleep(0)
        return 42

    async def main() -> None:
        with ThreadPoolExecutor(max_workers=1) as executor:
            value = run_coroutine_sync(inner(), executor=executor)
        assert value == 42
        await asyncio.sleep(0)

    asyncio.run(main())


def test_policy_signature_collection_from_running_loop() -> None:
    async def collect(_request_id: str, **_kwargs: object) -> list[str]:
        await asyncio.sleep(0)
        return []

    sync = mock.Mock()
    sync.collect_approval_signatures = mock.Mock(side_effect=collect)

    policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)

    async def main() -> None:
        result = policy._run_async_signature_collection(sync, 'req-1')
        assert result == []
        await asyncio.sleep(0)

    asyncio.run(main())
    sync.collect_approval_signatures.assert_called_once()
