"""Tests for multi-agent consensus validation (TASK-H4-002-03)."""

import unittest
from tempfile import TemporaryDirectory

from teaagent.consensus_validation import (
    ConsensusRequest,
    ConsensusRule,
    ConsensusRuleType,
    ConsensusStatus,
    ConsensusStore,
    ConsensusValidator,
)


class TestConsensusRule(unittest.TestCase):
    """Test consensus rule evaluation."""

    def test_check_consensus_n_of_m_approved(self):
        """Test N-of-M consensus when approved."""
        rule = ConsensusRule(
            rule_id='test-rule',
            rule_type=ConsensusRuleType.N_OF_M,
            required_approvals=2,
            total_voters=3,
        )

        votes = {'voter1': True, 'voter2': True, 'voter3': False}
        status = rule.check_consensus(votes)
        self.assertEqual(status, ConsensusStatus.APPROVED)

    def test_check_consensus_n_of_m_pending(self):
        """Test N-of-M consensus when pending."""
        rule = ConsensusRule(
            rule_id='test-rule',
            rule_type=ConsensusRuleType.N_OF_M,
            required_approvals=2,
            total_voters=3,
        )

        votes = {'voter1': True, 'voter2': False}
        status = rule.check_consensus(votes)
        self.assertEqual(status, ConsensusStatus.PENDING)

    def test_check_consensus_n_of_m_rejected(self):
        """Test N-of-M consensus when rejected."""
        rule = ConsensusRule(
            rule_id='test-rule',
            rule_type=ConsensusRuleType.N_OF_M,
            required_approvals=2,
            total_voters=3,
        )

        votes = {'voter1': False, 'voter2': False, 'voter3': True}
        status = rule.check_consensus(votes)
        self.assertEqual(status, ConsensusStatus.REJECTED)

    def test_check_consensus_unanimous_approved(self):
        """Test unanimous consensus when approved."""
        rule = ConsensusRule(
            rule_id='test-rule',
            rule_type=ConsensusRuleType.UNANIMOUS,
            required_approvals=0,
            total_voters=0,
        )

        votes = {'voter1': True, 'voter2': True, 'voter3': True}
        status = rule.check_consensus(votes)
        self.assertEqual(status, ConsensusStatus.APPROVED)

    def test_check_consensus_unanimous_rejected(self):
        """Test unanimous consensus when rejected."""
        rule = ConsensusRule(
            rule_id='test-rule',
            rule_type=ConsensusRuleType.UNANIMOUS,
            required_approvals=0,
            total_voters=0,
        )

        votes = {'voter1': True, 'voter2': True, 'voter3': False}
        status = rule.check_consensus(votes)
        self.assertEqual(status, ConsensusStatus.REJECTED)

    def test_check_consensus_majority_approved(self):
        """Test majority consensus when approved."""
        rule = ConsensusRule(
            rule_id='test-rule',
            rule_type=ConsensusRuleType.MAJORITY,
            required_approvals=0,
            total_voters=0,
        )

        votes = {'voter1': True, 'voter2': True, 'voter3': False}
        status = rule.check_consensus(votes)
        self.assertEqual(status, ConsensusStatus.APPROVED)

    def test_check_consensus_majority_pending(self):
        """Test majority consensus when tied."""
        rule = ConsensusRule(
            rule_id='test-rule',
            rule_type=ConsensusRuleType.MAJORITY,
            required_approvals=0,
            total_voters=0,
        )

        votes = {'voter1': True, 'voter2': False}
        status = rule.check_consensus(votes)
        self.assertEqual(status, ConsensusStatus.PENDING)

    def test_to_dict_and_from_dict(self):
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

        self.assertEqual(restored.rule_id, rule.rule_id)
        self.assertEqual(restored.rule_type, rule.rule_type)
        self.assertEqual(restored.required_approvals, rule.required_approvals)


