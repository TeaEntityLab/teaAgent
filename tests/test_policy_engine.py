"""Tests for policy engine foundation (TASK-H4-002-01)."""

from tempfile import TemporaryDirectory

import pytest
from teaagent.policy_engine import (
    Policy,
    PolicyCondition,
    PolicyEffect,
    PolicyEngine,
    PolicyPrecedence,
    PolicyStore,
    PolicyType,
)


def test_policy_condition_evaluate_equals():
    """Test equals operator."""
    condition = PolicyCondition(field='action', operator='equals', value='deploy')
    context = {'action': 'deploy'}
    assert condition.evaluate(context) is True

    context = {'action': 'delete'}
    assert condition.evaluate(context) is False


def test_policy_condition_evaluate_not_equals():
    """Test not_equals operator."""
    condition = PolicyCondition(field='action', operator='not_equals', value='delete')
    context = {'action': 'deploy'}
    assert condition.evaluate(context) is True

    context = {'action': 'delete'}
    assert condition.evaluate(context) is False


def test_policy_condition_evaluate_contains():
    """Test contains operator."""
    condition = PolicyCondition(field='path', operator='contains', value='/src/')
    context = {'path': '/src/main.py'}
    assert condition.evaluate(context) is True

    context = {'path': '/docs/readme.md'}
    assert condition.evaluate(context) is False


def test_policy_condition_evaluate_in():
    """Test in operator."""
    condition = PolicyCondition(field='role', operator='in', value=['admin', 'devops'])
    context = {'role': 'admin'}
    assert condition.evaluate(context) is True

    context = {'role': 'developer'}
    assert condition.evaluate(context) is False


def test_policy_condition_evaluate_not_in():
    """Test not_in operator."""
    condition = PolicyCondition(
        field='role', operator='not_in', value=['guest', 'readonly']
    )
    context = {'role': 'admin'}
    assert condition.evaluate(context) is True

    context = {'role': 'guest'}
    assert condition.evaluate(context) is False


def test_policy_condition_to_dict_and_from_dict():
    """Test serialization."""
    condition = PolicyCondition(field='action', operator='equals', value='deploy')
    data = condition.to_dict()

    restored = PolicyCondition.from_dict(data)
    assert restored.field == condition.field
    assert restored.operator == condition.operator
    assert restored.value == condition.value


def test_policy_evaluate_all_conditions_match():
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
    assert effect == PolicyEffect.ALLOW


def test_policy_evaluate_one_condition_fails():
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
    assert effect is None  # Policy doesn't apply


def test_policy_evaluate_no_conditions():
    """Test policy evaluation with no conditions (always applies)."""
    policy = Policy(
        policy_id='test-policy',
        policy_type=PolicyType.RBAC,
        effect=PolicyEffect.DENY,
        conditions=[],
    )

    context = {'action': 'deploy', 'role': 'developer'}
    effect = policy.evaluate(context)
    assert effect == PolicyEffect.DENY


def test_policy_evaluate_disabled_policy():
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
    assert effect is None  # Disabled policy doesn't apply


def test_policy_applies_to():
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
    assert policy.applies_to(context) is True

    context = {'action': 'delete'}
    assert policy.applies_to(context) is False


def test_policy_to_dict_and_from_dict():
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

    assert restored.policy_id == policy.policy_id
    assert restored.policy_type == policy.policy_type
    assert restored.effect == policy.effect
    assert len(restored.conditions) == len(policy.conditions)
    assert restored.precedence == policy.precedence
    assert restored.description == policy.description


@pytest.fixture
def policy_store():
    """Fixture for PolicyStore with temporary directory."""
    temp_dir = TemporaryDirectory()
    store = PolicyStore(temp_dir.name)
    yield store
    temp_dir.cleanup()


def test_policy_store_save_and_load(policy_store):
    """Test saving and loading a policy."""
    policy = Policy(
        policy_id='test-policy',
        policy_type=PolicyType.RBAC,
        effect=PolicyEffect.ALLOW,
        conditions=[
            PolicyCondition(field='action', operator='equals', value='deploy'),
        ],
    )

    policy_store.save(policy)
    loaded = policy_store.load('test-policy')

    assert loaded is not None
    assert loaded.policy_id == policy.policy_id
    assert loaded.policy_type == policy.policy_type


def test_policy_store_load_nonexistent(policy_store):
    """Test loading a non-existent policy."""
    loaded = policy_store.load('nonexistent')
    assert loaded is None


def test_policy_store_delete(policy_store):
    """Test deleting a policy."""
    policy = Policy(
        policy_id='test-policy',
        policy_type=PolicyType.RBAC,
        effect=PolicyEffect.ALLOW,
        conditions=[],
    )

    policy_store.save(policy)
    assert policy_store.delete('test-policy') is True
    assert policy_store.load('test-policy') is None


def test_policy_store_delete_nonexistent(policy_store):
    """Test deleting a non-existent policy."""
    assert policy_store.delete('nonexistent') is False


def test_policy_store_list_all(policy_store):
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

    policy_store.save(policy1)
    policy_store.save(policy2)

    policies = policy_store.list()
    assert len(policies) == 2


def test_policy_store_list_by_type(policy_store):
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

    policy_store.save(policy1)
    policy_store.save(policy2)

    rbac_policies = policy_store.list(policy_type=PolicyType.RBAC)
    assert len(rbac_policies) == 1
    assert rbac_policies[0].policy_id == 'policy-1'


