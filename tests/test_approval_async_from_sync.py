from __future__ import annotations

# test-type: behavior
import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from teaagent.approval.manager import MultiSigQuorumConfig, MultiSigQuorumManager
from teaagent.async_bridge import run_coroutine_sync


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


def test_multisig_signature_collection_from_running_loop() -> None:
    async def collect(_request_id: str, **_kwargs: object) -> list[str]:
        await asyncio.sleep(0)
        return []

    sync = mock.Mock()
    sync.collect_approval_signatures = mock.Mock(side_effect=collect)

    quorum = MultiSigQuorumManager(
        config=MultiSigQuorumConfig(enabled=True), agent_id='agent-a'
    )

    async def main() -> None:
        result = quorum._run_async_signature_collection(sync, 'req-1')
        assert result == []
        await asyncio.sleep(0)

    asyncio.run(main())
    sync.collect_approval_signatures.assert_called_once()