class TestConsensusRequest(unittest.TestCase):
    """Test consensus request management."""

    def test_add_vote(self):
        """Test adding a vote."""
        request = ConsensusRequest(
            request_id='test-request',
            rule_id='test-rule',
            action='deploy',
            context={},
            requested_by='user1',
        )

        request.add_vote('voter1', True)
        self.assertEqual(request.votes['voter1'], True)

        request.add_vote('voter2', False)
        self.assertEqual(request.votes['voter2'], False)

    def test_is_expired(self):
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
        self.assertTrue(request.is_expired())

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
        self.assertFalse(request.is_expired())

    def test_to_dict_and_from_dict(self):
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

        self.assertEqual(restored.request_id, request.request_id)
        self.assertEqual(restored.action, request.action)
        self.assertEqual(restored.context, request.context)


class TestConsensusStore(unittest.TestCase):
    """Test consensus storage."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.store = ConsensusStore(self.temp_dir.name)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_save_and_load_rule(self):
        """Test saving and loading a rule."""
        rule = ConsensusRule(
            rule_id='test-rule',
            rule_type=ConsensusRuleType.N_OF_M,
            required_approvals=2,
            total_voters=3,
        )

        self.store.save_rule(rule)
        loaded = self.store.load_rule('test-rule')

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.rule_id, rule.rule_id)
        self.assertEqual(loaded.rule_type, rule.rule_type)

    def test_delete_rule(self):
        """Test deleting a rule."""
        rule = ConsensusRule(
            rule_id='test-rule',
            rule_type=ConsensusRuleType.N_OF_M,
            required_approvals=2,
            total_voters=3,
        )

        self.store.save_rule(rule)
        self.assertTrue(self.store.delete_rule('test-rule'))
        self.assertIsNone(self.store.load_rule('test-rule'))

    def test_list_rules(self):
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

        self.store.save_rule(rule1)
        self.store.save_rule(rule2)

        rules = self.store.list_rules()
        self.assertEqual(len(rules), 2)

    def test_save_and_load_request(self):
        """Test saving and loading a request."""
        request = ConsensusRequest(
            request_id='test-request',
            rule_id='test-rule',
            action='deploy',
            context={},
            requested_by='user1',
        )

        self.store.save_request(request)
        loaded = self.store.load_request('test-request')

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.request_id, request.request_id)
        self.assertEqual(loaded.action, request.action)

    def test_delete_request(self):
        """Test deleting a request."""
        request = ConsensusRequest(
            request_id='test-request',
            rule_id='test-rule',
            action='deploy',
            context={},
            requested_by='user1',
        )

        self.store.save_request(request)
        self.assertTrue(self.store.delete_request('test-request'))
        self.assertIsNone(self.store.load_request('test-request'))

    def test_list_requests(self):
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

        self.store.save_request(request1)
        self.store.save_request(request2)

        requests = self.store.list_requests()
        self.assertEqual(len(requests), 2)

    def test_list_requests_by_status(self):
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

        self.store.save_request(request1)
        self.store.save_request(request2)

        pending_requests = self.store.list_requests(status=ConsensusStatus.PENDING)
        self.assertEqual(len(pending_requests), 1)
        self.assertEqual(pending_requests[0].request_id, 'request-1')

    def test_tenant_isolation(self):
        """Test tenant isolation in consensus storage."""
        store_default = ConsensusStore(self.temp_dir.name, tenant_id='default')
        store_tenant1 = ConsensusStore(self.temp_dir.name, tenant_id='tenant1')

        rule = ConsensusRule(
            rule_id='test-rule',
            rule_type=ConsensusRuleType.N_OF_M,
            required_approvals=2,
            total_voters=3,
        )

        store_default.save_rule(rule)

        self.assertIsNotNone(store_default.load_rule('test-rule'))
        self.assertIsNone(store_tenant1.load_rule('test-rule'))


class TestConsensusValidator(unittest.TestCase):
    """Test consensus validator integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.validator = ConsensusValidator(self.temp_dir.name)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_create_rule(self):
        """Test creating a consensus rule."""
        rule = self.validator.create_rule(
            ConsensusRuleType.N_OF_M,
            required_approvals=2,
            total_voters=3,
            description='Test rule',
        )

        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_type, ConsensusRuleType.N_OF_M)
        self.assertEqual(rule.required_approvals, 2)

    def test_request_consensus(self):
        """Test requesting consensus."""
        rule = self.validator.create_rule(
            ConsensusRuleType.N_OF_M,
            required_approvals=2,
            total_voters=3,
        )

        request = self.validator.request_consensus(
            rule.rule_id,
            'deploy',
            {'environment': 'production'},
            'user1',
        )

        self.assertIsNotNone(request)
        self.assertEqual(request.action, 'deploy')
        self.assertEqual(request.status, ConsensusStatus.PENDING)

    def test_cast_vote(self):
        """Test casting a vote."""
        rule = self.validator.create_rule(
            ConsensusRuleType.N_OF_M,
            required_approvals=2,
            total_voters=3,
        )

        request = self.validator.request_consensus(
            rule.rule_id,
            'deploy',
            {},
            'user1',
        )

        # Cast first vote
        updated = self.validator.cast_vote(request.request_id, 'voter1', True)
        self.assertEqual(len(updated.votes), 1)
        self.assertEqual(updated.votes['voter1'], True)

    def test_cast_vote_reaches_consensus(self):
        """Test that casting votes can reach consensus."""
        rule = self.validator.create_rule(
            ConsensusRuleType.N_OF_M,
            required_approvals=2,
            total_voters=3,
        )

        request = self.validator.request_consensus(
            rule.rule_id,
            'deploy',
            {},
            'user1',
        )

        # Cast votes to reach consensus
        self.validator.cast_vote(request.request_id, 'voter1', True)
        updated = self.validator.cast_vote(request.request_id, 'voter2', True)

        self.assertEqual(updated.status, ConsensusStatus.APPROVED)

    def test_cast_vote_rejects(self):
        """Test that votes can reject consensus."""
        rule = self.validator.create_rule(
            ConsensusRuleType.N_OF_M,
            required_approvals=2,
            total_voters=3,
        )

        request = self.validator.request_consensus(
            rule.rule_id,
            'deploy',
            {},
            'user1',
        )

        # Cast votes to reject (2 rejections makes it impossible to reach 2 approvals)
        self.validator.cast_vote(request.request_id, 'voter1', False)
        updated = self.validator.cast_vote(request.request_id, 'voter2', False)

        self.assertEqual(updated.status, ConsensusStatus.REJECTED)

    def test_get_consensus_status(self):
        """Test getting consensus status."""
        rule = self.validator.create_rule(
            ConsensusRuleType.N_OF_M,
            required_approvals=2,
            total_voters=3,
        )

        request = self.validator.request_consensus(
            rule.rule_id,
            'deploy',
            {},
            'user1',
        )

        status = self.validator.get_consensus_status(request.request_id)
        self.assertEqual(status, ConsensusStatus.PENDING)

    def test_expired_request(self):
        """Test that expired requests are marked as expired."""

        # Create rule with short timeout
        rule = self.validator.create_rule(
            ConsensusRuleType.N_OF_M,
            required_approvals=2,
            total_voters=3,
            timeout_seconds=1,  # 1 second timeout
        )

        request = self.validator.request_consensus(
            rule.rule_id,
            'deploy',
            {},
            'user1',
        )

        # Wait for expiration
        import time

        time.sleep(2)

        status = self.validator.get_consensus_status(request.request_id)
        self.assertEqual(status, ConsensusStatus.EXPIRED)

    def test_create_default_rules(self):
        """Test creating default consensus rules."""
        self.validator.create_default_rules()

        rules = self.validator.store.list_rules()
        self.assertGreaterEqual(len(rules), 3)

    def test_vote_on_nonexistent_request(self):
        """Test voting on a non-existent request."""
        with self.assertRaises(ValueError):
            self.validator.cast_vote('nonexistent', 'voter1', True)

    def test_vote_on_completed_request(self):
        """Test voting on a completed request."""
        rule = self.validator.create_rule(
            ConsensusRuleType.N_OF_M,
            required_approvals=2,
            total_voters=3,
        )

        request = self.validator.request_consensus(
            rule.rule_id,
            'deploy',
            {},
            'user1',
        )

        # Reach consensus
        self.validator.cast_vote(request.request_id, 'voter1', True)
        self.validator.cast_vote(request.request_id, 'voter2', True)

        # Try to vote again
        with self.assertRaises(ValueError):
            self.validator.cast_vote(request.request_id, 'voter3', True)


if __name__ == '__main__':
    unittest.main()
