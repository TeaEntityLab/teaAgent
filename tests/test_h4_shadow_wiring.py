"""Tests for H4 shadow wiring (WDA-002 / WDA-003)."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock

from teaagent.governance.h4_integration import (
    H4GovernanceMode,
    check_subagent_launch_rbac,
    evaluate_approval_policy_shadow,
    rbac_governance_mode,
)
from teaagent.rbac import Permission, RBACSystem
from teaagent.runner._approval_manager import RunnerApprovalCoordinator
from teaagent.runner._types import ApprovalRequest


class PolicyShadowWiringTests(unittest.TestCase):
    def test_approval_shadow_records_audit_event(self) -> None:
        audit = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            evaluate_approval_policy_shadow(
                workspace_root=tmp,
                audit=audit,
                run_id='run-1',
                tool_name='workspace_write_file',
                arguments={'path': 'a.txt'},
                destructive=True,
                call_id='call-1',
            )
        audit.record.assert_called_once()
        args, kwargs = audit.record.call_args
        self.assertEqual(args[0], 'h4_governance_shadow')
        self.assertEqual(args[1], 'run-1')
        self.assertEqual(kwargs['surface'], 'approval')
        self.assertEqual(kwargs['mode'], H4GovernanceMode.SHADOW.value)
        self.assertFalse(kwargs['enforced'])

    def test_runner_coordinator_invokes_policy_shadow(self) -> None:
        audit = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            coordinator = RunnerApprovalCoordinator(
                approval_policy=MagicMock(
                    permission_mode=MagicMock(),
                    approval_store=None,
                ),
                approval_handler=lambda _req: True,
                workspace_root=tmp,
            )
            request = ApprovalRequest(
                call_id='call-2',
                tool_name='workspace_write_file',
                arguments={'path': 'b.txt'},
                reason='test',
                annotations={'destructive': True},
                run_id='run-2',
            )
            approved = coordinator.handle_approval_request(
                approval_request=request,
                audit=audit,
                run_id='run-2',
            )
        self.assertTrue(approved)
        event_types = [call.args[0] for call in audit.record.call_args_list]
        self.assertIn('h4_governance_shadow', event_types)


class RBACShadowWiringTests(unittest.TestCase):
    def test_subagent_launch_shadow_allows_without_roles(self) -> None:
        audit = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            allowed, _reason = check_subagent_launch_rbac(
                workspace_root=tmp,
                audit=audit,
                parent_run_id='parent-run',
                assignee='operator-1',
                def_name='researcher',
                depth=1,
            )
        self.assertTrue(allowed)
        audit.record.assert_called_once()
        kwargs = audit.record.call_args.kwargs
        self.assertEqual(kwargs['surface'], 'subagent_launch')
        self.assertFalse(kwargs['enforced'])

    def test_subagent_launch_enforce_denies_without_permission(self) -> None:
        audit = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            rbac = RBACSystem(tmp)
            viewer = rbac.create_role('viewer', [Permission.READ_FILE])
            rbac.assign_role(viewer.role_id, 'operator-2')
            old = os.environ.get('TEAAGENT_H4_RBAC_MODE')
            os.environ['TEAAGENT_H4_RBAC_MODE'] = 'enforce'
            try:
                self.assertEqual(rbac_governance_mode(), H4GovernanceMode.ENFORCE)
                allowed, reason = check_subagent_launch_rbac(
                    workspace_root=tmp,
                    audit=audit,
                    parent_run_id='parent-run',
                    assignee='operator-2',
                    def_name='researcher',
                    depth=1,
                )
            finally:
                if old is None:
                    os.environ.pop('TEAAGENT_H4_RBAC_MODE', None)
                else:
                    os.environ['TEAAGENT_H4_RBAC_MODE'] = old
        self.assertFalse(allowed)
        self.assertIn('Permission denied', reason)
        self.assertTrue(audit.record.call_args.kwargs['enforced'])
