"""Unit tests for plan storage module."""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from teaagent.plan_storage import (
    PlanArtifact,
    PlanBinding,
    PlanContent,
    PlanDiff,
    PlanDiffer,
    PlanMetadata,
    PlanStorage,
    PlanVersioner,
    PlanBinder,
)


@pytest.fixture
def temp_storage(tmp_path):
    """Create a temporary PlanStorage instance."""
    return PlanStorage(root=tmp_path)


@pytest.fixture
def sample_plan():
    """Create a sample plan artifact."""
    metadata = PlanMetadata(
        id=uuid4().hex,
        version=1,
        parent_id=None,
        created_at=datetime.now(),
        created_by="user",
        title="Test Plan",
        content_hash="",
        storage_path=Path(""),
    )

    content = PlanContent(
        title="Test Plan",
        goal="Test goal",
        approach="Test approach",
        steps=[
            {"description": "Step 1", "command": None, "permission_mode": "read_only", "destructive": False},
            {"description": "Step 2", "command": None, "permission_mode": "prompt", "destructive": True},
        ],
        affected_files=["file1.py", "file2.py"],
        risks=["Risk 1", "Risk 2"],
        acceptance_criteria=["Criterion 1", "Criterion 2"],
    )

    return PlanArtifact(metadata=metadata, content=content)


def test_save_plan(temp_storage, sample_plan):
    """Test saving a plan to storage."""
    metadata = temp_storage.save(sample_plan)

    assert metadata.id == sample_plan.metadata.id
    assert metadata.content_hash  # Hash should be computed
    assert metadata.storage_path.exists()
    assert metadata.storage_path.name == f"{sample_plan.metadata.id}.json"


def test_load_plan(temp_storage, sample_plan):
    """Test loading a plan from storage."""
    temp_storage.save(sample_plan)

    loaded_plan = temp_storage.load(sample_plan.metadata.id)

    assert loaded_plan.metadata.id == sample_plan.metadata.id
    assert loaded_plan.metadata.title == sample_plan.metadata.title
    assert loaded_plan.content.title == sample_plan.content.title
    assert loaded_plan.content.goal == sample_plan.content.goal
    assert len(loaded_plan.content.steps) == len(sample_plan.content.steps)
    assert len(loaded_plan.content.affected_files) == len(sample_plan.content.affected_files)


def test_load_nonexistent_plan(temp_storage):
    """Test loading a plan that doesn't exist."""
    with pytest.raises(FileNotFoundError):
        temp_storage.load("nonexistent-id")


def test_list_plans(temp_storage, sample_plan):
    """Test listing all plans in storage."""
    temp_storage.save(sample_plan)

    # Create another plan
    metadata2 = PlanMetadata(
        id=uuid4().hex,
        version=1,
        parent_id=None,
        created_at=datetime.now(),
        created_by="user",
        title="Test Plan 2",
        content_hash="",
        storage_path=Path(""),
    )
    content2 = PlanContent(
        title="Test Plan 2",
        goal="Test goal 2",
        approach="Test approach 2",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )
    plan2 = PlanArtifact(metadata=metadata2, content=content2)
    temp_storage.save(plan2)

    plans = temp_storage.list()

    assert len(plans) == 2
    plan_ids = {p.id for p in plans}
    assert sample_plan.metadata.id in plan_ids
    assert plan2.metadata.id in plan_ids


def test_list_empty_storage(temp_storage):
    """Test listing plans when storage is empty."""
    plans = temp_storage.list()
    assert len(plans) == 0


def test_delete_plan(temp_storage, sample_plan):
    """Test deleting a plan from storage."""
    temp_storage.save(sample_plan)

    # Verify plan exists
    assert sample_plan.metadata.storage_path.exists()

    # Delete plan
    temp_storage.delete(sample_plan.metadata.id)

    # Verify plan is deleted
    assert not sample_plan.metadata.storage_path.exists()


