"""Tests for automation lifecycle management."""

import tempfile

from teaagent.automations import AutomationStore


def test_automation_renew():
    """Test renewing an automation updates next_run_at."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = AutomationStore(tmpdir)
        spec = store.create(
            name='test',
            task='test task',
            schedule='every 1h',
            provider='gpt',
            model='gpt-4',
            permission_mode='read-only',
            context_profile='balanced',
            max_iterations=10,
            max_tool_calls=10,
        )

        renewed = store.renew_automation(spec.automation_id)
        assert renewed.next_run_at is not None
        assert renewed.updated_at != spec.updated_at


def test_automation_expire():
    """Test expiring an automation disables it and clears next_run_at."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = AutomationStore(tmpdir)
        spec = store.create(
            name='test',
            task='test task',
            schedule='every 1h',
            provider='gpt',
            model='gpt-4',
            permission_mode='read-only',
            context_profile='balanced',
            max_iterations=10,
            max_tool_calls=10,
        )

        expired = store.expire_automation(spec.automation_id)
        assert expired.enabled is False
        assert expired.next_run_at is None


def test_automation_transfer_ownership():
    """Test transferring ownership adds provenance note."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = AutomationStore(tmpdir)
        spec = store.create(
            name='test',
            task='test task',
            schedule='every 1h',
            provider='gpt',
            model='gpt-4',
            permission_mode='read-only',
            context_profile='balanced',
            max_iterations=10,
            max_tool_calls=10,
        )

        transferred = store.transfer_ownership(spec.automation_id, 'new-owner')
        assert 'ownership_transfer_to=new-owner' in transferred.provenance_digest
        assert 'transferred_at=' in transferred.provenance_digest


def test_automation_review():
    """Test adding review notes to acceptance criteria."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = AutomationStore(tmpdir)
        spec = store.create(
            name='test',
            task='test task',
            schedule='every 1h',
            provider='gpt',
            model='gpt-4',
            permission_mode='read-only',
            context_profile='balanced',
            max_iterations=10,
            max_tool_calls=10,
            acceptance_criteria='Original criteria',
        )

        reviewed = store.review_automation(
            spec.automation_id, review_notes='Looks good'
        )
        assert 'Review: Looks good' in reviewed.acceptance_criteria
        assert 'Original criteria' in reviewed.acceptance_criteria


def test_automation_explain_skip():
    """Test explaining skip adds skip reason to acceptance criteria."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = AutomationStore(tmpdir)
        spec = store.create(
            name='test',
            task='test task',
            schedule='every 1h',
            provider='gpt',
            model='gpt-4',
            permission_mode='read-only',
            context_profile='balanced',
            max_iterations=10,
            max_tool_calls=10,
        )

        skipped = store.explain_skip(
            spec.automation_id, skip_reason='Dependency missing'
        )
        assert 'Skip Reason: Dependency missing' in skipped.acceptance_criteria
        assert 'at ' in skipped.acceptance_criteria
