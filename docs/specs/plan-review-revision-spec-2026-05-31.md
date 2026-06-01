# Plan Review and Revision Technical Specification

**Status:** Draft
**Priority:** P0
**Size:** Large (2-3 weeks)
**Acceptance Test:** `test_plan_review_revision_flow.py`

---

## Problem Statement

When a plan is generated (either manually or via issue-to-plan intake), operators need to:
1. Review the plan before execution
2. Compare different plan revisions
3. Bind execution to an accepted plan hash
4. Ensure the agent doesn't run from a modified plan

Currently, there is no:
- Plan versioning system
- Plan diff/comparison tool
- Run-to-plan binding mechanism
- Hash verification for plan integrity

This leads to:
- No audit trail of plan changes
- Risk of executing from modified plans
- No way to compare plan revisions
- No guarantee that execution matches the reviewed plan

---

## Requirements

### Functional Requirements

1. **Plan Storage and Versioning**
   - Store plans in a persistent location (`.teaagent/plans/`)
   - Version plans with unique IDs and timestamps
   - Track plan revisions with parent-child relationships
   - Compute content hashes for plan integrity

2. **Plan Diff and Comparison**
   - Compare two plan revisions side-by-side
   - Highlight differences in steps, affected files, risks
   - Generate a human-readable diff output
   - Support JSON and Markdown diff formats

3. **Run-to-Plan Binding**
   - Bind a run execution to a specific plan hash
   - Verify plan hash before execution
   - Reject execution if plan has been modified
   - Record plan hash in audit log

4. **Hash Verification**
   - Compute SHA-256 hash of plan content
   - Verify hash integrity before execution
   - Detect tampering or unauthorized modifications
   - Support hash-based plan references

### Non-Functional Requirements

1. **Performance:** Plan diff should complete within 2 seconds for typical plans
2. **Integrity:** Hash verification should detect all modifications
3. **Usability:** Plan diff should be understandable by developers
4. **Security:** Plan binding should prevent execution of modified plans

---

## Architecture Design

### Components

```
┌─────────────────┐
│  Plan Artifact   │
│  (JSON/Markdown) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PlanStorage     │
│ - save()        │
│ - load()        │
│ - list()        │
│ - version()     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PlanVersioner   │
│ - create()      │
│ - revise()      │
│ - get_history() │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PlanDiffer      │
│ - diff()        │
│ - compare()     │
│ - format()      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PlanBinder      │
│ - bind()        │
│ - verify()      │
│ - check_hash()  │
└─────────────────┘
```

### Data Structures

```python
@dataclass
class PlanMetadata:
    """Metadata for a plan."""
    id: str  # UUID
    version: int
    parent_id: Optional[str]  # UUID of parent revision
    created_at: datetime
    created_by: str  # user or system
    title: str
    content_hash: str  # SHA-256
    storage_path: Path

@dataclass
class PlanArtifact:
    """Complete plan artifact with metadata and content."""
    metadata: PlanMetadata
    content: PlanContent

@dataclass
class PlanContent:
    """Content of a plan."""
    title: str
    goal: str
    approach: str
    steps: list[PlanStep]
    affected_files: list[str]
    risks: list[str]
    acceptance_criteria: list[str]

@dataclass
class PlanStep:
    """A single step in the plan."""
    description: str
    command: Optional[str]
    permission_mode: str
    destructive: bool

@dataclass
class PlanDiff:
    """Difference between two plan revisions."""
    plan_a_id: str
    plan_b_id: str
    added_steps: list[PlanStep]
    removed_steps: list[PlanStep]
    modified_steps: list[tuple[PlanStep, PlanStep]]
    changed_files: set[str]
    summary: str

@dataclass
class PlanBinding:
    """Binding between a run and a plan."""
    run_id: str
    plan_id: str
    plan_hash: str
    bound_at: datetime
    verified: bool
```

### Plan Storage Format

```json
{
  "metadata": {
    "id": "uuid",
    "version": 1,
    "parent_id": null,
    "created_at": "2026-05-31T12:00:00Z",
    "created_by": "user",
    "title": "Fix authentication bug",
    "content_hash": "sha256:abc123...",
    "storage_path": ".teaagent/plans/uuid.json"
  },
  "content": {
    "title": "Fix authentication bug",
    "goal": "Fix JWT token validation",
    "approach": "Update token validation logic",
    "steps": [...],
    "affected_files": ["auth.py"],
    "risks": ["may break existing sessions"],
    "acceptance_criteria": [...]
  }
}
```

