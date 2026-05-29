"""AC: Federated swarm consensus end-to-end flow."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from teaagent.consensus import (
    ConsensusConfig,
    ConsensusEngine,
    ConsensusStatus,
    PeerIdentity,
    PeerRegistry,
    RiskLevel,
    VoteDecision,
    VotingThreshold,
    peer_vote_signature,
    task_matches_pre_approval,
)
from teaagent.swarm import SubagentResult, SubagentTask, SwarmManager


def test_consensus_request_vote_attestation_flow() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        storage = Path(tmp)
        registry = PeerRegistry(storage_path=storage / 'peers')
        peer1 = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
        peer2 = PeerIdentity(name='peer2', ssh_public_key='ssh-rsa key2')
        registry.register(peer1)
        registry.register(peer2)

        engine = ConsensusEngine(
            peer_registry=registry,
            config=ConsensusConfig(),
            storage_path=storage / 'consensus',
        )
        state = engine.request_consensus(
            task_description='Deploy billing service',
            risk_level=RiskLevel.HIGH,
            proposed_by='orchestrator',
            threshold=VotingThreshold.SIMPLE_MAJORITY,
        )
        assert state.status == ConsensusStatus.VOTING

        engine.submit_vote(
            state.proposal.id,
            'peer1',
            VoteDecision.APPROVE,
            peer_vote_signature(peer1, state.proposal.task_description),
        )
        engine.submit_vote(
            state.proposal.id,
            'peer2',
            VoteDecision.APPROVE,
            peer_vote_signature(peer2, state.proposal.task_description),
        )

        final = engine.get_consensus_status(state.proposal.id)
        assert final is not None
        assert final.status == ConsensusStatus.APPROVED
        attestation = engine.generate_attestation(state.proposal.id)
        assert attestation is not None
        assert 'peer1' in attestation['approved_by']


def test_swarm_pre_approval_executes_consensus_gated_task() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = PeerRegistry(storage_path=root / 'peers')
        peer1 = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
        peer2 = PeerIdentity(name='peer2', ssh_public_key='ssh-rsa key2')
        registry.register(peer1)
        registry.register(peer2)

        config = ConsensusConfig(
            enable_pre_approval=True,
            pre_approved_patterns=['Deploy *'],
        )
        manager = SwarmManager(
            root,
            enable_consensus=True,
            peer_registry=registry,
            consensus_config=config,
        )
        manager.add_subagent(
            SubagentTask(
                task_id='task-1',
                description='Deploy staging stack',
                risk_level=RiskLevel.HIGH,
                require_consensus=True,
            )
        )

        def fake_execute(self):  # type: ignore[no-untyped-def]
            return SubagentResult(task_id=self._task.task_id, success=True, output='ok')

        with patch.object(type(manager._subagents[0]), 'execute', fake_execute):
            report = manager.execute_swarm()

        assert report.total_subagents == 1
        assert report.successful_subagents == 1


def test_swarm_filters_task_when_consensus_not_reached() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = PeerRegistry(storage_path=root / 'peers')
        registry.register(PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1'))

        manager = SwarmManager(
            root,
            enable_consensus=True,
            peer_registry=registry,
            consensus_config=ConsensusConfig(enable_pre_approval=False),
        )
        manager.add_subagent(
            SubagentTask(
                task_id='blocked',
                description='Deploy production',
                risk_level=RiskLevel.CRITICAL,
                require_consensus=True,
            )
        )
        report = manager.execute_swarm()
        assert report.total_subagents == 0


def test_task_matches_pre_approval_patterns() -> None:
    config = ConsensusConfig(
        enable_pre_approval=True,
        pre_approved_patterns=['Deploy *', 'Review *'],
    )
    assert task_matches_pre_approval('Deploy staging', config)
    assert not task_matches_pre_approval('Delete database', config)


def test_swarm_async_consensus_executes_after_votes_arrive() -> None:
    import threading

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = PeerRegistry(storage_path=root / 'peers')
        peer1 = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
        peer2 = PeerIdentity(name='peer2', ssh_public_key='ssh-rsa key2')
        registry.register(peer1)
        registry.register(peer2)

        config = ConsensusConfig(
            enable_pre_approval=False,
            async_vote_collection=True,
            vote_poll_timeout_seconds=2.0,
        )
        manager = SwarmManager(
            root,
            enable_consensus=True,
            peer_registry=registry,
            consensus_config=config,
        )
        manager.add_subagent(
            SubagentTask(
                task_id='fast',
                description='Summarize logs',
                risk_level=RiskLevel.LOW,
                require_consensus=False,
            )
        )
        manager.add_subagent(
            SubagentTask(
                task_id='slow',
                description='Deploy production',
                risk_level=RiskLevel.CRITICAL,
                require_consensus=True,
            )
        )

        proposal_ids: list[str] = []
        ready = threading.Event()

        def fake_execute(self):  # type: ignore[no-untyped-def]
            return SubagentResult(task_id=self._task.task_id, success=True, output='ok')

        original_check = manager._check_consensus_for_tasks

        def capture_check() -> dict[str, object]:
            result = original_check()
            pending = result.get('pending', {})
            if isinstance(pending, dict):
                proposal_ids.extend(pending.values())
            ready.set()
            return result

        def submit_votes_later() -> None:
            assert ready.wait(timeout=2.0)
            engine = manager._consensus_engine
            assert engine is not None
            for proposal_id in proposal_ids:
                state = engine.get_consensus_status(proposal_id)
                assert state is not None
                description = state.proposal.task_description
                engine.submit_vote(
                    proposal_id,
                    'peer1',
                    VoteDecision.APPROVE,
                    peer_vote_signature(peer1, description),
                )
                engine.submit_vote(
                    proposal_id,
                    'peer2',
                    VoteDecision.APPROVE,
                    peer_vote_signature(peer2, description),
                )

        from teaagent.swarm import Subagent

        with (
            patch.object(manager, '_check_consensus_for_tasks', capture_check),
            patch.object(Subagent, 'execute', fake_execute),
        ):
            voter = threading.Thread(target=submit_votes_later, daemon=True)
            voter.start()
            report = manager.execute_swarm()
            voter.join(timeout=3)

        assert report.successful_subagents == 2
        assert {result.task_id for result in report.results} == {'fast', 'slow'}
