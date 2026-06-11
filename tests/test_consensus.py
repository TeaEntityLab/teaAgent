"""Tests for multi-agent consensus validation (TASK-H4-002-03)."""

from tempfile import TemporaryDirectory

import pytest
from teaagent.consensus_validation import (
    ConsensusRequest,
    ConsensusRule,
    ConsensusRuleType,
    ConsensusStatus,
    ConsensusStore,
    ConsensusValidator,
)


def test_check_consensus_n_of_m_approved():
    """Test N-of-M consensus when approved."""
    rule = ConsensusRule(
        rule_id='test-rule',
        rule_type=ConsensusRuleType.N_OF_M,
        required_approvals=2,
        total_voters=3,
    )

    votes = {'voter1': True, 'voter2': True, 'voter3': False}
    status = rule.check_consensus(votes)
    assert status == ConsensusStatus.APPROVED


def test_check_consensus_n_of_m_pending():
    """Test N-of-M consensus when pending."""
    rule = ConsensusRule(
        rule_id='test-rule',
        rule_type=ConsensusRuleType.N_OF_M,
        required_approvals=2,
        total_voters=3,
    )

    votes = {'voter1': True, 'voter2': False}
    status = rule.check_consensus(votes)
    assert status == ConsensusStatus.PENDING


def test_check_consensus_n_of_m_rejected():
    """Test N-of-M consensus when rejected."""
    rule = ConsensusRule(
        rule_id='test-rule',
        rule_type=ConsensusRuleType.N_OF_M,
        required_approvals=2,
        total_voters=3,
    )

    votes = {'voter1': False, 'voter2': False, 'voter3': True}
    status = rule.check_consensus(votes)
    assert status == ConsensusStatus.REJECTED


def test_check_consensus_unanimous_approved():
    """Test unanimous consensus when approved."""
    rule = ConsensusRule(
        rule_id='test-rule',
        rule_type=ConsensusRuleType.UNANIMOUS,
        required_approvals=0,
        total_voters=0,
    )

    votes = {'voter1': True, 'voter2': True, 'voter3': True}
    status = rule.check_consensus(votes)
    assert status == ConsensusStatus.APPROVED


def test_check_consensus_unanimous_rejected():
    """Test unanimous consensus when rejected."""
    rule = ConsensusRule(
        rule_id='test-rule',
        rule_type=ConsensusRuleType.UNANIMOUS,
        required_approvals=0,
        total_voters=0,
    )

    votes = {'voter1': True, 'voter2': True, 'voter3': False}
    status = rule.check_consensus(votes)
    assert status == ConsensusStatus.REJECTED


def test_check_consensus_majority_approved():
    """Test majority consensus when approved."""
    rule = ConsensusRule(
        rule_id='test-rule',
        rule_type=ConsensusRuleType.MAJORITY,
        required_approvals=0,
        total_voters=0,
    )

    votes = {'voter1': True, 'voter2': True, 'voter3': False}
    status = rule.check_consensus(votes)
    assert status == ConsensusStatus.APPROVED


def test_check_consensus_majority_pending():
    """Test majority consensus when tied."""
    rule = ConsensusRule(
        rule_id='test-rule',
        rule_type=ConsensusRuleType.MAJORITY,
        required_approvals=0,
        total_voters=0,
    )

    votes = {'voter1': True, 'voter2': False}
    status = rule.check_consensus(votes)
    assert status == ConsensusStatus.PENDING


def test_to_dict_and_from_dict():
    """Test rule serialization."""
    rule = ConsensusRule(
        rule_id='test-rule',
        rule_type=ConsensusRuleType.N_OF_M,
        required_approvals=2,
        total_voters=3,
        description='Test rule',
    )

    data = rule.to_dict()
    restored = ConsensusRule.from_dict(data)

    assert restored.rule_id == rule.rule_id
    assert restored.rule_type == rule.rule_type
    assert restored.required_approvals == rule.required_approvals


def test_add_vote():
    """Test adding a vote."""
    request = ConsensusRequest(
        request_id='test-request',
        rule_id='test-rule',
        action='deploy',
        context={},
        requested_by='user1',
    )

    request.add_vote('voter1', True)
    assert request.votes['voter1']

    request.add_vote('voter2', False)
    assert not request.votes['voter2']


def test_is_expired():
    """Test checking if request is expired."""
    from datetime import datetime, timedelta, timezone

    # Create expired request
    past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    request = ConsensusRequest(
        request_id='test-request',
        rule_id='test-rule',
        action='deploy',
        context={},
        requested_by='user1',
        expires_at=past_time,
    )
    assert request.is_expired()

    # Create non-expired request
    future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    request = ConsensusRequest(
        request_id='test-request',
        rule_id='test-rule',
        action='deploy',
        context={},
        requested_by='user1',
        expires_at=future_time,
    )
    assert not request.is_expired()