def test_delete_nonexistent_plan(temp_storage):
    """Test deleting a plan that doesn't exist."""
    with pytest.raises(FileNotFoundError):
        temp_storage.delete("nonexistent-id")


def test_content_hash_computation(temp_storage, sample_plan):
    """Test that content hash is computed correctly."""
    metadata = temp_storage.save(sample_plan)

    assert metadata.content_hash.startswith("sha256:")
    assert len(metadata.content_hash) > 7  # "sha256:" + hash


def test_hash_consistency(temp_storage, sample_plan):
    """Test that hash is consistent for same content."""
    metadata1 = temp_storage.save(sample_plan)
    hash1 = metadata1.content_hash

    # Save the same plan again (should have same hash)
    metadata2 = temp_storage.save(sample_plan)
    hash2 = metadata2.content_hash

    assert hash1 == hash2


def test_serialize_deserialize_roundtrip(temp_storage, sample_plan):
    """Test that serialization and deserialization are lossless."""
    temp_storage.save(sample_plan)
    loaded_plan = temp_storage.load(sample_plan.metadata.id)

    # Check metadata
    assert loaded_plan.metadata.id == sample_plan.metadata.id
    assert loaded_plan.metadata.version == sample_plan.metadata.version
    assert loaded_plan.metadata.parent_id == sample_plan.metadata.parent_id
    assert loaded_plan.metadata.created_by == sample_plan.metadata.created_by
    assert loaded_plan.metadata.title == sample_plan.metadata.title

    # Check content
    assert loaded_plan.content.title == sample_plan.content.title
    assert loaded_plan.content.goal == sample_plan.content.goal
    assert loaded_plan.content.approach == sample_plan.content.approach
    assert loaded_plan.content.affected_files == sample_plan.content.affected_files
    assert loaded_plan.content.risks == sample_plan.content.risks
    assert loaded_plan.content.acceptance_criteria == sample_plan.content.acceptance_criteria

    # Check steps
    assert len(loaded_plan.content.steps) == len(sample_plan.content.steps)
    for loaded_step, original_step in zip(loaded_plan.content.steps, sample_plan.content.steps):
        assert loaded_step["description"] == original_step["description"]
        assert loaded_step["permission_mode"] == original_step["permission_mode"]
        assert loaded_step["destructive"] == original_step["destructive"]


def test_storage_directory_creation(tmp_path):
    """Test that storage directory is created if it doesn't exist."""
    plans_dir = tmp_path / ".teaagent" / "plans"
    assert not plans_dir.exists()

    storage = PlanStorage(root=tmp_path)
    assert plans_dir.exists()


def test_multiple_saves_same_id(temp_storage, sample_plan):
    """Test saving the same plan ID multiple times (should overwrite)."""
    temp_storage.save(sample_plan)

    # Modify the plan and save again with same ID
    sample_plan.content.goal = "Updated goal"
    temp_storage.save(sample_plan)

    # Load and verify updated content
    loaded_plan = temp_storage.load(sample_plan.metadata.id)
    assert loaded_plan.content.goal == "Updated goal"


@pytest.fixture
def plan_versioner(temp_storage):
    """Create a PlanVersioner instance."""
    return PlanVersioner(storage=temp_storage)


def test_versioner_create_new_plan(plan_versioner):
    """Test creating a new plan with versioner."""
    content = PlanContent(
        title="New Plan",
        goal="New goal",
        approach="New approach",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )

    plan = plan_versioner.create(content, created_by="user")

    assert plan.metadata.version == 1
    assert plan.metadata.parent_id is None
    assert plan.metadata.created_by == "user"
    assert plan.content.title == "New Plan"


