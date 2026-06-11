"""Tests for policy-based routing (TASK-H4-002-04)."""

from tempfile import TemporaryDirectory

import pytest
from teaagent.policy_routing import (
    PolicyRouter,
    RoutingDecision,
    RoutingRule,
    RoutingStore,
    RoutingTarget,
)


def test_routing_rule_matches_action_exact():
    """Test exact action matching."""
    rule = RoutingRule(
        rule_id='test-rule',
        action_pattern='deploy',
        decision=RoutingDecision.ALLOW,
    )

    assert rule.matches_action('deploy') is True
    assert rule.matches_action('rollback') is False


def test_routing_rule_matches_action_wildcard():
    """Test wildcard action matching."""
    rule = RoutingRule(
        rule_id='test-rule',
        action_pattern='deploy:*',
        decision=RoutingDecision.ALLOW,
    )

    assert rule.matches_action('deploy:production') is True
    assert rule.matches_action('deploy:development') is True
    assert rule.matches_action('rollback') is False


def test_routing_rule_matches_action_wildcard_prefix():
    """Test wildcard prefix matching."""
    rule = RoutingRule(
        rule_id='test-rule',
        action_pattern='*:production',
        decision=RoutingDecision.ALLOW,
    )

    assert rule.matches_action('deploy:production') is True
    assert rule.matches_action('rollback:production') is True
    assert rule.matches_action('deploy:development') is False


def test_routing_rule_to_dict_and_from_dict():
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

    assert restored.rule_id == rule.rule_id
    assert restored.action_pattern == rule.action_pattern
    assert restored.decision == rule.decision
    assert restored.target == rule.target


@pytest.fixture
def routing_store():
    """Fixture for RoutingStore with temporary directory."""
    temp_dir = TemporaryDirectory()
    store = RoutingStore(temp_dir.name)
    yield store
    temp_dir.cleanup()


def test_routing_store_save_and_load_rule(routing_store):
    """Test saving and loading a routing rule."""
    rule = RoutingRule(
        rule_id='test-rule',
        action_pattern='deploy:*',
        decision=RoutingDecision.ALLOW,
    )

    routing_store.save_rule(rule)
    loaded = routing_store.load_rule('test-rule')

    assert loaded is not None
    assert loaded.rule_id == rule.rule_id
    assert loaded.action_pattern == rule.action_pattern


def test_routing_store_delete_rule(routing_store):
    """Test deleting a routing rule."""
    rule = RoutingRule(
        rule_id='test-rule',
        action_pattern='deploy:*',
        decision=RoutingDecision.ALLOW,
    )

    routing_store.save_rule(rule)
    assert routing_store.delete_rule('test-rule') is True
    assert routing_store.load_rule('test-rule') is None


def test_routing_store_list_rules(routing_store):
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

    routing_store.save_rule(rule1)
    routing_store.save_rule(rule2)

    rules = routing_store.list_rules()
    assert len(rules) == 2


def test_routing_store_list_enabled_only(routing_store):
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

    routing_store.save_rule(rule1)
    routing_store.save_rule(rule2)

    enabled_rules = routing_store.list_rules(enabled_only=True)
    assert len(enabled_rules) == 1
    assert enabled_rules[0].rule_id == 'rule-1'


def test_routing_store_tenant_isolation():
    """Test tenant isolation in routing storage."""
    temp_dir = TemporaryDirectory()
    store_default = RoutingStore(temp_dir.name, tenant_id='default')
    store_tenant1 = RoutingStore(temp_dir.name, tenant_id='tenant1')

    rule = RoutingRule(
        rule_id='test-rule',
        action_pattern='deploy:*',
        decision=RoutingDecision.ALLOW,
    )

    store_default.save_rule(rule)

    assert store_default.load_rule('test-rule') is not None
    assert store_tenant1.load_rule('test-rule') is None

    temp_dir.cleanup()


@pytest.fixture
def policy_router():
    """Fixture for PolicyRouter with temporary directory."""
    temp_dir = TemporaryDirectory()
    router = PolicyRouter(temp_dir.name)
    yield router
    temp_dir.cleanup()


def test_policy_router_create_routing_rule(policy_router):
    """Test creating a routing rule."""
    rule = policy_router.create_routing_rule(
        'deploy:*',
        RoutingDecision.ALLOW,
        target=RoutingTarget.DEFAULT,
        priority=50,
    )

    assert rule is not None
    assert rule.action_pattern == 'deploy:*'
    assert rule.decision == RoutingDecision.ALLOW