def test_request_to_dict_and_from_dict():
    """Test request serialization."""
    request = ConsensusRequest(
        request_id='test-request',
        rule_id='test-rule',
        action='deploy',
        context={'environment': 'production'},
        requested_by='user1',
    )

    data = request.to_dict()
    restored = ConsensusRequest.from_dict(data)

    assert restored.request_id == request.request_id
    assert restored.action == request.action
    assert restored.context == request.context


@pytest.fixture
def temp_dir():
    """Fixture for temporary directory."""
    with TemporaryDirectory() as tmp:
        yield tmp


@pytest.fixture
def consensus_store(temp_dir):
    """Fixture for consensus store."""
    return ConsensusStore(temp_dir)


def test_save_and_load_rule(consensus_store):
    """Test saving and loading a rule."""
    rule = ConsensusRule(
        rule_id='test-rule',
        rule_type=ConsensusRuleType.N_OF_M,
        required_approvals=2,
        total_voters=3,
    )

    consensus_store.save_rule(rule)
    loaded = consensus_store.load_rule('test-rule')

    assert loaded is not None
    assert loaded.rule_id == rule.rule_id
    assert loaded.rule_type == rule.rule_type


def test_delete_rule(consensus_store):
    """Test deleting a rule."""
    rule = ConsensusRule(
        rule_id='test-rule',
        rule_type=ConsensusRuleType.N_OF_M,
        required_approvals=2,
        total_voters=3,
    )

    consensus_store.save_rule(rule)
    assert consensus_store.delete_rule('test-rule')
    assert consensus_store.load_rule('test-rule') is None


def test_list_rules(consensus_store):
    """Test listing all rules."""
    rule1 = ConsensusRule(
        rule_id='rule-1',
        rule_type=ConsensusRuleType.N_OF_M,
        required_approvals=2,
        total_voters=3,
    )
    rule2 = ConsensusRule(
        rule_id='rule-2',
        rule_type=ConsensusRuleType.UNANIMOUS,
        required_approvals=0,
        total_voters=0,
    )

    consensus_store.save_rule(rule1)
    consensus_store.save_rule(rule2)

    rules = consensus_store.list_rules()
    assert len(rules) == 2


def test_save_and_load_request(consensus_store):
    """Test saving and loading a request."""
    request = ConsensusRequest(
        request_id='test-request',
        rule_id='test-rule',
        action='deploy',
        context={},
        requested_by='user1',
    )

    consensus_store.save_request(request)
    loaded = consensus_store.load_request('test-request')

    assert loaded is not None
    assert loaded.request_id == request.request_id
    assert loaded.action == request.action


def test_delete_request(consensus_store):
    """Test deleting a request."""
    request = ConsensusRequest(
        request_id='test-request',
        rule_id='test-rule',
        action='deploy',
        context={},
        requested_by='user1',
    )

    consensus_store.save_request(request)
    assert consensus_store.delete_request('test-request')
    assert consensus_store.load_request('test-request') is None


def test_list_requests(consensus_store):
    """Test listing requests."""
    request1 = ConsensusRequest(
        request_id='request-1',
        rule_id='rule-1',
        action='deploy',
        context={},
        requested_by='user1',
    )
    request2 = ConsensusRequest(
        request_id='request-2',
        rule_id='rule-1',
        action='rollback',
        context={},
        requested_by='user2',
    )

    consensus_store.save_request(request1)
    consensus_store.save_request(request2)

    requests = consensus_store.list_requests()
    assert len(requests) == 2


def test_list_requests_by_status(consensus_store):
    """Test listing requests by status."""
    request1 = ConsensusRequest(
        request_id='request-1',
        rule_id='rule-1',
        action='deploy',
        context={},
        requested_by='user1',
        status=ConsensusStatus.PENDING,
    )
    request2 = ConsensusRequest(
        request_id='request-2',
        rule_id='rule-1',
        action='rollback',
        context={},
        requested_by='user2',
        status=ConsensusStatus.APPROVED,
    )

    consensus_store.save_request(request1)
    consensus_store.save_request(request2)

    pending_requests = consensus_store.list_requests(status=ConsensusStatus.PENDING)
    assert len(pending_requests) == 1
    assert pending_requests[0].request_id == 'request-1'


def test_tenant_isolation(temp_dir):
    """Test tenant isolation in consensus storage."""
    store_default = ConsensusStore(temp_dir, tenant_id='default')
    store_tenant1 = ConsensusStore(temp_dir, tenant_id='tenant1')

    rule = ConsensusRule(
        rule_id='test-rule',
        rule_type=ConsensusRuleType.N_OF_M,
        required_approvals=2,
        total_voters=3,
    )

    store_default.save_rule(rule)

    assert store_default.load_rule('test-rule') is not None
    assert store_tenant1.load_rule('test-rule') is None