---

## API Design

### PlanStorage

```python
class PlanStorage:
    """Persistent storage for plan artifacts."""

    def __init__(self, root: Path):
        self._root = Path(root) / ".teaagent" / "plans"
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, plan: PlanArtifact) -> PlanMetadata:
        """Save a plan artifact to storage.

        Args:
            plan: Plan artifact to save

        Returns:
            PlanMetadata with assigned ID and hash
        """
        # Implementation logic
        pass

    def load(self, plan_id: str) -> PlanArtifact:
        """Load a plan artifact from storage.

        Args:
            plan_id: Plan UUID

        Returns:
            PlanArtifact
        """
        # Implementation logic
        pass

    def list(self) -> list[PlanMetadata]:
        """List all plans in storage.

        Returns:
            List of PlanMetadata
        """
        # Implementation logic
        pass

    def delete(self, plan_id: str) -> None:
        """Delete a plan from storage.

        Args:
            plan_id: Plan UUID
        """
        # Implementation logic
        pass
```

### PlanVersioner

```python
class PlanVersioner:
    """Manages plan versioning and revision history."""

    def __init__(self, storage: PlanStorage):
        self._storage = storage

    def create(self, content: PlanContent, created_by: str = "user") -> PlanArtifact:
        """Create a new plan (version 1).

        Args:
            content: Plan content
            created_by: Creator identifier

        Returns:
            PlanArtifact with metadata
        """
        # Implementation logic
        pass

    def revise(self, parent_id: str, new_content: PlanContent, created_by: str = "user") -> PlanArtifact:
        """Create a new revision of an existing plan.

        Args:
            parent_id: UUID of parent plan
            new_content: New plan content
            created_by: Creator identifier

        Returns:
            PlanArtifact with incremented version
        """
        # Implementation logic
        pass

    def get_history(self, plan_id: str) -> list[PlanArtifact]:
        """Get revision history for a plan.

        Args:
            plan_id: Plan UUID

        Returns:
            List of PlanArtifact in version order
        """
        # Implementation logic
        pass

    def get_latest(self, plan_id: str) -> PlanArtifact:
        """Get the latest revision of a plan.

        Args:
            plan_id: Plan UUID (any version)

        Returns:
            Latest PlanArtifact
        """
        # Implementation logic
        pass
```

### PlanDiffer

```python
class PlanDiffer:
    """Compares plan revisions and generates diffs."""

    def diff(self, plan_a: PlanArtifact, plan_b: PlanArtifact) -> PlanDiff:
        """Generate a diff between two plan revisions.

        Args:
            plan_a: First plan
            plan_b: Second plan

        Returns:
            PlanDiff with differences
        """
        # Implementation logic
        pass

    def compare(self, plan_a_id: str, plan_b_id: str, storage: PlanStorage) -> PlanDiff:
        """Compare two plans by ID.

        Args:
            plan_a_id: First plan UUID
            plan_b_id: Second plan UUID
            storage: PlanStorage instance

        Returns:
            PlanDiff with differences
        """
        # Implementation logic
        pass

    def format_markdown(self, diff: PlanDiff) -> str:
        """Format diff as Markdown.

        Args:
            diff: PlanDiff to format

        Returns:
            Markdown string
        """
        # Implementation logic
        pass

    def format_json(self, diff: PlanDiff) -> dict:
        """Format diff as JSON.

        Args:
            diff: PlanDiff to format

        Returns:
            JSON-serializable dict
        """
        # Implementation logic
        pass
```

### PlanBinder

```python
class PlanBinder:
    """Binds runs to plans and verifies integrity."""

    def __init__(self, storage: PlanStorage):
        self._storage = storage
        self._bindings: dict[str, PlanBinding] = {}  # run_id -> binding

    def bind(self, run_id: str, plan_id: str) -> PlanBinding:
        """Bind a run to a plan.

        Args:
            run_id: Run identifier
            plan_id: Plan UUID

        Returns:
            PlanBinding
        """
        # Implementation logic
        pass

    def verify(self, run_id: str) -> bool:
        """Verify that the bound plan hasn't been modified.

        Args:
            run_id: Run identifier

        Returns:
            True if plan hash matches, False otherwise
        """
        # Implementation logic
        pass

    def check_hash(self, plan_id: str, expected_hash: str) -> bool:
        """Check if a plan's hash matches the expected value.

        Args:
            plan_id: Plan UUID
            expected_hash: Expected SHA-256 hash

        Returns:
            True if hash matches, False otherwise
        """
        # Implementation logic
        pass

    def get_binding(self, run_id: str) -> Optional[PlanBinding]:
        """Get the binding for a run.

        Args:
            run_id: Run identifier

        Returns:
            PlanBinding or None
        """
        # Implementation logic
        pass
```