def test_versioner_revise_plan(plan_versioner):
    """Test revising an existing plan."""
    # Create initial plan
    content1 = PlanContent(
        title="Original Plan",
        goal="Original goal",
        approach="Original approach",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )
    plan1 = plan_versioner.create(content1, created_by="user")

    # Revise the plan
    content2 = PlanContent(
        title="Revised Plan",
        goal="Revised goal",
        approach="Revised approach",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )
    plan2 = plan_versioner.revise(plan1.metadata.id, content2, created_by="user")

    assert plan2.metadata.version == 2
    assert plan2.metadata.parent_id == plan1.metadata.id
    assert plan2.content.title == "Revised Plan"


def test_versioner_get_history(plan_versioner):
    """Test getting revision history."""
    # Create initial plan
    content1 = PlanContent(
        title="Plan v1",
        goal="Goal v1",
        approach="Approach v1",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )
    plan1 = plan_versioner.create(content1)

    # Create revision
    content2 = PlanContent(
        title="Plan v2",
        goal="Goal v2",
        approach="Approach v2",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )
    plan2 = plan_versioner.revise(plan1.metadata.id, content2)

    # Create another revision
    content3 = PlanContent(
        title="Plan v3",
        goal="Goal v3",
        approach="Approach v3",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )
    plan3 = plan_versioner.revise(plan2.metadata.id, content3)

    # Get history from latest
    history = plan_versioner.get_history(plan3.metadata.id)

    assert len(history) == 3
    assert history[0].metadata.version == 1
    assert history[1].metadata.version == 2
    assert history[2].metadata.version == 3
    assert history[0].metadata.id == plan1.metadata.id
    assert history[1].metadata.id == plan2.metadata.id
    assert history[2].metadata.id == plan3.metadata.id


def test_versioner_get_history_from_middle(plan_versioner):
    """Test getting history from a middle revision."""
    # Create plan chain
    content1 = PlanContent(
        title="Plan v1",
        goal="Goal v1",
        approach="Approach v1",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )
    plan1 = plan_versioner.create(content1)

    content2 = PlanContent(
        title="Plan v2",
        goal="Goal v2",
        approach="Approach v2",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )
    plan2 = plan_versioner.revise(plan1.metadata.id, content2)

    content3 = PlanContent(
        title="Plan v3",
        goal="Goal v3",
        approach="Approach v3",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )
    plan3 = plan_versioner.revise(plan2.metadata.id, content3)

    # Get history from middle revision
    history = plan_versioner.get_history(plan2.metadata.id)

    assert len(history) == 2
    assert history[0].metadata.version == 1
    assert history[1].metadata.version == 2


def test_versioner_get_latest(plan_versioner):
    """Test getting the latest revision."""
    # Create plan chain
    content1 = PlanContent(
        title="Plan v1",
        goal="Goal v1",
        approach="Approach v1",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )
    plan1 = plan_versioner.create(content1)

    content2 = PlanContent(
        title="Plan v2",
        goal="Goal v2",
        approach="Approach v2",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )
    plan2 = plan_versioner.revise(plan1.metadata.id, content2)

    # Get latest from v1
    latest = plan_versioner.get_latest(plan1.metadata.id)

    assert latest.metadata.version == 2
    assert latest.metadata.id == plan2.metadata.id


def test_versioner_get_latest_single_version(plan_versioner):
    """Test getting latest when there's only one version."""
    content = PlanContent(
        title="Single Plan",
        goal="Goal",
        approach="Approach",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )
    plan = plan_versioner.create(content)

    latest = plan_versioner.get_latest(plan.metadata.id)

    assert latest.metadata.version == 1
    assert latest.metadata.id == plan.metadata.id


def test_versioner_revise_nonexistent(plan_versioner):
    """Test revising a plan that doesn't exist."""
    content = PlanContent(
        title="Revised",
        goal="Goal",
        approach="Approach",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )

    with pytest.raises(FileNotFoundError):
        plan_versioner.revise("nonexistent-id", content)


