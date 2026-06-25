"""Tests for remaining Phase 4-6 maturity-matrix gaps."""

from __future__ import annotations

import json
from pathlib import Path

from teaagent.consensus import (
    ConsensusConfig,
    ConsensusEngine,
    ConsensusStatus,
    PeerIdentity,
    PeerRegistry,
    RiskLevel,
    VotingThreshold,
    import_votes_batch,
    parse_vote_import_payload,
)
from teaagent.control_plane_api import ControlPlaneState
from teaagent.control_plane_bridge import publish_swarm_workflow
from teaagent.swarm import SubagentResult, SubagentTask, SwarmManager
from teaagent.tournament.benchmark import (
    metrics_from_subagent_result,
    select_winner_from_subagent_results,
)
from teaagent.wasm_skill import build_wasm_invoke_contract, write_wasm_manifest


def test_parse_vote_import_payload_accepts_wrapper() -> None:
    wrapped = {
        'votes': [{'proposal_id': 'p1', 'peer_name': 'a', 'decision': 'approve'}]
    }
    records = parse_vote_import_payload(wrapped)
    assert len(records) == 1


def test_consensus_wait_and_votes_import(tmp_path: Path) -> None:
    registry = PeerRegistry(storage_path=tmp_path / 'peers.json')
    peer = PeerIdentity(name='peer-a', ssh_public_key='ssh-rsa KEY')
    registry.register(peer)
    registry.activate(peer.name)
    engine = ConsensusEngine(
        peer_registry=registry,
        config=ConsensusConfig(),
        storage_path=tmp_path / 'consensus.json',
    )
    state = engine.request_consensus(
        task_description='deploy',
        risk_level=RiskLevel.MEDIUM,
        proposed_by='cli',
        threshold=VotingThreshold.SIMPLE_MAJORITY,
    )
    engine.cast_approving_votes_for_active_peers(state.proposal.id)
    final = engine.poll_until_resolved(state.proposal.id, timeout_seconds=2.0)
    assert final is not None
    assert final.status == ConsensusStatus.APPROVED

    state2 = engine.request_consensus(
        task_description='rollback',
        risk_level=RiskLevel.LOW,
        proposed_by='cli',
    )
    votes_file = tmp_path / 'votes.json'
    votes_file.write_text(
        json.dumps(
            [
                {
                    'proposal_id': state2.proposal.id,
                    'peer_name': peer.name,
                    'decision': 'approve',
                }
            ]
        ),
        encoding='utf-8',
    )
    summary = import_votes_batch(
        engine, parse_vote_import_payload(json.loads(votes_file.read_text()))
    )
    assert summary['accepted'] == 1


def test_consensus_cancel_records_cancelled_by(tmp_path: Path) -> None:
    registry = PeerRegistry(storage_path=tmp_path / 'peers.json')
    peer = PeerIdentity(name='peer-a', ssh_public_key='ssh-rsa KEY')
    registry.register(peer)
    registry.activate(peer.name)
    engine = ConsensusEngine(
        peer_registry=registry,
        config=ConsensusConfig(),
        storage_path=tmp_path / 'consensus.json',
    )
    state = engine.request_consensus(
        task_description='deploy',
        risk_level=RiskLevel.MEDIUM,
        proposed_by='cli',
    )
    assert engine.cancel_consensus(state.proposal.id, cancelled_by='operator-a')
    final = engine.get_consensus_status(state.proposal.id)
    assert final is not None
    assert final.status == ConsensusStatus.CANCELLED
    assert final.cancelled_by == 'operator-a'


def test_deny_request_sync_records_denied_by() -> None:
    from teaagent.subagents._approval_queue import (
        CentralizedApprovalQueue,
        SubagentApprovalRequest,
    )

    queue = CentralizedApprovalQueue(parent_run_id='parent-1')
    request_id = queue.generate_request_id()
    queue._requests[request_id] = SubagentApprovalRequest(
        request_id=request_id,
        subagent_id='sub-1',
        parent_run_id='parent-1',
        subagent_name='worker',
        tool_name='workspace_write_file',
        tool_arguments={'path': 'README.md'},
        permission_mode='prompt',
        isolation='none',
    )

    assert queue.deny_request_sync(
        request_id, reason='too risky', denied_by='reviewer-1'
    )
    assert queue._requests[request_id].denied_by == 'reviewer-1'


def test_control_plane_bridge_publishes_workflow() -> None:
    state = ControlPlaneState()
    publish_swarm_workflow(
        state,
        parent_run_id='run-1',
        phase='running',
        subagents=[{'task_id': 't1', 'status': 'running'}],
        totals={'successful': 0},
    )
    snapshot = state.snapshot()
    assert snapshot['workflow']['parent_run_id'] == 'run-1'
    assert snapshot['focus']['phase'] == 'running'


def test_comparator_selects_successful_subagent() -> None:
    good = SubagentResult(
        task_id='a',
        success=True,
        execution_time_ms=100.0,
        test_results={'passed': 10, 'failed': 0},
    )
    bad = SubagentResult(
        task_id='b',
        success=False,
        execution_time_ms=5000.0,
        test_results={'passed': 0, 'failed': 5},
    )
    winner_id, score, best = select_winner_from_subagent_results([bad, good])
    assert winner_id == 'a'
    assert score > 0
    assert best is good
    metrics = metrics_from_subagent_result(good)
    assert metrics.test_pass_rate == 1.0


def test_swarm_publishes_to_control_plane(tmp_path: Path) -> None:
    state = ControlPlaneState()
    manager = SwarmManager(tmp_path, control_plane_state=state)
    manager.add_subagent(SubagentTask(task_id='t1', description='task one'))
    report = manager.execute_swarm()
    assert report.total_subagents == 1
    workflow = state.snapshot()['workflow']
    assert workflow is not None
    assert workflow['phase'] == 'completed'


def test_wasm_invoke_contract_and_manifest(tmp_path: Path) -> None:
    skill = tmp_path / 'skill'
    skill.mkdir()
    contract = build_wasm_invoke_contract(skill)
    assert contract['wasm_file'] is None
    manifest = write_wasm_manifest(skill)
    assert manifest.is_file()
