"""Tests for policy engine foundation (TASK-H4-002-01)."""

import unittest
from tempfile import TemporaryDirectory

from teaagent.policy_engine import (
    Policy,
    PolicyCondition,
    PolicyEffect,
    PolicyEngine,
    PolicyPrecedence,
    PolicyStore,
    PolicyType,
)


class TestPolicyCondition(unittest.TestCase):
    """Test policy condition evaluation."""

    def test_evaluate_equals(self):
        """Test equals operator."""
        condition = PolicyCondition(field='action', operator='equals', value='deploy')
        context = {'action': 'deploy'}
        self.assertTrue(condition.evaluate(context))

        context = {'action': 'delete'}
        self.assertFalse(condition.evaluate(context))

    def test_evaluate_not_equals(self):
        """Test not_equals operator."""
        condition = PolicyCondition(
            field='action', operator='not_equals', value='delete'
        )
        context = {'action': 'deploy'}
        self.assertTrue(condition.evaluate(context))

        context = {'action': 'delete'}
        self.assertFalse(condition.evaluate(context))

    def test_evaluate_contains(self):
        """Test contains operator."""
        condition = PolicyCondition(field='path', operator='contains', value='/src/')
        context = {'path': '/src/main.py'}
        self.assertTrue(condition.evaluate(context))

        context = {'path': '/docs/readme.md'}
        self.assertFalse(condition.evaluate(context))

    def test_evaluate_in(self):
        """Test in operator."""
        condition = PolicyCondition(
            field='role', operator='in', value=['admin', 'devops']
        )
        context = {'role': 'admin'}
        self.assertTrue(condition.evaluate(context))

        context = {'role': 'developer'}
        self.assertFalse(condition.evaluate(context))

    def test_evaluate_not_in(self):
        """Test not_in operator."""
        condition = PolicyCondition(
            field='role', operator='not_in', value=['guest', 'readonly']
        )
        context = {'role': 'admin'}
        self.assertTrue(condition.evaluate(context))

        context = {'role': 'guest'}
        self.assertFalse(condition.evaluate(context))

    def test_to_dict_and_from_dict(self):
        """Test serialization."""
        condition = PolicyCondition(field='action', operator='equals', value='deploy')
        data = condition.to_dict()

        restored = PolicyCondition.from_dict(data)
        self.assertEqual(restored.field, condition.field)
        self.assertEqual(restored.operator, condition.operator)
        self.assertEqual(restored.value, condition.value)


class TestPolicy(unittest.TestCase):
    """Test policy evaluation."""

    def test_evaluate_all_conditions_match(self):
        """Test policy evaluation when all conditions match."""
        policy = Policy(
            policy_id='test-policy',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.ALLOW,
            conditions=[
                PolicyCondition(field='action', operator='equals', value='deploy'),
                PolicyCondition(field='role', operator='in', value=['admin', 'devops']),
            ],
        )

        context = {'action': 'deploy', 'role': 'admin'}
        effect = policy.evaluate(context)
        self.assertEqual(effect, PolicyEffect.ALLOW)

    def test_evaluate_one_condition_fails(self):
        """Test policy evaluation when one condition fails."""
        policy = Policy(
            policy_id='test-policy',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.ALLOW,
            conditions=[
                PolicyCondition(field='action', operator='equals', value='deploy'),
                PolicyCondition(field='role', operator='in', value=['admin', 'devops']),
            ],
        )

        context = {'action': 'deploy', 'role': 'developer'}
        effect = policy.evaluate(context)
        self.assertIsNone(effect)  # Policy doesn't apply

    def test_evaluate_no_conditions(self):
        """Test policy evaluation with no conditions (always applies)."""
        policy = Policy(
            policy_id='test-policy',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.DENY,
            conditions=[],
        )

        context = {'action': 'deploy', 'role': 'developer'}
        effect = policy.evaluate(context)
        self.assertEqual(effect, PolicyEffect.DENY)

    def test_evaluate_disabled_policy(self):
        """Test that disabled policies don't apply."""
        policy = Policy(
            policy_id='test-policy',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.DENY,
            conditions=[],
            enabled=False,
        )

        context = {'action': 'deploy', 'role': 'developer'}
        effect = policy.evaluate(context)
        self.assertIsNone(effect)  # Disabled policy doesn't apply

    def test_applies_to(self):
        """Test applies_to method."""
        policy = Policy(
            policy_id='test-policy',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.ALLOW,
            conditions=[
                PolicyCondition(field='action', operator='equals', value='deploy'),
            ],
        )

        context = {'action': 'deploy'}
        self.assertTrue(policy.applies_to(context))

        context = {'action': 'delete'}
        self.assertFalse(policy.applies_to(context))

    def test_to_dict_and_from_dict(self):
        """Test policy serialization."""
        policy = Policy(
            policy_id='test-policy',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.ALLOW,
            conditions=[
                PolicyCondition(field='action', operator='equals', value='deploy'),
            ],
            precedence=PolicyPrecedence.HIGH,
            description='Test policy',
        )

        data = policy.to_dict()
        restored = Policy.from_dict(data)

        self.assertEqual(restored.policy_id, policy.policy_id)
        self.assertEqual(restored.policy_type, policy.policy_type)
        self.assertEqual(restored.effect, policy.effect)
        self.assertEqual(len(restored.conditions), len(policy.conditions))
        self.assertEqual(restored.precedence, policy.precedence)
        self.assertEqual(restored.description, policy.description)