def test_versioner_get_history_nonexistent(plan_versioner):
    """Test getting history for a plan that doesn't exist."""
    history = plan_versioner.get_history("nonexistent-id")
    assert len(history) == 0


def test_versioner_get_all_revisions(plan_versioner):
    """Test getting all revisions of a plan."""
    # Create plan chain
    content1 = PlanContent(
        title="Plan v1",
        goal="Goal v1",
        approach="Approach v1",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )
    plan1 = plan_versioner.create(content1)

    content2 = PlanContent(
        title="Plan v2",
        goal="Goal v2",
        approach="Approach v2",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )
    plan2 = plan_versioner.revise(plan1.metadata.id, content2)

    # Get all revisions
    all_revisions = plan_versioner.get_all_revisions(plan1.metadata.id)

    assert len(all_revisions) == 2
    assert all_revisions[0].metadata.version == 1
    assert all_revisions[1].metadata.version == 2


@pytest.fixture
def plan_differ(temp_storage):
    """Create a PlanDiffer instance."""
    return PlanDiffer(storage=temp_storage)


def test_differ_identical_plans(plan_differ, temp_storage):
    """Test diffing identical plans."""
    content = PlanContent(
        title="Plan",
        goal="Goal",
        approach="Approach",
        steps=[{"description": "Step 1", "command": None, "permission_mode": "read_only", "destructive": False}],
        affected_files=["file.py"],
        risks=[],
        acceptance_criteria=[],
    )

    plan1 = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=1,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content,
    )
    temp_storage.save(plan1)

    plan2 = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=2,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content,
    )
    temp_storage.save(plan2)

    diff = plan_differ.diff(plan1.metadata.id, plan2.metadata.id)

    assert len(diff.added_steps) == 0
    assert len(diff.removed_steps) == 0
    assert len(diff.modified_steps) == 0
    assert len(diff.changed_files) == 0
    assert "No changes detected" in diff.summary


def test_differ_added_steps(plan_differ, temp_storage):
    """Test diffing plans with added steps."""
    content1 = PlanContent(
        title="Plan",
        goal="Goal",
        approach="Approach",
        steps=[{"description": "Step 1", "command": None, "permission_mode": "read_only", "destructive": False}],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )

    content2 = PlanContent(
        title="Plan",
        goal="Goal",
        approach="Approach",
        steps=[
            {"description": "Step 1", "command": None, "permission_mode": "read_only", "destructive": False},
            {"description": "Step 2", "command": None, "permission_mode": "prompt", "destructive": True},
        ],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )

    plan1 = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=1,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content1,
    )
    temp_storage.save(plan1)

    plan2 = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=2,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content2,
    )
    temp_storage.save(plan2)

    diff = plan_differ.diff(plan1.metadata.id, plan2.metadata.id)

    assert len(diff.added_steps) == 1
    assert diff.added_steps[0]["description"] == "Step 2"
    assert len(diff.removed_steps) == 0


def test_differ_removed_steps(plan_differ, temp_storage):
    """Test diffing plans with removed steps."""
    content1 = PlanContent(
        title="Plan",
        goal="Goal",
        approach="Approach",
        steps=[
            {"description": "Step 1", "command": None, "permission_mode": "read_only", "destructive": False},
            {"description": "Step 2", "command": None, "permission_mode": "prompt", "destructive": True},
        ],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )

    content2 = PlanContent(
        title="Plan",
        goal="Goal",
        approach="Approach",
        steps=[{"description": "Step 1", "command": None, "permission_mode": "read_only", "destructive": False}],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )

    plan1 = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=1,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content1,
    )
    temp_storage.save(plan1)

    plan2 = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=2,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content2,
    )
    temp_storage.save(plan2)

    diff = plan_differ.diff(plan1.metadata.id, plan2.metadata.id)

    assert len(diff.removed_steps) == 1
    assert diff.removed_steps[0]["description"] == "Step 2"
    assert len(diff.added_steps) == 0


