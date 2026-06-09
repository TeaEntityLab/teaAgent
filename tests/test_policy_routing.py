"""Tests for policy-based routing (TASK-H4-002-04)."""

import unittest
from tempfile import TemporaryDirectory

from teaagent.policy_routing import (
    PolicyRouter,
    RoutingDecision,
    RoutingRule,
    RoutingStore,
    RoutingTarget,
)


class TestRoutingRule(unittest.TestCase):
    """Test routing rule matching."""

    def test_matches_action_exact(self):
        """Test exact action matching."""
        rule = RoutingRule(
            rule_id='test-rule',
            action_pattern='deploy',
            decision=RoutingDecision.ALLOW,
        )

        self.assertTrue(rule.matches_action('deploy'))
        self.assertFalse(rule.matches_action('rollback'))

    def test_matches_action_wildcard(self):
        """Test wildcard action matching."""
        rule = RoutingRule(
            rule_id='test-rule',
            action_pattern='deploy:*',
            decision=RoutingDecision.ALLOW,
        )

        self.assertTrue(rule.matches_action('deploy:production'))
        self.assertTrue(rule.matches_action('deploy:development'))
        self.assertFalse(rule.matches_action('rollback'))

    def test_matches_action_wildcard_prefix(self):
        """Test wildcard prefix matching."""
        rule = RoutingRule(
            rule_id='test-rule',
            action_pattern='*:production',
            decision=RoutingDecision.ALLOW,
        )

        self.assertTrue(rule.matches_action('deploy:production'))
        self.assertTrue(rule.matches_action('rollback:production'))
        self.assertFalse(rule.matches_action('deploy:development'))

    def test_to_dict_and_from_dict(self):
        """Test rule serialization."""
        rule = RoutingRule(
            rule_id='test-rule',
            action_pattern='deploy:*',
            decision=RoutingDecision.ALLOW,
            target=RoutingTarget.HUMAN,
            priority=50,
        )

        data = rule.to_dict()
        restored = RoutingRule.from_dict(data)

        self.assertEqual(restored.rule_id, rule.rule_id)
        self.assertEqual(restored.action_pattern, rule.action_pattern)
        self.assertEqual(restored.decision, rule.decision)
        self.assertEqual(restored.target, rule.target)


