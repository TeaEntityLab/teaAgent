"""Tests for Role-Based Access Control (TASK-H4-002-02)."""

from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory

import pytest
from teaagent.rbac import (
    Permission,
    RBACSystem,
    Role,
    RoleAssignment,
    RoleStore,
)


def test_role_has_permission():
    """Test checking if role has permission."""
    role = Role(
        role_id='test-role',
        name='developer',
        permissions={Permission.READ_FILE, Permission.WRITE_FILE},
    )

    assert role.has_permission(Permission.READ_FILE) is True
    assert role.has_permission(Permission.WRITE_FILE) is True
    assert role.has_permission(Permission.DELETE_FILE) is False


def test_role_grant_permission():
    """Test granting a permission."""
    role = Role(
        role_id='test-role',
        name='developer',
        permissions={Permission.READ_FILE},
    )

    role.grant_permission(Permission.WRITE_FILE)
    assert role.has_permission(Permission.WRITE_FILE) is True


def test_role_revoke_permission():
    """Test revoking a permission."""
    role = Role(
        role_id='test-role',
        name='developer',
        permissions={Permission.READ_FILE, Permission.WRITE_FILE},
    )

    role.revoke_permission(Permission.WRITE_FILE)
    assert role.has_permission(Permission.WRITE_FILE) is False
    assert role.has_permission(Permission.READ_FILE) is True


def test_role_to_dict_and_from_dict():
    """Test role serialization."""
    role = Role(
        role_id='test-role',
        name='developer',
        description='Developer role',
        permissions={Permission.READ_FILE, Permission.WRITE_FILE},
    )

    data = role.to_dict()
    restored = Role.from_dict(data)

    assert restored.role_id == role.role_id
    assert restored.name == role.name
    assert restored.description == role.description
    assert restored.permissions == role.permissions


def test_role_assignment_is_expired():
    """Test checking if assignment is expired."""
    # Create expired assignment
    past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    assignment = RoleAssignment(
        assignment_id='test-assignment',
        role_id='test-role',
        assignee='user1',
        expires_at=past_time,
    )
    assert assignment.is_expired() is True

    # Create non-expired assignment
    future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    assignment = RoleAssignment(
        assignment_id='test-assignment',
        role_id='test-role',
        assignee='user1',
        expires_at=future_time,
    )
    assert assignment.is_expired() is False

    # Create assignment without expiration
    assignment = RoleAssignment(
        assignment_id='test-assignment',
        role_id='test-role',
        assignee='user1',
    )
    assert assignment.is_expired() is False


def test_role_assignment_to_dict_and_from_dict():
    """Test assignment serialization."""
    assignment = RoleAssignment(
        assignment_id='test-assignment',
        role_id='test-role',
        assignee='user1',
        tenant_id='tenant1',
    )

    data = assignment.to_dict()
    restored = RoleAssignment.from_dict(data)

    assert restored.assignment_id == assignment.assignment_id
    assert restored.role_id == assignment.role_id
    assert restored.assignee == assignment.assignee
    assert restored.tenant_id == assignment.tenant_id


@pytest.fixture
def role_store():
    """Fixture for RoleStore with temporary directory."""
    temp_dir = TemporaryDirectory()
    store = RoleStore(temp_dir.name)
    yield store
    temp_dir.cleanup()


def test_role_store_save_and_load_role(role_store):
    """Test saving and loading a role."""
    role = Role(
        role_id='test-role',
        name='developer',
        permissions={Permission.READ_FILE, Permission.WRITE_FILE},
    )

    role_store.save_role(role)
    loaded = role_store.load_role('test-role')

    assert loaded is not None
    assert loaded.role_id == role.role_id
    assert loaded.name == role.name
    assert loaded.permissions == role.permissions


def test_role_store_delete_role(role_store):
    """Test deleting a role."""
    role = Role(
        role_id='test-role',
        name='developer',
        permissions={Permission.READ_FILE},
    )

    role_store.save_role(role)
    assert role_store.delete_role('test-role') is True
    assert role_store.load_role('test-role') is None


def test_role_store_list_roles(role_store):
    """Test listing all roles."""
    role1 = Role(
        role_id='role-1',
        name='developer',
        permissions={Permission.READ_FILE},
    )
    role2 = Role(
        role_id='role-2',
        name='operator',
        permissions={Permission.START_WORKFLOW},
    )

    role_store.save_role(role1)
    role_store.save_role(role2)

    roles = role_store.list_roles()
    assert len(roles) == 2


def test_role_store_save_and_load_assignment(role_store):
    """Test saving and loading an assignment."""
    assignment = RoleAssignment(
        assignment_id='test-assignment',
        role_id='test-role',
        assignee='user1',
    )

    role_store.save_assignment(assignment)
    loaded = role_store.load_assignment('test-assignment')

    assert loaded is not None
    assert loaded.assignment_id == assignment.assignment_id
    assert loaded.assignee == assignment.assignee


def test_role_store_get_assignments_for_assignee(role_store):
    """Test getting assignments for an assignee."""
    assignment1 = RoleAssignment(
        assignment_id='assignment-1',
        role_id='role-1',
        assignee='user1',
    )
    assignment2 = RoleAssignment(
        assignment_id='assignment-2',
        role_id='role-2',
        assignee='user1',
    )
    assignment3 = RoleAssignment(
        assignment_id='assignment-3',
        role_id='role-1',
        assignee='user2',
    )

    role_store.save_assignment(assignment1)
    role_store.save_assignment(assignment2)
    role_store.save_assignment(assignment3)

    assignments = role_store.get_assignments_for_assignee('user1')
    assert len(assignments) == 2