def test_policy_store_list_enabled_only(policy_store):
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

    policy_store.save(policy1)
    policy_store.save(policy2)

    enabled_policies = policy_store.list(enabled_only=True)
    assert len(enabled_policies) == 1
    assert enabled_policies[0].policy_id == 'policy-1'


def test_policy_store_count(policy_store):
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

    policy_store.save(policy1)
    policy_store.save(policy2)

    count = policy_store.count()
    assert count == 2


def test_policy_store_tenant_isolation():
    """Test tenant isolation in policy storage."""
    # Create stores for different tenants
    temp_dir = TemporaryDirectory()
    store_default = PolicyStore(temp_dir.name, tenant_id='default')
    store_tenant1 = PolicyStore(temp_dir.name, tenant_id='tenant1')

    policy = Policy(
        policy_id='test-policy',
        policy_type=PolicyType.RBAC,
        effect=PolicyEffect.ALLOW,
        conditions=[],
    )

    store_default.save(policy)

    # Policy should be in default store
    assert store_default.load('test-policy') is not None

    # Policy should not be in tenant1 store
    assert store_tenant1.load('test-policy') is None

    temp_dir.cleanup()


@pytest.fixture
def policy_engine():
    """Fixture for PolicyEngine with temporary directory."""
    temp_dir = TemporaryDirectory()
    store = PolicyStore(temp_dir.name)
    engine = PolicyEngine(store)
    yield engine, store
    temp_dir.cleanup()


def test_policy_engine_evaluate_default_allow(policy_engine):
    """Test default allow when no policies match."""
    engine, store = policy_engine
    context = {'action': 'deploy', 'role': 'developer'}
    effect = engine.evaluate(context)
    assert effect == PolicyEffect.ALLOW


def test_policy_engine_evaluate_with_matching_policy(policy_engine):
    """Test evaluation with a matching policy."""
    engine, store = policy_engine
    policy = Policy(
        policy_id='deny-deploy',
        policy_type=PolicyType.RBAC,
        effect=PolicyEffect.DENY,
        conditions=[
            PolicyCondition(field='action', operator='equals', value='deploy'),
            PolicyCondition(field='role', operator='equals', value='developer'),
        ],
    )
    store.save(policy)

    context = {'action': 'deploy', 'role': 'developer'}
    effect = engine.evaluate(context, policy_type=PolicyType.RBAC)
    assert effect == PolicyEffect.DENY


def test_policy_engine_evaluate_precedence(policy_engine):
    """Test that higher precedence policies override lower ones."""
    engine, store = policy_engine
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
    store.save(low_policy)

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
    store.save(high_policy)

    context = {'action': 'deploy'}
    effect = engine.evaluate(context, policy_type=PolicyType.RBAC)
    # High precedence should win
    assert effect == PolicyEffect.DENY


def test_policy_engine_evaluate_with_explanation(policy_engine):
    """Test evaluation with detailed explanation."""
    engine, store = policy_engine
    policy = Policy(
        policy_id='deny-deploy',
        policy_type=PolicyType.RBAC,
        effect=PolicyEffect.DENY,
        conditions=[
            PolicyCondition(field='action', operator='equals', value='deploy'),
        ],
        description='Deny deployment actions',
    )
    store.save(policy)

    context = {'action': 'deploy'}
    effect, details = engine.evaluate_with_explanation(
        context, policy_type=PolicyType.RBAC
    )

    assert effect == PolicyEffect.DENY
    assert len(details) == 1
    assert details[0]['policy_id'] == 'deny-deploy'
    assert details[0]['applies'] is True
    assert details[0]['effect'] == 'deny'


def test_policy_engine_check_permission_granted(policy_engine):
    """Test permission check when granted."""
    engine, store = policy_engine
    policy = Policy(
        policy_id='allow-admin',
        policy_type=PolicyType.RBAC,
        effect=PolicyEffect.ALLOW,
        conditions=[
            PolicyCondition(field='role', operator='equals', value='admin'),
        ],
    )
    store.save(policy)

    allowed, reason = engine.check_permission('deploy', 'admin', {})
    assert allowed is True
    assert 'granted' in reason


def test_policy_engine_check_permission_denied(policy_engine):
    """Test permission check when denied."""
    engine, store = policy_engine
    policy = Policy(
        policy_id='deny-developer',
        policy_type=PolicyType.RBAC,
        effect=PolicyEffect.DENY,
        conditions=[
            PolicyCondition(field='role', operator='equals', value='developer'),
        ],
    )
    store.save(policy)

    allowed, reason = engine.check_permission('deploy', 'developer', {})
    assert allowed is False
    assert 'denied' in reason


def test_policy_engine_create_policy(policy_engine):
    """Test creating a policy through the engine."""
    engine, store = policy_engine
    policy = engine.create_policy(
        policy_type=PolicyType.RBAC,
        effect=PolicyEffect.DENY,
        conditions=[
            {'field': 'action', 'operator': 'equals', 'value': 'delete'},
        ],
        precedence=PolicyPrecedence.HIGH,
        description='Deny delete actions',
    )

    assert policy is not None
    assert policy.policy_type == PolicyType.RBAC
    assert policy.effect == PolicyEffect.DENY

    # Verify it was saved
    loaded = store.load(policy.policy_id)
    assert loaded is not None