class TestRoutingStore(unittest.TestCase):
    """Test routing rule storage."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.store = RoutingStore(self.temp_dir.name)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_save_and_load_rule(self):
        """Test saving and loading a routing rule."""
        rule = RoutingRule(
            rule_id='test-rule',
            action_pattern='deploy:*',
            decision=RoutingDecision.ALLOW,
        )

        self.store.save_rule(rule)
        loaded = self.store.load_rule('test-rule')

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.rule_id, rule.rule_id)
        self.assertEqual(loaded.action_pattern, rule.action_pattern)

    def test_delete_rule(self):
        """Test deleting a routing rule."""
        rule = RoutingRule(
            rule_id='test-rule',
            action_pattern='deploy:*',
            decision=RoutingDecision.ALLOW,
        )

        self.store.save_rule(rule)
        self.assertTrue(self.store.delete_rule('test-rule'))
        self.assertIsNone(self.store.load_rule('test-rule'))

    def test_list_rules(self):
        """Test listing all routing rules."""
        rule1 = RoutingRule(
            rule_id='rule-1',
            action_pattern='deploy:*',
            decision=RoutingDecision.ALLOW,
        )
        rule2 = RoutingRule(
            rule_id='rule-2',
            action_pattern='delete:*',
            decision=RoutingDecision.DENY,
        )

        self.store.save_rule(rule1)
        self.store.save_rule(rule2)

        rules = self.store.list_rules()
        self.assertEqual(len(rules), 2)

    def test_list_enabled_only(self):
        """Test listing only enabled rules."""
        rule1 = RoutingRule(
            rule_id='rule-1',
            action_pattern='deploy:*',
            decision=RoutingDecision.ALLOW,
            enabled=True,
        )
        rule2 = RoutingRule(
            rule_id='rule-2',
            action_pattern='delete:*',
            decision=RoutingDecision.DENY,
            enabled=False,
        )

        self.store.save_rule(rule1)
        self.store.save_rule(rule2)

        enabled_rules = self.store.list_rules(enabled_only=True)
        self.assertEqual(len(enabled_rules), 1)
        self.assertEqual(enabled_rules[0].rule_id, 'rule-1')

    def test_tenant_isolation(self):
        """Test tenant isolation in routing storage."""
        store_default = RoutingStore(self.temp_dir.name, tenant_id='default')
        store_tenant1 = RoutingStore(self.temp_dir.name, tenant_id='tenant1')

        rule = RoutingRule(
            rule_id='test-rule',
            action_pattern='deploy:*',
            decision=RoutingDecision.ALLOW,
        )

        store_default.save_rule(rule)

        self.assertIsNotNone(store_default.load_rule('test-rule'))
        self.assertIsNone(store_tenant1.load_rule('test-rule'))


class TestPolicyRouter(unittest.TestCase):
    """Test policy router integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.router = PolicyRouter(self.temp_dir.name)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_create_routing_rule(self):
        """Test creating a routing rule."""
        rule = self.router.create_routing_rule(
            'deploy:*',
            RoutingDecision.ALLOW,
            target=RoutingTarget.DEFAULT,
            priority=50,
        )

        self.assertIsNotNone(rule)
        self.assertEqual(rule.action_pattern, 'deploy:*')
        self.assertEqual(rule.decision, RoutingDecision.ALLOW)

    def test_route_action_with_matching_rule(self):
        """Test routing action with a matching rule."""
        self.router.create_routing_rule(
            'deploy:*',
            RoutingDecision.ALLOW,
            target=RoutingTarget.SPECIALIST,
        )

        decision, target, reason = self.router.route_action(
            'deploy:production', 'user1', {}
        )

        self.assertEqual(decision, RoutingDecision.ALLOW)
        self.assertEqual(target, RoutingTarget.SPECIALIST)
        self.assertIn('Routed by rule', reason)

    def test_route_action_without_matching_rule(self):
        """Test routing action without a matching rule."""
        decision, target, reason = self.router.route_action(
            'unknown:action', 'user1', {}
        )

        # Should use policy engine default
        self.assertEqual(decision, RoutingDecision.ALLOW)
        self.assertEqual(target, RoutingTarget.DEFAULT)

    def test_route_action_with_required_roles(self):
        """Test routing action with required roles."""
        # Create RBAC system and assign role
        self.router.rbac_system.create_default_roles()
        role = self.router.rbac_system.role_store.load_role('developer')
        if role:
            self.router.rbac_system.assign_role(role.role_id, 'user1')

        self.router.create_routing_rule(
            'deploy:*',
            RoutingDecision.ALLOW,
            required_roles={'developer'},
        )

        decision, target, reason = self.router.route_action(
            'deploy:production', 'user1', {}
        )

        # If role assignment worked, should be allowed; otherwise denied
        if role:
            self.assertEqual(decision, RoutingDecision.ALLOW)
        else:
            self.assertEqual(decision, RoutingDecision.DENY)

    def test_route_action_without_required_roles(self):
        """Test routing action without required roles."""
        self.router.create_routing_rule(
            'deploy:*',
            RoutingDecision.ALLOW,
            required_roles={'admin'},
        )

        decision, target, reason = self.router.route_action(
            'deploy:production', 'user1', {}
        )

        self.assertEqual(decision, RoutingDecision.DENY)
        self.assertIn('lacks required roles', reason)

    def test_route_action_priority(self):
        """Test that higher priority rules are evaluated first."""
        # Create high priority rule that denies
        self.router.create_routing_rule(
            'deploy:*',
            RoutingDecision.DENY,
            priority=100,
        )

        # Create low priority rule that allows
        self.router.create_routing_rule(
            'deploy:*',
            RoutingDecision.ALLOW,
            priority=10,
        )

        decision, target, reason = self.router.route_action(
            'deploy:production', 'user1', {}
        )

        # High priority rule should win
        self.assertEqual(decision, RoutingDecision.DENY)

    def test_check_routing_permission_allowed(self):
        """Test checking routing permission when allowed."""
        self.router.create_routing_rule(
            'read:*',
            RoutingDecision.ALLOW,
        )

        allowed, reason = self.router.check_routing_permission('read:file', 'user1', {})
        self.assertTrue(allowed)
        self.assertIn('Routed by rule', reason)

    def test_check_routing_permission_denied(self):
        """Test checking routing permission when denied."""
        self.router.create_routing_rule(
            'delete:*',
            RoutingDecision.DENY,
        )

        allowed, reason = self.router.check_routing_permission(
            'delete:file', 'user1', {}
        )
        self.assertFalse(allowed)
        self.assertIn('Routed by rule', reason)

    def test_check_routing_permission_requires_approval(self):
        """Test checking routing permission when approval required."""
        self.router.create_routing_rule(
            'deploy:production',
            RoutingDecision.REQUIRE_APPROVAL,
        )

        allowed, reason = self.router.check_routing_permission(
            'deploy:production', 'user1', {}
        )
        self.assertFalse(allowed)
        self.assertIn('Approval required', reason)

    def test_create_default_routing_rules(self):
        """Test creating default routing rules."""
        self.router.create_default_routing_rules()

        rules = self.router.routing_store.list_rules()
        self.assertGreaterEqual(len(rules), 5)

    def test_wildcard_pattern_matching(self):
        """Test wildcard pattern matching in routing."""
        self.router.create_routing_rule(
            '*:production',
            RoutingDecision.REQUIRE_APPROVAL,
        )

        decision, target, reason = self.router.route_action(
            'deploy:production', 'user1', {}
        )
        self.assertEqual(decision, RoutingDecision.REQUIRE_APPROVAL)

        decision, target, reason = self.router.route_action(
            'rollback:production', 'user1', {}
        )
        self.assertEqual(decision, RoutingDecision.REQUIRE_APPROVAL)


if __name__ == '__main__':
    unittest.main()
