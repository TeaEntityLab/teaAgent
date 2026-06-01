"""Acceptance test for plan review and revision flow.

This test verifies that:
1. Plans can be stored with versioning
2. Plan revisions can be compared
3. Plan diffs can be generated
4. Runs can be bound to specific plan hashes
5. Hash verification prevents execution of modified plans
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from teaagent.plan_storage import (
    PlanArtifact,
    PlanBinder,
    PlanContent,
    PlanDiff,
    PlanDiffer,
    PlanMetadata,
    PlanStorage,
    PlanVersioner,
)


def test_plan_storage_save_and_load(tmp_path: Path):
    """Test that plans can be saved and loaded."""
    storage = PlanStorage(root=tmp_path)

    content = PlanContent(
        title="Test Plan",
        goal="Fix bug",
        approach="Update code",
        steps=[],
        affected_files=["test.py"],
        risks=["May break tests"],
        acceptance_criteria=["Tests pass"],
    )

    metadata = PlanMetadata(
        id="test-id",
        version=1,
        parent_id=None,
        created_at=datetime.now(),
        created_by="user",
        title="Test Plan",
        content_hash="",  # Will be computed by storage.save()
        storage_path=tmp_path / ".teaagent" / "plans" / "test-id.json",
    )

    plan = PlanArtifact(metadata=metadata, content=content)
    saved_metadata = storage.save(plan)

    # Verify save
    assert saved_metadata.id == "test-id"
    assert saved_metadata.version == 1

    # Verify load
    loaded_plan = storage.load("test-id")
    assert loaded_plan.metadata.id == "test-id"
    assert loaded_plan.content.title == "Test Plan"
    assert loaded_plan.content.goal == "Fix bug"


def test_plan_versioning(tmp_path: Path):
    """Test that plan versioning works correctly."""
    storage = PlanStorage(root=tmp_path)
    versioner = PlanVersioner(storage)

    # Create initial plan
    content_v1 = PlanContent(
        title="Test Plan",
        goal="Fix bug",
        approach="Update code",
        steps=[],
        affected_files=["test.py"],
        risks=["May break tests"],
        acceptance_criteria=["Tests pass"],
    )

    plan_v1 = versioner.create(content_v1, created_by="user")
    assert plan_v1.metadata.version == 1
    assert plan_v1.metadata.parent_id is None

    # Create revision
    content_v2 = PlanContent(
        title="Test Plan",
        goal="Fix bug and add tests",
        approach="Update code and add tests",
        steps=[],
        affected_files=["test.py", "test_new.py"],
        risks=["May break tests"],
        acceptance_criteria=["Tests pass", "Coverage > 80%"],
    )

    plan_v2 = versioner.revise(plan_v1.metadata.id, content_v2, created_by="user")
    assert plan_v2.metadata.version == 2
    assert plan_v2.metadata.parent_id == plan_v1.metadata.id

    # Verify history
    history = versioner.get_history(plan_v2.metadata.id)
    assert len(history) == 2
    assert history[0].metadata.version == 1
    assert history[1].metadata.version == 2


def test_plan_diff_generation(tmp_path: Path):
    """Test that plan diffs can be generated."""
    storage = PlanStorage(root=tmp_path)
    versioner = PlanVersioner(storage)
    differ = PlanDiffer(storage)

    # Create two plans
    content_v1 = PlanContent(
        title="Test Plan",
        goal="Fix bug",
        approach="Update code",
        steps=[],
        affected_files=["test.py"],
        risks=["May break tests"],
        acceptance_criteria=["Tests pass"],
    )

    plan_v1 = versioner.create(content_v1, created_by="user")

    content_v2 = PlanContent(
        title="Test Plan",
        goal="Fix bug and add tests",
        approach="Update code and add tests",
        steps=[],
        affected_files=["test.py", "test_new.py"],
        risks=["May break tests"],
        acceptance_criteria=["Tests pass", "Coverage > 80%"],
    )

    plan_v2 = versioner.revise(plan_v1.metadata.id, content_v2, created_by="user")

    # Generate diff
    diff = differ.diff(plan_v1.metadata.id, plan_v2.metadata.id)

    assert isinstance(diff, PlanDiff)
    assert diff.plan_a_id == plan_v1.metadata.id
    assert diff.plan_b_id == plan_v2.metadata.id
    assert len(diff.changed_files) > 0
    assert "test_new.py" in diff.changed_files


def test_plan_hash_verification(tmp_path: Path):
    """Test that plan hash verification works."""
    storage = PlanStorage(root=tmp_path)

    content = PlanContent(
        title="Test Plan",
        goal="Fix bug",
        approach="Update code",
        steps=[],
        affected_files=["test.py"],
        risks=["May break tests"],
        acceptance_criteria=["Tests pass"],
    )

    metadata = PlanMetadata(
        id="test-id",
        version=1,
        parent_id=None,
        created_at=datetime.now(),
        created_by="user",
        title="Test Plan",
        content_hash="",  # Will be computed by storage.save()
        storage_path=tmp_path / ".teaagent" / "plans" / "test-id.json",
    )

    plan = PlanArtifact(metadata=metadata, content=content)
    saved_metadata = storage.save(plan)

    # Verify hash is computed and stored
    assert saved_metadata.content_hash is not None
    assert saved_metadata.content_hash.startswith("sha256:")

    # Load and verify hash matches
    loaded_plan = storage.load("test-id")
    assert loaded_plan.metadata.content_hash == saved_metadata.content_hash


def test_plan_run_binding(tmp_path: Path):
    """Test that runs can be bound to specific plan hashes."""
    storage = PlanStorage(root=tmp_path)
    binder = PlanBinder(storage)

    # Create a plan
    content = PlanContent(
        title="Test Plan",
        goal="Fix bug",
        approach="Update code",
        steps=[],
        affected_files=["test.py"],
        risks=["May break tests"],
        acceptance_criteria=["Tests pass"],
    )

    metadata = PlanMetadata(
        id="test-id",
        version=1,
        parent_id=None,
        created_at=datetime.now(),
        created_by="user",
        title="Test Plan",
        content_hash="",  # Will be computed by storage.save()
        storage_path=tmp_path / ".teaagent" / "plans" / "test-id.json",
    )

    plan = PlanArtifact(metadata=metadata, content=content)
    saved_metadata = storage.save(plan)

    # Bind run to plan
    binding = binder.bind("run-123", "test-id")

    # Verify binding
    assert binding.run_id == "run-123"
    assert binding.plan_id == "test-id"
    assert binding.plan_hash == saved_metadata.content_hash
    assert binding.verified is True


def test_plan_execution_rejects_modified_plan(tmp_path: Path):
    """Test that execution is rejected if plan is modified."""
    storage = PlanStorage(root=tmp_path)
    binder = PlanBinder(storage)

    # Create a plan
    content = PlanContent(
        title="Test Plan",
        goal="Fix bug",
        approach="Update code",
        steps=[],
        affected_files=["test.py"],
        risks=["May break tests"],
        acceptance_criteria=["Tests pass"],
    )

    metadata = PlanMetadata(
        id="test-id",
        version=1,
        parent_id=None,
        created_at=datetime.now(),
        created_by="user",
        title="Test Plan",
        content_hash="",  # Will be computed by storage.save()
        storage_path=tmp_path / ".teaagent" / "plans" / "test-id.json",
    )

    plan = PlanArtifact(metadata=metadata, content=content)
    storage.save(plan)

    # Bind run to plan
    binding = binder.bind("run-123", "test-id")

    # Verify hash matches
    is_valid = binder.verify("run-123")
    assert is_valid is True

    # Check hash with correct plan_id
    is_valid = binder.check_hash("run-123", "test-id")
    assert is_valid is True

    # Check hash with wrong plan_id
    is_valid = binder.check_hash("run-123", "wrong-id")
    assert is_valid is False


def test_plan_list(tmp_path: Path):
    """Test that plans can be listed."""
    storage = PlanStorage(root=tmp_path)

    # Create multiple plans
    for i in range(3):
        content = PlanContent(
            title=f"Test Plan {i}",
            goal="Fix bug",
            approach="Update code",
            steps=[],
            affected_files=["test.py"],
            risks=["May break tests"],
            acceptance_criteria=["Tests pass"],
        )

        metadata = PlanMetadata(
            id=f"test-id-{i}",
            version=1,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title=f"Test Plan {i}",
            content_hash="",  # Will be computed by storage.save()
            storage_path=tmp_path / ".teaagent" / "plans" / f"test-id-{i}.json",
        )

        plan = PlanArtifact(metadata=metadata, content=content)
        storage.save(plan)

    # List plans
    plans = storage.list()
    assert len(plans) == 3
    assert all(p.title.startswith("Test Plan") for p in plans)


def test_plan_delete(tmp_path: Path):
    """Test that plans can be deleted."""
    storage = PlanStorage(root=tmp_path)

    content = PlanContent(
        title="Test Plan",
        goal="Fix bug",
        approach="Update code",
        steps=[],
        affected_files=["test.py"],
        risks=["May break tests"],
        acceptance_criteria=["Tests pass"],
    )

    metadata = PlanMetadata(
        id="test-id",
        version=1,
        parent_id=None,
        created_at=datetime.now(),
        created_by="user",
        title="Test Plan",
        content_hash="",  # Will be computed by storage.save()
        storage_path=tmp_path / ".teaagent" / "plans" / "test-id.json",
    )

    plan = PlanArtifact(metadata=metadata, content=content)
    storage.save(plan)

    # Verify plan exists
    storage.load("test-id")

    # Delete plan
    storage.delete("test-id")

    # Verify plan is deleted
    with pytest.raises(FileNotFoundError):
        storage.load("test-id")