@pytest.fixture
def consensus_validator(temp_dir):
    """Fixture for consensus validator."""
    return ConsensusValidator(temp_dir)


def test_create_rule(consensus_validator):
    """Test creating a consensus rule."""
    rule = consensus_validator.create_rule(
        ConsensusRuleType.N_OF_M,
        required_approvals=2,
        total_voters=3,
        description='Test rule',
    )

    assert rule is not None
    assert rule.rule_type == ConsensusRuleType.N_OF_M
    assert rule.required_approvals == 2


def test_request_consensus(consensus_validator):
    """Test requesting consensus."""
    rule = consensus_validator.create_rule(
        ConsensusRuleType.N_OF_M,
        required_approvals=2,
        total_voters=3,
    )

    request = consensus_validator.request_consensus(
        rule.rule_id,
        'deploy',
        {'environment': 'production'},
        'user1',
    )

    assert request is not None
    assert request.action == 'deploy'
    assert request.status == ConsensusStatus.PENDING


def test_cast_vote(consensus_validator):
    """Test casting a vote."""
    rule = consensus_validator.create_rule(
        ConsensusRuleType.N_OF_M,
        required_approvals=2,
        total_voters=3,
    )

    request = consensus_validator.request_consensus(
        rule.rule_id,
        'deploy',
        {},
        'user1',
    )

    # Cast first vote
    updated = consensus_validator.cast_vote(request.request_id, 'voter1', True)
    assert len(updated.votes) == 1
    assert updated.votes['voter1']


def test_cast_vote_reaches_consensus(consensus_validator):
    """Test that casting votes can reach consensus."""
    rule = consensus_validator.create_rule(
        ConsensusRuleType.N_OF_M,
        required_approvals=2,
        total_voters=3,
    )

    request = consensus_validator.request_consensus(
        rule.rule_id,
        'deploy',
        {},
        'user1',
    )

    # Cast votes to reach consensus
    consensus_validator.cast_vote(request.request_id, 'voter1', True)
    updated = consensus_validator.cast_vote(request.request_id, 'voter2', True)

    assert updated.status == ConsensusStatus.APPROVED


def test_cast_vote_rejects(consensus_validator):
    """Test that votes can reject consensus."""
    rule = consensus_validator.create_rule(
        ConsensusRuleType.N_OF_M,
        required_approvals=2,
        total_voters=3,
    )

    request = consensus_validator.request_consensus(
        rule.rule_id,
        'deploy',
        {},
        'user1',
    )

    # Cast votes to reject (2 rejections makes it impossible to reach 2 approvals)
    consensus_validator.cast_vote(request.request_id, 'voter1', False)
    updated = consensus_validator.cast_vote(request.request_id, 'voter2', False)

    assert updated.status == ConsensusStatus.REJECTED


def test_get_consensus_status(consensus_validator):
    """Test getting consensus status."""
    rule = consensus_validator.create_rule(
        ConsensusRuleType.N_OF_M,
        required_approvals=2,
        total_voters=3,
    )

    request = consensus_validator.request_consensus(
        rule.rule_id,
        'deploy',
        {},
        'user1',
    )

    status = consensus_validator.get_consensus_status(request.request_id)
    assert status == ConsensusStatus.PENDING


def test_expired_request(consensus_validator):
    """Test that expired requests are marked as expired."""

    # Create rule with short timeout
    rule = consensus_validator.create_rule(
        ConsensusRuleType.N_OF_M,
        required_approvals=2,
        total_voters=3,
        timeout_seconds=1,  # 1 second timeout
    )

    request = consensus_validator.request_consensus(
        rule.rule_id,
        'deploy',
        {},
        'user1',
    )

    # Wait for expiration
    import time

    time.sleep(2)

    status = consensus_validator.get_consensus_status(request.request_id)
    assert status == ConsensusStatus.EXPIRED


def test_create_default_rules(consensus_validator):
    """Test creating default consensus rules."""
    consensus_validator.create_default_rules()

    rules = consensus_validator.store.list_rules()
    assert len(rules) >= 3


def test_vote_on_nonexistent_request(consensus_validator):
    """Test voting on a non-existent request."""
    with pytest.raises(ValueError):
        consensus_validator.cast_vote('nonexistent', 'voter1', True)


def test_vote_on_completed_request(consensus_validator):
    """Test voting on a completed request."""
    rule = consensus_validator.create_rule(
        ConsensusRuleType.N_OF_M,
        required_approvals=2,
        total_voters=3,
    )

    request = consensus_validator.request_consensus(
        rule.rule_id,
        'deploy',
        {},
        'user1',
    )

    # Reach consensus
    consensus_validator.cast_vote(request.request_id, 'voter1', True)
    consensus_validator.cast_vote(request.request_id, 'voter2', True)

    # Try to vote again
    with pytest.raises(ValueError):
        consensus_validator.cast_vote(request.request_id, 'voter3', True)