---

## Hash Computation

### Hash Algorithm

```python
import hashlib
import json

def compute_plan_hash(content: PlanContent) -> str:
    """Compute SHA-256 hash of plan content.

    Args:
        content: PlanContent to hash

    Returns:
        SHA-256 hash as hex string with "sha256:" prefix
    """
    # Convert to canonical JSON (sorted keys, no whitespace)
    canonical = json.dumps(content.__dict__, sort_keys=True, separators=(',', ':'))
    hash_bytes = hashlib.sha256(canonical.encode('utf-8')).digest()
    return f"sha256:{hash_bytes.hex()}"
```

### Hash Verification

```python
def verify_plan_hash(plan: PlanArtifact, expected_hash: str) -> bool:
    """Verify that a plan's hash matches the expected value.

    Args:
        plan: PlanArtifact to verify
        expected_hash: Expected hash

    Returns:
        True if hash matches, False otherwise
    """
    actual_hash = compute_plan_hash(plan.content)
    return actual_hash == expected_hash
```

---

## Plan Diff Algorithm

### Step Comparison

```python
def compare_steps(steps_a: list[PlanStep], steps_b: list[PlanStep]) -> dict:
    """Compare two lists of plan steps.

    Returns:
        Dict with 'added', 'removed', 'modified' keys
    """
    # Use sequence matching algorithm (e.g., difflib.SequenceMatcher)
    # to identify added, removed, and modified steps
    pass
```

### File Comparison

```python
def compare_files(files_a: list[str], files_b: list[str]) -> set:
    """Compare two lists of affected files.

    Returns:
        Set of changed files
    """
    set_a = set(files_a)
    set_b = set(files_b)
    return (set_a | set_b) - (set_a & set_b)
```

---

## Implementation Phases

### Phase 1: Plan Storage (Week 1)

**Goal:** Implement `PlanStorage` for persistent plan storage

**Tasks:**
1. Create `PlanMetadata`, `PlanArtifact`, `PlanContent` dataclasses
2. Implement `PlanStorage.save()` method
3. Implement `PlanStorage.load()` method
4. Implement `PlanStorage.list()` method
5. Implement hash computation
6. Add unit tests for storage operations
7. Add unit tests for hash computation

**Acceptance:**
- Plans can be saved and loaded
- Hashes are computed correctly
- Storage persists across process restarts

### Phase 2: Plan Versioning (Week 1-2)

**Goal:** Implement `PlanVersioner` for plan revision management

**Tasks:**
1. Implement `PlanVersioner.create()` method
2. Implement `PlanVersioner.revise()` method
3. Implement `PlanVersioner.get_history()` method
4. Implement parent-child relationship tracking
5. Add unit tests for versioning
6. Add unit tests for revision history

**Acceptance:**
- Plans can be created with version 1
- Plans can be revised with incremented versions
- Revision history is accurate

### Phase 3: Plan Diff (Week 2)

**Goal:** Implement `PlanDiffer` for plan comparison

**Tasks:**
1. Create `PlanDiff` dataclass
2. Implement `PlanDiffer.diff()` method
3. Implement step comparison algorithm
4. Implement file comparison algorithm
5. Implement `PlanDiffer.format_markdown()` method
6. Implement `PlanDiffer.format_json()` method
7. Add unit tests for diff generation
8. Add unit tests for diff formatting

**Acceptance:**
- Plan diffs are accurate
- Diff output is readable
- Both Markdown and JSON formats work

### Phase 4: Plan Binding (Week 2-3)

**Goal:** Implement `PlanBinder` for run-to-plan binding

**Tasks:**
1. Create `PlanBinding` dataclass
2. Implement `PlanBinder.bind()` method
3. Implement `PlanBinder.verify()` method
4. Implement `PlanBinder.check_hash()` method
5. Integrate with audit log
6. Add unit tests for binding
7. Add unit tests for verification

