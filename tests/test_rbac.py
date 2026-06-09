"""Tests for Role-Based Access Control (TASK-H4-002-02)."""

import unittest
from tempfile import TemporaryDirectory

from teaagent.rbac import (
    Permission,
    RBACSystem,
    Role,
    RoleAssignment,
    RoleStore,
)


class TestRole(unittest.TestCase):
    """Test role management."""

    def test_has_permission(self):
        """Test checking if role has permission."""
        role = Role(
            role_id='test-role',
            name='developer',
            permissions={Permission.READ_FILE, Permission.WRITE_FILE},
        )

        self.assertTrue(role.has_permission(Permission.READ_FILE))
        self.assertTrue(role.has_permission(Permission.WRITE_FILE))
        self.assertFalse(role.has_permission(Permission.DELETE_FILE))

    def test_grant_permission(self):
        """Test granting a permission."""
        role = Role(
            role_id='test-role',
            name='developer',
            permissions={Permission.READ_FILE},
        )

        role.grant_permission(Permission.WRITE_FILE)
        self.assertTrue(role.has_permission(Permission.WRITE_FILE))

    def test_revoke_permission(self):
        """Test revoking a permission."""
        role = Role(
            role_id='test-role',
            name='developer',
            permissions={Permission.READ_FILE, Permission.WRITE_FILE},
        )

        role.revoke_permission(Permission.WRITE_FILE)
        self.assertFalse(role.has_permission(Permission.WRITE_FILE))
        self.assertTrue(role.has_permission(Permission.READ_FILE))

    def test_to_dict_and_from_dict(self):
        """Test role serialization."""
        role = Role(
            role_id='test-role',
            name='developer',
            description='Developer role',
            permissions={Permission.READ_FILE, Permission.WRITE_FILE},
        )

        data = role.to_dict()
        restored = Role.from_dict(data)

        self.assertEqual(restored.role_id, role.role_id)
        self.assertEqual(restored.name, role.name)
        self.assertEqual(restored.description, role.description)
        self.assertEqual(restored.permissions, role.permissions)


class TestRoleAssignment(unittest.TestCase):
    """Test role assignment management."""

    def test_is_expired(self):
        """Test checking if assignment is expired."""
        from datetime import datetime, timedelta, timezone

        # Create expired assignment
        past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assignment = RoleAssignment(
            assignment_id='test-assignment',
            role_id='test-role',
            assignee='user1',
            expires_at=past_time,
        )
        self.assertTrue(assignment.is_expired())

        # Create non-expired assignment
        future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        assignment = RoleAssignment(
            assignment_id='test-assignment',
            role_id='test-role',
            assignee='user1',
            expires_at=future_time,
        )
        self.assertFalse(assignment.is_expired())

        # Create assignment without expiration
        assignment = RoleAssignment(
            assignment_id='test-assignment',
            role_id='test-role',
            assignee='user1',
        )
        self.assertFalse(assignment.is_expired())

    def test_to_dict_and_from_dict(self):
        """Test assignment serialization."""
        assignment = RoleAssignment(
            assignment_id='test-assignment',
            role_id='test-role',
            assignee='user1',
            tenant_id='tenant1',
        )

        data = assignment.to_dict()
        restored = RoleAssignment.from_dict(data)

        self.assertEqual(restored.assignment_id, assignment.assignment_id)
        self.assertEqual(restored.role_id, assignment.role_id)
        self.assertEqual(restored.assignee, assignment.assignee)
        self.assertEqual(restored.tenant_id, assignment.tenant_id)