def test_differ_changed_files(plan_differ, temp_storage):
    """Test diffing plans with changed files."""
    content1 = PlanContent(
        title="Plan",
        goal="Goal",
        approach="Approach",
        steps=[],
        affected_files=["file1.py"],
        risks=[],
        acceptance_criteria=[],
    )

    content2 = PlanContent(
        title="Plan",
        goal="Goal",
        approach="Approach",
        steps=[],
        affected_files=["file2.py"],
        risks=[],
        acceptance_criteria=[],
    )

    plan1 = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=1,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content1,
    )
    temp_storage.save(plan1)

    plan2 = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=2,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content2,
    )
    temp_storage.save(plan2)

    diff = plan_differ.diff(plan1.metadata.id, plan2.metadata.id)

    assert "file1.py" in diff.changed_files
    assert "file2.py" in diff.changed_files
    assert len(diff.changed_files) == 2


def test_differ_format_markdown(plan_differ, temp_storage):
    """Test formatting diff as Markdown."""
    content1 = PlanContent(
        title="Plan",
        goal="Goal",
        approach="Approach",
        steps=[],
        affected_files=["file1.py"],
        risks=[],
        acceptance_criteria=[],
    )

    content2 = PlanContent(
        title="Plan",
        goal="Goal",
        approach="Approach",
        steps=[],
        affected_files=["file2.py"],
        risks=[],
        acceptance_criteria=[],
    )

    plan1 = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=1,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content1,
    )
    temp_storage.save(plan1)

    plan2 = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=2,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content2,
    )
    temp_storage.save(plan2)

    diff = plan_differ.diff(plan1.metadata.id, plan2.metadata.id)
    formatted = plan_differ.format(diff, format_type="markdown")

    assert "# Plan Diff" in formatted
    assert "Changed Files" in formatted
    assert "file1.py" in formatted
    assert "file2.py" in formatted


def test_differ_format_json(plan_differ, temp_storage):
    """Test formatting diff as JSON."""
    content = PlanContent(
        title="Plan",
        goal="Goal",
        approach="Approach",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )

    plan1 = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=1,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content,
    )
    temp_storage.save(plan1)

    plan2 = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=2,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content,
    )
    temp_storage.save(plan2)

    diff = plan_differ.diff(plan1.metadata.id, plan2.metadata.id)
    formatted = plan_differ.format(diff, format_type="json")

    import json

    parsed = json.loads(formatted)
    assert "plan_a_id" in parsed
    assert "plan_b_id" in parsed
    assert "summary" in parsed


def test_differ_compare_method(plan_differ, temp_storage):
    """Test the compare method."""
    content = PlanContent(
        title="Plan",
        goal="Goal",
        approach="Approach",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )

    plan1 = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=1,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content,
    )
    temp_storage.save(plan1)

    plan2 = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=2,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content,
    )
    temp_storage.save(plan2)

    comparison = plan_differ.compare(plan1.metadata.id, plan2.metadata.id)

    assert comparison["plan_a_id"] == plan1.metadata.id
    assert comparison["plan_b_id"] == plan2.metadata.id
    assert "added_steps" in comparison
    assert "removed_steps" in comparison
    assert "modified_steps" in comparison
    assert "changed_files" in comparison
    assert "summary" in comparison


@pytest.fixture
def plan_binder(temp_storage):
    """Create a PlanBinder instance."""
    return PlanBinder(storage=temp_storage)


def test_binder_bind(plan_binder, temp_storage):
    """Test binding a run to a plan."""
    # Create a plan
    content = PlanContent(
        title="Test Plan",
        goal="Test goal",
        approach="Test approach",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )

    plan = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=1,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Test Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content,
    )
    temp_storage.save(plan)

    # Bind run to plan
    binding = plan_binder.bind("run-123", plan.metadata.id)

    assert binding.run_id == "run-123"
    assert binding.plan_id == plan.metadata.id
    assert binding.plan_hash == plan.metadata.content_hash
    assert binding.verified is True