**Acceptance:**
- Runs can be bound to plans
- Hash verification detects modifications
- Audit log records plan bindings

### Phase 5: CLI Integration (Week 3)

**Goal:** Add CLI commands for plan review and revision

**Tasks:**
1. Add `agent plan create` command
2. Add `agent plan revise` command
3. Add `agent plan diff` command
4. Add `agent plan show` command
5. Add `agent run --from-plan` flag
6. Add acceptance test `test_plan_review_revision_flow.py`

**Acceptance:**
- CLI commands work correctly
- `--from-plan` flag binds run to plan
- Acceptance test verifies end-to-end flow

---

## Integration Points

### Existing Plan Mode

**File:** `teaagent/plan_mode.py`
**Integration:** Use `PlanContent` structure compatible with existing plan mode

### Existing Audit Log

**File:** `teaagent/audit.py`
**Integration:** Record plan bindings in audit events

```python
audit.log_event({
    "event_type": "plan_bound",
    "run_id": run_id,
    "plan_id": plan_id,
    "plan_hash": plan_hash,
    "bound_at": timestamp
})
```

### Existing CLI

**File:** `teaagent/cli/_handlers/_agent.py`
**Integration:** Add `--from-plan` flag to `agent run` command

---

## Acceptance Criteria

### Unit Tests

1. `test_plan_storage_save_load()`
2. `test_plan_storage_list()`
3. `test_plan_hash_computation()`
4. `test_plan_versioner_create()`
5. `test_plan_versioner_revise()`
6. `test_plan_versioner_history()`
7. `test_plan_differ_diff()`
8. `test_plan_differ_format_markdown()`
9. `test_plan_binder_bind()`
10. `test_plan_binder_verify()`
11. `test_plan_binder_hash_mismatch()`

### Acceptance Test

**File:** `tests/acceptance/test_plan_review_revision_flow.py`

**Scenario:** User can compare two plan revisions and bind run to accepted plan hash

```python
def test_plan_review_revision_flow(tmp_path: Path) -> None:
    # 1. Create an initial plan
    # 2. Revise the plan to create version 2
    # 3. Compare the two revisions
    # 4. User accepts version 2
    # 5. Bind a run to the accepted plan hash
    # 6. Verify that run execution checks the hash
    # 7. Verify that modified plan is rejected
```

---

## Open Questions

1. **Plan Format:** Should plans be stored as JSON, Markdown, or both?
   - **Decision:** JSON for machine readability, generate Markdown on demand

2. **Plan Deletion:** Should old plan revisions be deletable?
   - **Decision:** Yes, but keep at least the latest version

3. **Plan Sharing:** Should plans be shareable across workspaces?
   - **Decision:** Out of scope for MVP, plans are workspace-local

4. **Plan Templates:** Should we support plan templates for common tasks?
   - **Decision:** Out of scope for MVP, future enhancement

---

## Dependencies

### Existing Components
- `teaagent/plan_mode.py` - Plan content structure
- `teaagent/audit.py` - Audit log for plan binding events
- `teaagent/cli/` - CLI command integration

### New Components
- `teaagent/plan_storage.py` - New module for plan storage and versioning
- `teaagent/plan_diff.py` - New module for plan comparison
- `teaagent/plan_binder.py` - New module for run-to-plan binding
- `tests/test_plan_storage.py` - Unit tests
- `tests/test_plan_versioning.py` - Unit tests
- `tests/test_plan_diff.py` - Unit tests
- `tests/test_plan_binder.py` - Unit tests
- `tests/acceptance/test_plan_review_revision_flow.py` - Acceptance test

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Hash collisions | Very Low | Critical | Use SHA-256, collision probability negligible |
| Plan storage corruption | Low | Medium | Add validation on load, backup mechanism |
| Diff algorithm inaccuracy | Medium | Low | Use well-tested difflib, manual review option |
| Performance on large plans | Low | Low | Cache diffs, limit plan size |
| Plan binding bypass | Low | High | Enforce in runner, audit all attempts |

---

## Success Metrics

1. **Integrity:** 100% of plan modifications are detected by hash verification
2. **Usability:** Plan diff is understandable by developers 90%+ of the time
3. **Adoption:** Users use plan binding 80%+ of the time when available
4. **Performance:** Plan diff completes within 2 seconds for typical plans

---

**Spec Author:** Devin AI
**Created:** 2026-05-31
**Status:** Draft - Ready for review
