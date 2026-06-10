"""Role-Based Access Control (RBAC) system.

Wired in shadow/enforce mode via ``teaagent.governance.h4_integration`` (WDA-003).

This module provides role definitions, role assignment, and permission
checking for collaborative agent workflows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from .policy_engine import PolicyEffect, PolicyEngine, PolicyStore, PolicyType


class Permission(str, Enum):
    """Standard permissions for agent actions."""

    # File operations
    READ_FILE = 'read_file'
    WRITE_FILE = 'write_file'
    DELETE_FILE = 'delete_file'

    # Workflow operations
    START_WORKFLOW = 'start_workflow'
    STOP_WORKFLOW = 'stop_workflow'
    RESUME_WORKFLOW = 'resume_workflow'

    # Deployment operations
    DEPLOY = 'deploy'
    ROLLBACK = 'rollback'

    # Administrative operations
    MANAGE_USERS = 'manage_users'
    MANAGE_ROLES = 'manage_roles'
    MANAGE_POLICIES = 'manage_policies'

    # Cost operations
    VIEW_COSTS = 'view_costs'
    SET_BUDGET = 'set_budget'

    # Approval operations
    APPROVE = 'approve'
    REJECT = 'reject'


@dataclass
class Role:
    """A role with associated permissions."""

    role_id: str
    name: str
    description: str = ''
    permissions: set[Permission] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def has_permission(self, permission: Permission) -> bool:
        """Check if role has a specific permission.

        Args:
            permission: Permission to check.

        Returns:
            True if role has permission, False otherwise.
        """
        return permission in self.permissions

    def grant_permission(self, permission: Permission) -> None:
        """Grant a permission to the role.

        Args:
            permission: Permission to grant.
        """
        self.permissions.add(permission)

    def revoke_permission(self, permission: Permission) -> None:
        """Revoke a permission from the role.

        Args:
            permission: Permission to revoke.
        """
        self.permissions.discard(permission)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'role_id': self.role_id,
            'name': self.name,
            'description': self.description,
            'permissions': [p.value for p in self.permissions],
            'metadata': self.metadata,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Role':
        """Create from dictionary."""
        return cls(
            role_id=data['role_id'],
            name=data['name'],
            description=data.get('description', ''),
            permissions={Permission(p) for p in data.get('permissions', [])},
            metadata=data.get('metadata', {}),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
        )


@dataclass
class RoleAssignment:
    """Assignment of a role to a user or agent."""

    assignment_id: str
    role_id: str
    assignee: str  # User ID or agent ID
    tenant_id: str = 'default'
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    expires_at: Optional[str] = None

    def is_expired(self) -> bool:
        """Check if the assignment has expired.

        Returns:
            True if expired, False otherwise.
        """
        if self.expires_at is None:
            return False

        from datetime import datetime, timezone

        try:
            expiry = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            return now >= expiry
        except (ValueError, TypeError):
            return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'assignment_id': self.assignment_id,
            'role_id': self.role_id,
            'assignee': self.assignee,
            'tenant_id': self.tenant_id,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'expires_at': self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'RoleAssignment':
        """Create from dictionary."""
        return cls(
            assignment_id=data['assignment_id'],
            role_id=data['role_id'],
            assignee=data['assignee'],
            tenant_id=data.get('tenant_id', 'default'),
            metadata=data.get('metadata', {}),
            created_at=data.get('created_at'),
            expires_at=data.get('expires_at'),
        )


class RoleStore:
    """Storage for roles and role assignments."""

    def __init__(self, root: str | Path, *, tenant_id: str = 'default') -> None:
        """Initialize the role store.

        Args:
            root: Workspace root directory.
            tenant_id: Tenant ID for multi-tenant scenarios.
        """
        self.root = Path(root).resolve()
        self.tenant_id = tenant_id

        if tenant_id == 'default':
            self.roles_dir = self.root / '.teaagent' / 'roles'
            self.assignments_dir = self.root / '.teaagent' / 'role-assignments'
        else:
            self.roles_dir = self.root / '.teaagent' / 'tenants' / tenant_id / 'roles'
            self.assignments_dir = (
                self.root / '.teaagent' / 'tenants' / tenant_id / 'role-assignments'
            )

        self.roles_dir.mkdir(parents=True, exist_ok=True)
        self.assignments_dir.mkdir(parents=True, exist_ok=True)

    def _role_path(self, role_id: str) -> Path:
        """Get the file path for a role."""
        return self.roles_dir / f'{role_id}.json'

    def _assignment_path(self, assignment_id: str) -> Path:
        """Get the file path for a role assignment."""
        return self.assignments_dir / f'{assignment_id}.json'

    def save_role(self, role: Role) -> None:
        """Save a role to storage.

        Args:
            role: Role to save.
        """
        import time

        from teaagent.storage import atomic_write_text

        path = self._role_path(role.role_id)

        # Update timestamps
        if path.exists():
            existing = self.load_role(role.role_id)
            if existing:
                role.created_at = existing.created_at
        else:
            if role.created_at is None:
                role.created_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

        role.updated_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

        atomic_write_text(path, json.dumps(role.to_dict(), indent=2))

    def load_role(self, role_id: str) -> Optional[Role]:
        """Load a role from storage.

        Args:
            role_id: Role ID to load.

        Returns:
            Role if found, None otherwise.
        """
        path = self._role_path(role_id)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return Role.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def delete_role(self, role_id: str) -> bool:
        """Delete a role from storage.

        Args:
            role_id: Role ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        path = self._role_path(role_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_roles(self) -> list[Role]:
        """List all roles.

        Returns:
            List of roles.
        """
        roles = []
        for path in self.roles_dir.glob('*.json'):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                roles.append(Role.from_dict(data))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return roles

    def save_assignment(self, assignment: RoleAssignment) -> None:
        """Save a role assignment to storage.

        Args:
            assignment: Assignment to save.
        """
        import time

        from teaagent.storage import atomic_write_text

        path = self._assignment_path(assignment.assignment_id)

        if assignment.created_at is None:
            assignment.created_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

        atomic_write_text(path, json.dumps(assignment.to_dict(), indent=2))

    def load_assignment(self, assignment_id: str) -> Optional[RoleAssignment]:
        """Load a role assignment from storage.

        Args:
            assignment_id: Assignment ID to load.

        Returns:
            Assignment if found, None otherwise.
        """
        path = self._assignment_path(assignment_id)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return RoleAssignment.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def delete_assignment(self, assignment_id: str) -> bool:
        """Delete a role assignment from storage.

        Args:
            assignment_id: Assignment ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        path = self._assignment_path(assignment_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def get_assignments_for_assignee(self, assignee: str) -> list[RoleAssignment]:
        """Get all role assignments for a specific assignee.

        Args:
            assignee: Assignee ID.

        Returns:
            List of role assignments.
        """
        assignments = []
        for path in self.assignments_dir.glob('*.json'):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                assignment = RoleAssignment.from_dict(data)
                if assignment.assignee == assignee:
                    assignments.append(assignment)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return assignments

    def get_assignments_for_role(self, role_id: str) -> list[RoleAssignment]:
        """Get all role assignments for a specific role.

        Args:
            role_id: Role ID.

        Returns:
            List of role assignments.
        """
        assignments = []
        for path in self.assignments_dir.glob('*.json'):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                assignment = RoleAssignment.from_dict(data)
                if assignment.role_id == role_id:
                    assignments.append(assignment)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return assignments


class RBACSystem:
    """Role-Based Access Control system.

    Combines role management with policy engine for comprehensive
    permission checking.
    """

    def __init__(self, root: str | Path, *, tenant_id: str = 'default') -> None:
        """Initialize the RBAC system.

        Args:
            root: Workspace root directory.
            tenant_id: Tenant ID for multi-tenant scenarios.
        """
        self.root = Path(root).resolve()
        self.tenant_id = tenant_id
        self.role_store = RoleStore(self.root, tenant_id=tenant_id)
        self.policy_store = PolicyStore(self.root, tenant_id=tenant_id)
        self.policy_engine = PolicyEngine(self.policy_store)

    def create_role(
        self,
        name: str,
        permissions: list[Permission],
        *,
        description: str = '',
        metadata: Optional[dict[str, Any]] = None,
    ) -> Role:
        """Create a new role.

        Args:
            name: Role name.
            permissions: List of permissions for the role.
            description: Role description.
            metadata: Additional metadata.

        Returns:
            Created role.
        """
        role_id = str(uuid4())
        role = Role(
            role_id=role_id,
            name=name,
            description=description,
            permissions=set(permissions),
            metadata=metadata or {},
        )

        self.role_store.save_role(role)

        # Create corresponding policy for the role
        self._create_role_policy(role)

        return role

    def _create_role_policy(self, role: Role) -> None:
        """Create a policy for a role based on its permissions.

        Args:
            role: Role to create policy for.
        """
        # Create a policy that allows actions based on role permissions
        conditions = [
            {
                'field': 'role',
                'operator': 'equals',
                'value': role.name,
            }
        ]

        self.policy_engine.create_policy(
            policy_type=PolicyType.RBAC,
            effect=PolicyEffect.ALLOW,
            conditions=conditions,
            description=f'RBAC policy for role: {role.name}',
            metadata={'role_id': role.role_id},
        )

    def assign_role(
        self,
        role_id: str,
        assignee: str,
        *,
        expires_at: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> RoleAssignment:
        """Assign a role to an assignee.

        Args:
            role_id: Role ID to assign.
            assignee: Assignee ID (user or agent).
            expires_at: Optional expiration timestamp.
            metadata: Additional metadata.

        Returns:
            Created assignment.
        """
        assignment_id = str(uuid4())
        assignment = RoleAssignment(
            assignment_id=assignment_id,
            role_id=role_id,
            assignee=assignee,
            tenant_id=self.tenant_id,
            expires_at=expires_at,
            metadata=metadata or {},
        )

        self.role_store.save_assignment(assignment)
        return assignment

    def revoke_assignment(self, assignment_id: str) -> bool:
        """Revoke a role assignment.

        Args:
            assignment_id: Assignment ID to revoke.

        Returns:
            True if revoked, False if not found.
        """
        return self.role_store.delete_assignment(assignment_id)

    def get_roles_for_assignee(self, assignee: str) -> list[Role]:
        """Get all roles assigned to an assignee.

        Args:
            assignee: Assignee ID.

        Returns:
            List of roles.
        """
        assignments = self.role_store.get_assignments_for_assignee(assignee)
        roles = []

        for assignment in assignments:
            # Skip expired assignments
            if assignment.is_expired():
                continue

            role = self.role_store.load_role(assignment.role_id)
            if role:
                roles.append(role)

        return roles

    def check_permission(
        self,
        assignee: str,
        permission: Permission,
        context: dict[str, Any],
    ) -> tuple[bool, str]:
        """Check if an assignee has a specific permission.

        Args:
            assignee: Assignee ID to check.
            permission: Permission to check.
            context: Additional context for evaluation.

        Returns:
            Tuple of (allowed, reason).
        """
        # Get roles for the assignee
        roles = self.get_roles_for_assignee(assignee)

        # Check if any role has the permission
        for role in roles:
            if role.has_permission(permission):
                # Use policy engine for final decision
                context_with_role = {
                    'role': role.name,
                    'permission': permission.value,
                    **context,
                }
                allowed, reason = self.policy_engine.check_permission(
                    permission.value, role.name, context_with_role
                )
                if allowed:
                    return True, f'Permission granted via role: {role.name}'

        return False, f'Permission denied: no role with permission {permission.value}'

    def check_action_permission(
        self,
        assignee: str,
        action: str,
        context: dict[str, Any],
    ) -> tuple[bool, str]:
        """Check if an assignee has permission for a specific action.

        Args:
            assignee: Assignee ID to check.
            action: Action to check.
            context: Additional context for evaluation.

        Returns:
            Tuple of (allowed, reason).
        """
        # Map action to permission
        action_permission_map = {
            'read_file': Permission.READ_FILE,
            'write_file': Permission.WRITE_FILE,
            'delete_file': Permission.DELETE_FILE,
            'start_workflow': Permission.START_WORKFLOW,
            'stop_workflow': Permission.STOP_WORKFLOW,
            'resume_workflow': Permission.RESUME_WORKFLOW,
            'deploy': Permission.DEPLOY,
            'rollback': Permission.ROLLBACK,
            'approve': Permission.APPROVE,
            'reject': Permission.REJECT,
        }

        permission = action_permission_map.get(action)
        if permission is None:
            # Unknown action, use policy engine directly
            return self.policy_engine.check_permission(action, assignee, context)

        return self.check_permission(assignee, permission, context)

    def create_default_roles(self) -> None:
        """Create default roles for the system.

        Creates standard roles: admin, developer, operator, viewer.
        """
        # Admin role - all permissions
        admin_permissions = list(Permission)
        self.create_role(
            'admin',
            admin_permissions,
            description='Administrator with full access',
        )

        # Developer role - development permissions
        developer_permissions = [
            Permission.READ_FILE,
            Permission.WRITE_FILE,
            Permission.START_WORKFLOW,
            Permission.STOP_WORKFLOW,
            Permission.VIEW_COSTS,
        ]
        self.create_role(
            'developer',
            developer_permissions,
            description='Developer with standard development access',
        )

        # Operator role - operational permissions
        operator_permissions = [
            Permission.READ_FILE,
            Permission.START_WORKFLOW,
            Permission.STOP_WORKFLOW,
            Permission.RESUME_WORKFLOW,
            Permission.VIEW_COSTS,
            Permission.APPROVE,
            Permission.REJECT,
        ]
        self.create_role(
            'operator',
            operator_permissions,
            description='Operator with workflow management access',
        )

        # Viewer role - read-only permissions
        viewer_permissions = [
            Permission.READ_FILE,
            Permission.VIEW_COSTS,
        ]
        self.create_role(
            'viewer',
            viewer_permissions,
            description='Viewer with read-only access',
        )