def test_binder_verify_success(plan_binder, temp_storage):
    """Test verifying a binding with matching hash."""
    # Create a plan
    content = PlanContent(
        title="Test Plan",
        goal="Test goal",
        approach="Test approach",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )

    plan = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=1,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Test Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content,
    )
    temp_storage.save(plan)

    # Bind run to plan
    plan_binder.bind("run-123", plan.metadata.id)

    # Verify binding
    verified = plan_binder.verify("run-123")

    assert verified is True


def test_binder_verify_modified_plan(plan_binder, temp_storage):
    """Test verifying a binding with modified plan (hash mismatch)."""
    # Create a plan
    content = PlanContent(
        title="Test Plan",
        goal="Test goal",
        approach="Test approach",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )

    plan = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=1,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Test Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content,
    )
    temp_storage.save(plan)

    # Bind run to plan
    plan_binder.bind("run-123", plan.metadata.id)

    # Modify the plan
    plan.content.goal = "Modified goal"
    temp_storage.save(plan)

    # Verify binding (should fail due to hash mismatch)
    verified = plan_binder.verify("run-123")

    assert verified is False


def test_binder_verify_no_binding(plan_binder):
    """Test verifying a run with no binding."""
    with pytest.raises(ValueError):
        plan_binder.verify("nonexistent-run")


def test_binder_check_hash(plan_binder, temp_storage):
    """Test checking if a plan hash matches the binding."""
    # Create a plan
    content = PlanContent(
        title="Test Plan",
        goal="Test goal",
        approach="Test approach",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )

    plan = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=1,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Test Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content,
    )
    temp_storage.save(plan)

    # Bind run to plan
    plan_binder.bind("run-123", plan.metadata.id)

    # Check hash (should match)
    matches = plan_binder.check_hash("run-123", plan.metadata.id)
    assert matches is True

    # Check with wrong plan ID
    matches = plan_binder.check_hash("run-123", "wrong-plan-id")
    assert matches is False


def test_binder_get_binding(plan_binder, temp_storage):
    """Test getting a binding."""
    # Create a plan
    content = PlanContent(
        title="Test Plan",
        goal="Test goal",
        approach="Test approach",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )

    plan = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=1,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Test Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content,
    )
    temp_storage.save(plan)

    # Bind run to plan
    plan_binder.bind("run-123", plan.metadata.id)

    # Get binding
    binding = plan_binder.get_binding("run-123")

    assert binding is not None
    assert binding.run_id == "run-123"
    assert binding.plan_id == plan.metadata.id

    # Get nonexistent binding
    binding = plan_binder.get_binding("nonexistent-run")
    assert binding is None


def test_binder_unbind(plan_binder, temp_storage):
    """Test unbinding a run."""
    # Create a plan
    content = PlanContent(
        title="Test Plan",
        goal="Test goal",
        approach="Test approach",
        steps=[],
        affected_files=[],
        risks=[],
        acceptance_criteria=[],
    )

    plan = PlanArtifact(
        metadata=PlanMetadata(
            id=uuid4().hex,
            version=1,
            parent_id=None,
            created_at=datetime.now(),
            created_by="user",
            title="Test Plan",
            content_hash="",
            storage_path=Path(""),
        ),
        content=content,
    )
    temp_storage.save(plan)

    # Bind run to plan
    plan_binder.bind("run-123", plan.metadata.id)

    # Verify binding exists
    assert plan_binder.get_binding("run-123") is not None

    # Unbind
    plan_binder.unbind("run-123")

    # Verify binding is removed
    assert plan_binder.get_binding("run-123") is None


def test_binder_bind_nonexistent_plan(plan_binder):
    """Test binding to a nonexistent plan."""
    with pytest.raises(FileNotFoundError):
        plan_binder.bind("run-123", "nonexistent-plan-id")
