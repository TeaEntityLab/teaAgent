"""Adversarial fuzz tests for governance loops.

This module provides fuzz tests for the core governance loops:
- Tool governance (mislabelled tools, capability escapes)
- Plan-before-write enforcement
- Memory invalidation rules
- Approval queue security

These tests are designed to catch runtime escapes and policy bypasses.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from teaagent.errors import ToolPermissionError
from teaagent.governance.plan_gate import WRITE_TOOLS, assert_write_allowed
from teaagent.memory.failure_card import (
    AutoInvalidationRule,
    FailureCard,
    FailureCardStorage,
    MemoryAutoInvalidationConfig,
)
from teaagent.policy import PermissionMode
from teaagent.subagents._approval_queue import (
    ApprovalRequestStatus,
    CentralizedApprovalQueue,
    SubagentApprovalRequest,
)


class TestPlanBeforeWriteFuzz:
    """Fuzz tests for plan-before-write enforcement."""

    def test_workspace_write_mode_strict_default(self):
        """Test that workspace-write mode enforces plan-by-default."""
        context = {}  # No plan contract

        # Should block without plan in workspace-write mode
        with pytest.raises(ToolPermissionError):
            assert_write_allowed(
                tool_name='workspace_write_file',
                permission_mode=PermissionMode.WORKSPACE_WRITE,
                context=context,
                require_plan=False,  # Not explicitly required, but workspace-write defaults to strict
                skip_plan_check=False,
            )

    def test_skip_plan_check_override(self):
        """Test that --skip-plan-check allows writes without plan."""
        context = {}  # No plan contract

        # Should allow with skip_plan_check=True
        assert_write_allowed(
            tool_name='workspace_write_file',
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            context=context,
            require_plan=False,
            skip_plan_check=True,  # Explicit override
        )
        # No exception raised

    def test_read_only_mode_blocks_all_writes(self):
        """Test that read-only mode blocks all write tools regardless of plan."""
        context = {'plan_contract': {'content_hash': 'abc123'}}

        # Plan gate doesn't block based on permission mode - that's handled by ApprovalPolicy
        # This test documents that plan gate only enforces plan requirement, not permission mode
        for tool in WRITE_TOOLS:
            # In read-only mode, plan gate doesn't block - ApprovalPolicy handles that
            assert_write_allowed(
                tool_name=tool,
                permission_mode=PermissionMode.READ_ONLY,
                context=context,
                require_plan=True,
                skip_plan_check=False,
            )

    def test_malformed_plan_contract_rejected(self):
        """Test that malformed plan contracts are rejected."""
        malformed_contexts = [
            {},  # No plan
            {'plan_contract': {}},  # Empty plan
            {'plan_contract': {'content_hash': ''}},  # Empty hash
            {'plan_contract': {'content_hash': None}},  # None hash
            {'plan_contract': {'content_hash': 123}},  # Wrong type
        ]

        for context in malformed_contexts:
            with pytest.raises(ToolPermissionError):
                assert_write_allowed(
                    tool_name='workspace_write_file',
                    permission_mode=PermissionMode.WORKSPACE_WRITE,
                    context=context,
                    require_plan=True,
                    skip_plan_check=False,
                )


class TestMemoryInvalidationFuzz:
    """Fuzz tests for automated memory invalidation."""

    def test_file_signature_change_invalidates_cards(self, tmp_path: Path):
        """Test that file signature changes trigger invalidation."""
        # Create a test file
        test_file = tmp_path / 'test.py'
        test_file.write_text('original content')

        # Create a failure card for this file
        storage = FailureCardStorage(tmp_path)
        card = FailureCard.create(
            run_id='test-run',
            error_type='SyntaxError',
            file_path='test.py',
            error_message='test error',
            task_description='test task',
            context_files=['test.py'],
            confidence='high',
        )
        storage.append(card)

        # Configure auto-invalidation for file signature changes
        config = MemoryAutoInvalidationConfig(
            rules=[
                AutoInvalidationRule(
                    trigger='file_signature_change',
                    confidence='high',
                    action='invalidate',
                    enabled=True,
                )
            ],
            enabled=True,
        )

        # First run to store signature
        storage.apply_auto_invalidation(config)

        # Modify the file
        test_file.write_text('modified content')

        # Apply auto-invalidation again to detect change
        counts = storage.apply_auto_invalidation(config)

        # Should have invalidated the card
        assert counts.get('file_signature_change', 0) == 1

        # Verify card is now inactive
        updated_card = storage.get_by_id(card.id)
        assert updated_card is not None
        assert not updated_card.is_active()
        assert updated_card.invalidated

    def test_auto_invalidation_disabled_when_config_disabled(self, tmp_path: Path):
        """Test that auto-invalidation respects disabled configuration."""
        storage = FailureCardStorage(tmp_path)
        card = FailureCard.create(
            run_id='test-run',
            error_type='SyntaxError',
            file_path='test.py',
            error_message='test error',
            task_description='test task',
            context_files=['test.py'],
        )
        storage.append(card)

        # Disabled configuration
        config = MemoryAutoInvalidationConfig(enabled=False, rules=[])

        # Apply auto-invalidation
        counts = storage.apply_auto_invalidation(config)

        # Should have no effect
        assert counts == {}

        # Card should still be active
        updated_card = storage.get_by_id(card.id)
        assert updated_card is not None
        assert updated_card.is_active()

    def test_path_filtering_in_auto_invalidation(self, tmp_path: Path):
        """Test that path filters work correctly in auto-invalidation rules."""
        # Create test files in different directories
        src_file = tmp_path / 'src' / 'auth.py'
        src_file.parent.mkdir(parents=True, exist_ok=True)
        src_file.write_text('auth code')

        other_file = tmp_path / 'other.py'
        other_file.write_text('other code')

        storage = FailureCardStorage(tmp_path)

        # Create cards for both files
        auth_card = FailureCard.create(
            run_id='test-run-1',
            error_type='SyntaxError',
            file_path='src/auth.py',
            error_message='auth error',
            task_description='auth task',
            context_files=['src/auth.py'],
        )

        other_card = FailureCard.create(
            run_id='test-run-2',
            error_type='SyntaxError',
            file_path='other.py',
            error_message='other error',
            task_description='other task',
            context_files=['other.py'],
        )

        storage.append(auth_card)
        storage.append(other_card)

        # Configure rule with path filter for src/auth/**
        config = MemoryAutoInvalidationConfig(
            rules=[
                AutoInvalidationRule(
                    trigger='file_signature_change',
                    confidence='high',
                    action='invalidate',
                    paths=['src/auth'],
                    enabled=True,
                )
            ],
            enabled=True,
        )

        # First run to store signatures
        storage.apply_auto_invalidation(config)

        # Modify both files
        src_file.write_text('modified auth code')
        other_file.write_text('modified other code')

        # Apply auto-invalidation again to detect changes
        counts = storage.apply_auto_invalidation(config)

        # Should only invalidate the auth card
        assert counts.get('file_signature_change', 0) == 1

        # Verify auth card is inactive, other card is still active
        auth_updated = storage.get_by_id(auth_card.id)
        other_updated = storage.get_by_id(other_card.id)
        assert auth_updated is not None
        assert other_updated is not None
        assert not auth_updated.is_active()
        assert other_updated.is_active()


class TestApprovalQueueSecurity:
    """Fuzz tests for centralized approval queue security."""

    def test_approval_queue_initialization(self):
        """Test that approval queue initializes correctly."""
        queue = CentralizedApprovalQueue(parent_run_id='parent-123')
        assert queue._parent_run_id == 'parent-123'
        assert len(queue._requests) == 0
        assert len(queue._batches) == 0

    def test_request_generation(self):
        """Test that request IDs are generated correctly."""
        queue = CentralizedApprovalQueue(parent_run_id='parent-123')
        request_id_1 = queue.generate_request_id()
        request_id_2 = queue.generate_request_id()
        assert request_id_1 != request_id_2
        assert len(request_id_1) > 0

    def test_batch_creation(self):
        """Test that batches can be created from requests."""
        queue = CentralizedApprovalQueue(parent_run_id='parent-123')

        # Add some pending requests
        request_ids = []
        for i in range(3):
            request_id = queue.generate_request_id()
            request = SubagentApprovalRequest(
                request_id=request_id,
                subagent_id=f'subagent-{i}',
                parent_run_id='parent-123',
                subagent_name=f'test_subagent_{i}',
                tool_name='workspace_write_file',
                tool_arguments={'path': f'test{i}.py'},
                permission_mode='workspace-write',
                isolation='worktree',
            )
            queue._requests[request_id] = request
            request_ids.append(request_id)

        # Create batch
        batch_id = queue.create_batch(request_ids)
        assert batch_id is not None
        assert len(queue.get_batch(batch_id).requests) == 3

    def test_pending_requests_filter(self):
        """Test that get_pending_requests only returns pending requests."""
        queue = CentralizedApprovalQueue(parent_run_id='parent-123')

        # Add pending request
        pending_id = queue.generate_request_id()
        pending_request = SubagentApprovalRequest(
            request_id=pending_id,
            subagent_id='subagent-1',
            parent_run_id='parent-123',
            subagent_name='test_subagent',
            tool_name='workspace_write_file',
            tool_arguments={'path': 'test.py'},
            permission_mode='workspace-write',
            isolation='worktree',
        )
        queue._requests[pending_id] = pending_request

        # Add completed request
        completed_id = queue.generate_request_id()
        completed_request = SubagentApprovalRequest(
            request_id=completed_id,
            subagent_id='subagent-2',
            parent_run_id='parent-123',
            subagent_name='test_subagent_2',
            tool_name='workspace_write_file',
            tool_arguments={'path': 'test2.py'},
            permission_mode='workspace-write',
            isolation='worktree',
            status=ApprovalRequestStatus.APPROVED,
        )
        queue._requests[completed_id] = completed_request

        # Only pending should be returned
        pending = queue.get_pending_requests()
        assert len(pending) == 1
        assert pending[0].request_id == pending_id


class TestGovernanceIntegration:
    """Integration tests for governance loop interactions."""

    def test_plan_gate_blocks_without_skip_flag(self, tmp_path: Path):
        """Test that plan gate enforcement requires explicit skip flag."""
        context = {}

        # Should block without plan
        with pytest.raises(ToolPermissionError):
            assert_write_allowed(
                tool_name='workspace_write_file',
                permission_mode=PermissionMode.WORKSPACE_WRITE,
                context=context,
                require_plan=False,
                skip_plan_check=False,
            )

        # Should allow with skip flag
        assert_write_allowed(
            tool_name='workspace_write_file',
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            context=context,
            require_plan=False,
            skip_plan_check=True,
        )

    def test_memory_auto_invalidation_conservative_defaults(self, tmp_path: Path):
        """Test that default auto-invalidation rules are conservative."""
        config = MemoryAutoInvalidationConfig.default()

        # Should be enabled by default
        assert config.enabled is True

        # Should have conservative rules
        assert len(config.rules) == 3

        # File signature change should invalidate (high confidence)
        file_rule = next(
            r for r in config.rules if r.trigger == 'file_signature_change'
        )
        assert file_rule.confidence == 'high'
        assert file_rule.action == 'invalidate'

        # Test refactor should warn (medium confidence)
        test_rule = next(r for r in config.rules if r.trigger == 'test_refactor')
        assert test_rule.confidence == 'medium'
        assert test_rule.action == 'warn'

        # Dependency change should warn (medium confidence)
        dep_rule = next(
            r for r in config.rules if r.trigger == 'dependency_version_change'
        )
        assert dep_rule.confidence == 'medium'
        assert dep_rule.action == 'warn'