class TestRoleStore(unittest.TestCase):
    """Test role storage."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.store = RoleStore(self.temp_dir.name)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_save_and_load_role(self):
        """Test saving and loading a role."""
        role = Role(
            role_id='test-role',
            name='developer',
            permissions={Permission.READ_FILE, Permission.WRITE_FILE},
        )

        self.store.save_role(role)
        loaded = self.store.load_role('test-role')

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.role_id, role.role_id)
        self.assertEqual(loaded.name, role.name)
        self.assertEqual(loaded.permissions, role.permissions)

    def test_delete_role(self):
        """Test deleting a role."""
        role = Role(
            role_id='test-role',
            name='developer',
            permissions={Permission.READ_FILE},
        )

        self.store.save_role(role)
        self.assertTrue(self.store.delete_role('test-role'))
        self.assertIsNone(self.store.load_role('test-role'))

    def test_list_roles(self):
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

        self.store.save_role(role1)
        self.store.save_role(role2)

        roles = self.store.list_roles()
        self.assertEqual(len(roles), 2)

    def test_save_and_load_assignment(self):
        """Test saving and loading an assignment."""
        assignment = RoleAssignment(
            assignment_id='test-assignment',
            role_id='test-role',
            assignee='user1',
        )

        self.store.save_assignment(assignment)
        loaded = self.store.load_assignment('test-assignment')

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.assignment_id, assignment.assignment_id)
        self.assertEqual(loaded.assignee, assignment.assignee)

    def test_get_assignments_for_assignee(self):
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

        self.store.save_assignment(assignment1)
        self.store.save_assignment(assignment2)
        self.store.save_assignment(assignment3)

        assignments = self.store.get_assignments_for_assignee('user1')
        self.assertEqual(len(assignments), 2)

    def test_get_assignments_for_role(self):
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

        self.store.save_assignment(assignment1)
        self.store.save_assignment(assignment2)
        self.store.save_assignment(assignment3)

        assignments = self.store.get_assignments_for_role('role-1')
        self.assertEqual(len(assignments), 2)

    def test_tenant_isolation(self):
        """Test tenant isolation in role storage."""
        store_default = RoleStore(self.temp_dir.name, tenant_id='default')
        store_tenant1 = RoleStore(self.temp_dir.name, tenant_id='tenant1')

        role = Role(
            role_id='test-role',
            name='developer',
            permissions={Permission.READ_FILE},
        )

        store_default.save_role(role)

        self.assertIsNotNone(store_default.load_role('test-role'))
        self.assertIsNone(store_tenant1.load_role('test-role'))


class TestRBACSystem(unittest.TestCase):
    """Test RBAC system integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.rbac = RBACSystem(self.temp_dir.name)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_create_role(self):
        """Test creating a role."""
        role = self.rbac.create_role(
            'developer',
            [Permission.READ_FILE, Permission.WRITE_FILE],
            description='Developer role',
        )

        self.assertIsNotNone(role)
        self.assertEqual(role.name, 'developer')
        self.assertTrue(role.has_permission(Permission.READ_FILE))
        self.assertTrue(role.has_permission(Permission.WRITE_FILE))

    def test_assign_role(self):
        """Test assigning a role to an assignee."""
        role = self.rbac.create_role('developer', [Permission.READ_FILE])
        assignment = self.rbac.assign_role(role.role_id, 'user1')

        self.assertEqual(assignment.assignee, 'user1')
        self.assertEqual(assignment.role_id, role.role_id)

    def test_revoke_assignment(self):
        """Test revoking a role assignment."""
        role = self.rbac.create_role('developer', [Permission.READ_FILE])
        assignment = self.rbac.assign_role(role.role_id, 'user1')

        self.assertTrue(self.rbac.revoke_assignment(assignment.assignment_id))

    def test_get_roles_for_assignee(self):
        """Test getting roles for an assignee."""
        role1 = self.rbac.create_role('developer', [Permission.READ_FILE])
        role2 = self.rbac.create_role('operator', [Permission.START_WORKFLOW])

        self.rbac.assign_role(role1.role_id, 'user1')
        self.rbac.assign_role(role2.role_id, 'user1')

        roles = self.rbac.get_roles_for_assignee('user1')
        self.assertEqual(len(roles), 2)

    def test_check_permission_granted(self):
        """Test permission check when granted."""
        role = self.rbac.create_role('developer', [Permission.READ_FILE])
        self.rbac.assign_role(role.role_id, 'user1')

        allowed, reason = self.rbac.check_permission('user1', Permission.READ_FILE, {})
        self.assertTrue(allowed)
        self.assertIn('granted', reason)

    def test_check_permission_denied(self):
        """Test permission check when denied."""
        role = self.rbac.create_role('developer', [Permission.READ_FILE])
        self.rbac.assign_role(role.role_id, 'user1')

        allowed, reason = self.rbac.check_permission(
            'user1', Permission.DELETE_FILE, {}
        )
        self.assertFalse(allowed)
        self.assertIn('denied', reason)

    def test_check_action_permission(self):
        """Test checking permission for an action."""
        role = self.rbac.create_role('developer', [Permission.READ_FILE])
        self.rbac.assign_role(role.role_id, 'user1')

        allowed, reason = self.rbac.check_action_permission('user1', 'read_file', {})
        self.assertTrue(allowed)

        allowed, reason = self.rbac.check_action_permission('user1', 'delete_file', {})
        self.assertFalse(allowed)

    def test_expired_assignment(self):
        """Test that expired assignments are not considered."""
        from datetime import datetime, timedelta, timezone

        role = self.rbac.create_role('developer', [Permission.READ_FILE])

        # Create assignment that expires in the past
        past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        self.rbac.assign_role(role.role_id, 'user1', expires_at=past_time)

        # Permission should be denied due to expiration
        allowed, reason = self.rbac.check_permission('user1', Permission.READ_FILE, {})
        self.assertFalse(allowed)

    def test_create_default_roles(self):
        """Test creating default roles."""
        self.rbac.create_default_roles()

        roles = self.rbac.role_store.list_roles()
        role_names = {role.name for role in roles}

        self.assertIn('admin', role_names)
        self.assertIn('developer', role_names)
        self.assertIn('operator', role_names)
        self.assertIn('viewer', role_names)

    def test_admin_has_all_permissions(self):
        """Test that admin role has all permissions."""
        self.rbac.create_default_roles()

        admin_role = None
        for role in self.rbac.role_store.list_roles():
            if role.name == 'admin':
                admin_role = role
                break

        self.assertIsNotNone(admin_role)

        # Admin should have all permissions
        for permission in Permission:
            self.assertTrue(admin_role.has_permission(permission))


if __name__ == '__main__':
    unittest.main()