class TestPolicyStore(unittest.TestCase):
    """Test policy storage."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.store = PolicyStore(self.temp_dir.name)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_save_and_load(self):
        """Test saving and loading a policy."""
        policy = Policy(
            policy_id='test-policy',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.ALLOW,
            conditions=[
                PolicyCondition(field='action', operator='equals', value='deploy'),
            ],
        )

        self.store.save(policy)
        loaded = self.store.load('test-policy')

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.policy_id, policy.policy_id)
        self.assertEqual(loaded.policy_type, policy.policy_type)

    def test_load_nonexistent(self):
        """Test loading a non-existent policy."""
        loaded = self.store.load('nonexistent')
        self.assertIsNone(loaded)

    def test_delete(self):
        """Test deleting a policy."""
        policy = Policy(
            policy_id='test-policy',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.ALLOW,
            conditions=[],
        )

        self.store.save(policy)
        self.assertTrue(self.store.delete('test-policy'))
        self.assertIsNone(self.store.load('test-policy'))

    def test_delete_nonexistent(self):
        """Test deleting a non-existent policy."""
        self.assertFalse(self.store.delete('nonexistent'))

    def test_list_all(self):
        """Test listing all policies."""
        policy1 = Policy(
            policy_id='policy-1',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.ALLOW,
            conditions=[],
        )
        policy2 = Policy(
            policy_id='policy-2',
            policy_type=PolicyType.CONSENSUS,
            effect=PolicyEffect.DENY,
            conditions=[],
        )

        self.store.save(policy1)
        self.store.save(policy2)

        policies = self.store.list()
        self.assertEqual(len(policies), 2)

    def test_list_by_type(self):
        """Test listing policies by type."""
        policy1 = Policy(
            policy_id='policy-1',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.ALLOW,
            conditions=[],
        )
        policy2 = Policy(
            policy_id='policy-2',
            policy_type=PolicyType.CONSENSUS,
            effect=PolicyEffect.DENY,
            conditions=[],
        )

        self.store.save(policy1)
        self.store.save(policy2)

        rbac_policies = self.store.list(policy_type=PolicyType.RBAC)
        self.assertEqual(len(rbac_policies), 1)
        self.assertEqual(rbac_policies[0].policy_id, 'policy-1')

    def test_list_enabled_only(self):
        """Test listing only enabled policies."""
        policy1 = Policy(
            policy_id='policy-1',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.ALLOW,
            conditions=[],
            enabled=True,
        )
        policy2 = Policy(
            policy_id='policy-2',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.DENY,
            conditions=[],
            enabled=False,
        )

        self.store.save(policy1)
        self.store.save(policy2)

        enabled_policies = self.store.list(enabled_only=True)
        self.assertEqual(len(enabled_policies), 1)
        self.assertEqual(enabled_policies[0].policy_id, 'policy-1')

    def test_count(self):
        """Test counting policies."""
        policy1 = Policy(
            policy_id='policy-1',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.ALLOW,
            conditions=[],
        )
        policy2 = Policy(
            policy_id='policy-2',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.DENY,
            conditions=[],
        )

        self.store.save(policy1)
        self.store.save(policy2)

        count = self.store.count()
        self.assertEqual(count, 2)

    def test_tenant_isolation(self):
        """Test tenant isolation in policy storage."""
        # Create stores for different tenants
        store_default = PolicyStore(self.temp_dir.name, tenant_id='default')
        store_tenant1 = PolicyStore(self.temp_dir.name, tenant_id='tenant1')

        policy = Policy(
            policy_id='test-policy',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.ALLOW,
            conditions=[],
        )

        store_default.save(policy)

        # Policy should be in default store
        self.assertIsNotNone(store_default.load('test-policy'))

        # Policy should not be in tenant1 store
        self.assertIsNone(store_tenant1.load('test-policy'))


class TestPolicyEngine(unittest.TestCase):
    """Test policy engine evaluation."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.store = PolicyStore(self.temp_dir.name)
        self.engine = PolicyEngine(self.store)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_evaluate_default_allow(self):
        """Test default allow when no policies match."""
        context = {'action': 'deploy', 'role': 'developer'}
        effect = self.engine.evaluate(context)
        self.assertEqual(effect, PolicyEffect.ALLOW)

    def test_evaluate_with_matching_policy(self):
        """Test evaluation with a matching policy."""
        policy = Policy(
            policy_id='deny-deploy',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.DENY,
            conditions=[
                PolicyCondition(field='action', operator='equals', value='deploy'),
                PolicyCondition(field='role', operator='equals', value='developer'),
            ],
        )
        self.store.save(policy)

        context = {'action': 'deploy', 'role': 'developer'}
        effect = self.engine.evaluate(context, policy_type=PolicyType.RBAC)
        self.assertEqual(effect, PolicyEffect.DENY)

    def test_evaluate_precedence(self):
        """Test that higher precedence policies override lower ones."""
        # Create low precedence policy that allows
        low_policy = Policy(
            policy_id='low-policy',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.ALLOW,
            conditions=[
                PolicyCondition(field='action', operator='equals', value='deploy'),
            ],
            precedence=PolicyPrecedence.LOW,
        )
        self.store.save(low_policy)

        # Create high precedence policy that denies
        high_policy = Policy(
            policy_id='high-policy',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.DENY,
            conditions=[
                PolicyCondition(field='action', operator='equals', value='deploy'),
            ],
            precedence=PolicyPrecedence.HIGH,
        )
        self.store.save(high_policy)

        context = {'action': 'deploy'}
        effect = self.engine.evaluate(context, policy_type=PolicyType.RBAC)
        # High precedence should win
        self.assertEqual(effect, PolicyEffect.DENY)

    def test_evaluate_with_explanation(self):
        """Test evaluation with detailed explanation."""
        policy = Policy(
            policy_id='deny-deploy',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.DENY,
            conditions=[
                PolicyCondition(field='action', operator='equals', value='deploy'),
            ],
            description='Deny deployment actions',
        )
        self.store.save(policy)

        context = {'action': 'deploy'}
        effect, details = self.engine.evaluate_with_explanation(
            context, policy_type=PolicyType.RBAC
        )

        self.assertEqual(effect, PolicyEffect.DENY)
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]['policy_id'], 'deny-deploy')
        self.assertTrue(details[0]['applies'])
        self.assertEqual(details[0]['effect'], 'deny')

    def test_check_permission_granted(self):
        """Test permission check when granted."""
        policy = Policy(
            policy_id='allow-admin',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.ALLOW,
            conditions=[
                PolicyCondition(field='role', operator='equals', value='admin'),
            ],
        )
        self.store.save(policy)

        allowed, reason = self.engine.check_permission('deploy', 'admin', {})
        self.assertTrue(allowed)
        self.assertIn('granted', reason)

    def test_check_permission_denied(self):
        """Test permission check when denied."""
        policy = Policy(
            policy_id='deny-developer',
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.DENY,
            conditions=[
                PolicyCondition(field='role', operator='equals', value='developer'),
            ],
        )
        self.store.save(policy)

        allowed, reason = self.engine.check_permission('deploy', 'developer', {})
        self.assertFalse(allowed)
        self.assertIn('denied', reason)

    def test_create_policy(self):
        """Test creating a policy through the engine."""
        policy = self.engine.create_policy(
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.DENY,
            conditions=[
                {'field': 'action', 'operator': 'equals', 'value': 'delete'},
            ],
            precedence=PolicyPrecedence.HIGH,
            description='Deny delete actions',
        )

        self.assertIsNotNone(policy)
        self.assertEqual(policy.policy_type, PolicyType.RBAC)
        self.assertEqual(policy.effect, PolicyEffect.DENY)

        # Verify it was saved
        loaded = self.store.load(policy.policy_id)
        self.assertIsNotNone(loaded)


if __name__ == '__main__':
    unittest.main()