def test_role_store_get_assignments_for_role(role_store):
    """Test getting assignments for a role."""
    assignment1 = RoleAssignment(
        assignment_id='assignment-1',
        role_id='role-1',
        assignee='user1',
    )
    assignment2 = RoleAssignment(
        assignment_id='assignment-2',
        role_id='role-1',
        assignee='user2',
    )
    assignment3 = RoleAssignment(
        assignment_id='assignment-3',
        role_id='role-2',
        assignee='user1',
    )

    role_store.save_assignment(assignment1)
    role_store.save_assignment(assignment2)
    role_store.save_assignment(assignment3)

    assignments = role_store.get_assignments_for_role('role-1')
    assert len(assignments) == 2


def test_role_store_tenant_isolation():
    """Test tenant isolation in role storage."""
    temp_dir = TemporaryDirectory()
    store_default = RoleStore(temp_dir.name, tenant_id='default')
    store_tenant1 = RoleStore(temp_dir.name, tenant_id='tenant1')

    role = Role(
        role_id='test-role',
        name='developer',
        permissions={Permission.READ_FILE},
    )

    store_default.save_role(role)

    assert store_default.load_role('test-role') is not None
    assert store_tenant1.load_role('test-role') is None

    temp_dir.cleanup()


@pytest.fixture
def rbac_system():
    """Fixture for RBACSystem with temporary directory."""
    temp_dir = TemporaryDirectory()
    rbac = RBACSystem(temp_dir.name)
    yield rbac
    temp_dir.cleanup()


def test_rbac_system_create_role(rbac_system):
    """Test creating a role."""
    role = rbac_system.create_role(
        'developer',
        [Permission.READ_FILE, Permission.WRITE_FILE],
        description='Developer role',
    )

    assert role is not None
    assert role.name == 'developer'
    assert role.has_permission(Permission.READ_FILE) is True
    assert role.has_permission(Permission.WRITE_FILE) is True


def test_rbac_system_assign_role(rbac_system):
    """Test assigning a role to an assignee."""
    role = rbac_system.create_role('developer', [Permission.READ_FILE])
    assignment = rbac_system.assign_role(role.role_id, 'user1')

    assert assignment.assignee == 'user1'
    assert assignment.role_id == role.role_id


def test_rbac_system_revoke_assignment(rbac_system):
    """Test revoking a role assignment."""
    role = rbac_system.create_role('developer', [Permission.READ_FILE])
    assignment = rbac_system.assign_role(role.role_id, 'user1')

    assert rbac_system.revoke_assignment(assignment.assignment_id) is True


def test_rbac_system_get_roles_for_assignee(rbac_system):
    """Test getting roles for an assignee."""
    role1 = rbac_system.create_role('developer', [Permission.READ_FILE])
    role2 = rbac_system.create_role('operator', [Permission.START_WORKFLOW])

    rbac_system.assign_role(role1.role_id, 'user1')
    rbac_system.assign_role(role2.role_id, 'user1')

    roles = rbac_system.get_roles_for_assignee('user1')
    assert len(roles) == 2


def test_rbac_system_check_permission_granted(rbac_system):
    """Test permission check when granted."""
    role = rbac_system.create_role('developer', [Permission.READ_FILE])
    rbac_system.assign_role(role.role_id, 'user1')

    allowed, reason = rbac_system.check_permission('user1', Permission.READ_FILE, {})
    assert allowed is True
    assert 'granted' in reason


def test_rbac_system_check_permission_denied(rbac_system):
    """Test permission check when denied."""
    role = rbac_system.create_role('developer', [Permission.READ_FILE])
    rbac_system.assign_role(role.role_id, 'user1')

    allowed, reason = rbac_system.check_permission('user1', Permission.DELETE_FILE, {})
    assert allowed is False
    assert 'denied' in reason


def test_rbac_system_check_action_permission(rbac_system):
    """Test checking permission for an action."""
    role = rbac_system.create_role('developer', [Permission.READ_FILE])
    rbac_system.assign_role(role.role_id, 'user1')

    allowed, reason = rbac_system.check_action_permission('user1', 'read_file', {})
    assert allowed is True

    allowed, reason = rbac_system.check_action_permission('user1', 'delete_file', {})
    assert allowed is False


def test_rbac_system_expired_assignment(rbac_system):
    """Test that expired assignments are not considered."""
    role = rbac_system.create_role('developer', [Permission.READ_FILE])

    # Create assignment that expires in the past
    past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    rbac_system.assign_role(role.role_id, 'user1', expires_at=past_time)

    # Permission should be denied due to expiration
    allowed, reason = rbac_system.check_permission('user1', Permission.READ_FILE, {})
    assert allowed is False


def test_rbac_system_create_default_roles(rbac_system):
    """Test creating default roles."""
    rbac_system.create_default_roles()

    roles = rbac_system.role_store.list_roles()
    role_names = {role.name for role in roles}

    assert 'admin' in role_names
    assert 'developer' in role_names
    assert 'operator' in role_names
    assert 'viewer' in role_names


def test_rbac_system_admin_has_all_permissions(rbac_system):
    """Test that admin role has all permissions."""
    rbac_system.create_default_roles()

    admin_role = None
    for role in rbac_system.role_store.list_roles():
        if role.name == 'admin':
            admin_role = role
            break

    assert admin_role is not None

    # Admin should have all permissions
    for permission in Permission:
        assert admin_role.has_permission(permission) is True