def test_policy_router_route_action_with_matching_rule(policy_router):
    """Test routing action with a matching rule."""
    policy_router.create_routing_rule(
        'deploy:*',
        RoutingDecision.ALLOW,
        target=RoutingTarget.SPECIALIST,
    )

    decision, target, reason = policy_router.route_action(
        'deploy:production', 'user1', {}
    )

    assert decision == RoutingDecision.ALLOW
    assert target == RoutingTarget.SPECIALIST
    assert 'Routed by rule' in reason


def test_policy_router_route_action_without_matching_rule(policy_router):
    """Test routing action without a matching rule."""
    decision, target, reason = policy_router.route_action('unknown:action', 'user1', {})

    # Should use policy engine default
    assert decision == RoutingDecision.ALLOW
    assert target == RoutingTarget.DEFAULT


def test_policy_router_route_action_with_required_roles(policy_router):
    """Test routing action with required roles."""
    # Create RBAC system and assign role
    policy_router.rbac_system.create_default_roles()
    role = policy_router.rbac_system.role_store.load_role('developer')
    if role:
        policy_router.rbac_system.assign_role(role.role_id, 'user1')

    policy_router.create_routing_rule(
        'deploy:*',
        RoutingDecision.ALLOW,
        required_roles={'developer'},
    )

    decision, target, reason = policy_router.route_action(
        'deploy:production', 'user1', {}
    )

    # If role assignment worked, should be allowed; otherwise denied
    if role:
        assert decision == RoutingDecision.ALLOW
    else:
        assert decision == RoutingDecision.DENY


def test_policy_router_route_action_without_required_roles(policy_router):
    """Test routing action without required roles."""
    policy_router.create_routing_rule(
        'deploy:*',
        RoutingDecision.ALLOW,
        required_roles={'admin'},
    )

    decision, target, reason = policy_router.route_action(
        'deploy:production', 'user1', {}
    )

    assert decision == RoutingDecision.DENY
    assert 'lacks required roles' in reason


def test_policy_router_route_action_priority(policy_router):
    """Test that higher priority rules are evaluated first."""
    # Create high priority rule that denies
    policy_router.create_routing_rule(
        'deploy:*',
        RoutingDecision.DENY,
        priority=100,
    )

    # Create low priority rule that allows
    policy_router.create_routing_rule(
        'deploy:*',
        RoutingDecision.ALLOW,
        priority=10,
    )

    decision, target, reason = policy_router.route_action(
        'deploy:production', 'user1', {}
    )

    # High priority rule should win
    assert decision == RoutingDecision.DENY


def test_policy_router_check_routing_permission_allowed(policy_router):
    """Test checking routing permission when allowed."""
    policy_router.create_routing_rule(
        'read:*',
        RoutingDecision.ALLOW,
    )

    allowed, reason = policy_router.check_routing_permission('read:file', 'user1', {})
    assert allowed is True
    assert 'Routed by rule' in reason


def test_policy_router_check_routing_permission_denied(policy_router):
    """Test checking routing permission when denied."""
    policy_router.create_routing_rule(
        'delete:*',
        RoutingDecision.DENY,
    )

    allowed, reason = policy_router.check_routing_permission('delete:file', 'user1', {})
    assert allowed is False
    assert 'Routed by rule' in reason


def test_policy_router_check_routing_permission_requires_approval(policy_router):
    """Test checking routing permission when approval required."""
    policy_router.create_routing_rule(
        'deploy:production',
        RoutingDecision.REQUIRE_APPROVAL,
    )

    allowed, reason = policy_router.check_routing_permission(
        'deploy:production', 'user1', {}
    )
    assert allowed is False
    assert 'Approval required' in reason


def test_policy_router_create_default_routing_rules(policy_router):
    """Test creating default routing rules."""
    policy_router.create_default_routing_rules()

    rules = policy_router.routing_store.list_rules()
    assert len(rules) >= 5


def test_policy_router_wildcard_pattern_matching(policy_router):
    """Test wildcard pattern matching in routing."""
    policy_router.create_routing_rule(
        '*:production',
        RoutingDecision.REQUIRE_APPROVAL,
    )

    decision, target, reason = policy_router.route_action(
        'deploy:production', 'user1', {}
    )
    assert decision == RoutingDecision.REQUIRE_APPROVAL

    decision, target, reason = policy_router.route_action(
        'rollback:production', 'user1', {}
    )
    assert decision == RoutingDecision.REQUIRE_APPROVAL
