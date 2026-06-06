"""Plan Storage module for persistent plan management.

This module provides tools to store, retrieve, and manage plan artifacts
with versioning and hash-based integrity verification.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.audit import secure_audit_dir, secure_audit_file
from teaagent.storage import atomic_write_text

logger = logging.getLogger(__name__)


@dataclass
class PlanDiff:
    """Difference between two plan revisions."""

    plan_a_id: str
    plan_b_id: str
    added_steps: list[dict[str, Any]]
    removed_steps: list[dict[str, Any]]
    modified_steps: list[tuple[dict[str, Any], dict[str, Any]]]
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


class PlanVersioner:
    """Manages plan versioning and revision history."""

    def __init__(self, storage: PlanStorage):
        self._storage = storage

    def create(self, content: PlanContent, created_by: str = 'user') -> PlanArtifact:
        """Create a new plan (version 1).

        Args:
            content: Plan content
            created_by: Creator identifier

        Returns:
            PlanArtifact with metadata
        """
        metadata = PlanMetadata(
            id=uuid4().hex,
            version=1,
            parent_id=None,
            created_at=datetime.now(),
            created_by=created_by,
            title=content.title,
            content_hash='',
            storage_path=Path(''),
        )

        plan = PlanArtifact(metadata=metadata, content=content)
        self._storage.save(plan)

        logger.info(f'Created new plan {metadata.id} version 1')

        return plan

    def revise(
        self, parent_id: str, new_content: PlanContent, created_by: str = 'user'
    ) -> PlanArtifact:
        """Create a new revision of an existing plan.

        Args:
            parent_id: UUID of parent plan
            new_content: New plan content
            created_by: Creator identifier

        Returns:
            PlanArtifact with incremented version

        Raises:
            FileNotFoundError: If parent plan does not exist
        """
        # Load parent plan
        parent_plan = self._storage.load(parent_id)

        # Create new metadata with incremented version
        metadata = PlanMetadata(
            id=uuid4().hex,
            version=parent_plan.metadata.version + 1,
            parent_id=parent_id,
            created_at=datetime.now(),
            created_by=created_by,
            title=new_content.title,
            content_hash='',
            storage_path=Path(''),
        )

        plan = PlanArtifact(metadata=metadata, content=new_content)
        self._storage.save(plan)

        logger.info(
            f'Created revision {metadata.version} of plan {parent_id} as {metadata.id}'
        )

        return plan

    def get_history(self, plan_id: str) -> list[PlanArtifact]:
        """Get revision history for a plan.

        Args:
            plan_id: Plan UUID (any version)

        Returns:
            List of PlanArtifact in version order
        """
        # Start with the given plan
        history = []

        try:
            current = self._storage.load(plan_id)
        except FileNotFoundError:
            return []

        # Walk up the parent chain
        while current:
            history.append(current)
            parent_id = current.metadata.parent_id
            if parent_id is None:
                break
            try:
                current = self._storage.load(parent_id)
            except FileNotFoundError:
                break

        # Reverse to get chronological order
        history.reverse()

        return history

    def get_latest(self, plan_id: str) -> PlanArtifact:
        """Get the latest revision of a plan.

        Args:
            plan_id: Plan UUID (any version)

        Returns:
            Latest PlanArtifact

        Raises:
            FileNotFoundError: If plan does not exist
        """
        # Get all revisions and return the one with highest version
        all_revisions = self.get_all_revisions(plan_id)
        if not all_revisions:
            raise FileNotFoundError(f'No revisions found for plan {plan_id}')

        # Sort by version descending and return first
        all_revisions.sort(key=lambda p: p.metadata.version, reverse=True)
        return all_revisions[0]

    def get_all_revisions(self, plan_id: str) -> list[PlanArtifact]:
        """Get all revisions of a plan (including branches).

        This is different from get_history which only follows the parent chain.
        This method finds all plans that share the same root.

        Args:
            plan_id: Plan UUID

        Returns:
            List of all PlanArtifact with the same root
        """
        # Get the root plan
        history = self.get_history(plan_id)
        if not history:
            return []

        root_id = history[0].metadata.id

        # Find all plans with this root or that have this root in their ancestry
        all_plans = self._storage.list()
        related_plans = []

        for plan_metadata in all_plans:
            # Check if this plan is the root or has the root in its ancestry
            if plan_metadata.id == root_id:
                related_plans.append(self._storage.load(plan_metadata.id))
            else:
                # Check ancestry
                plan_history = self.get_history(plan_metadata.id)
                if plan_history and plan_history[0].metadata.id == root_id:
                    related_plans.append(self._storage.load(plan_metadata.id))

        # Sort by version
        related_plans.sort(key=lambda p: p.metadata.version)

        return related_plans


class PlanDiffer:
    """Compares two plan revisions and generates diffs."""

    def __init__(self, storage: PlanStorage):
        self._storage = storage

    def diff(self, plan_a_id: str, plan_b_id: str) -> PlanDiff:
        """Compare two plan revisions.

        Args:
            plan_a_id: UUID of first plan
            plan_b_id: UUID of second plan

        Returns:
            PlanDiff with differences
        """
        plan_a = self._storage.load(plan_a_id)
        plan_b = self._storage.load(plan_b_id)

        # Compare steps
        added_steps, removed_steps, modified_steps = self._diff_steps(
            plan_a.content.steps, plan_b.content.steps
        )

        # Compare affected files
        changed_files = self._diff_files(
            plan_a.content.affected_files, plan_b.content.affected_files
        )

        # Generate summary
        summary = self._generate_summary(
            plan_a, plan_b, added_steps, removed_steps, modified_steps, changed_files
        )

        return PlanDiff(
            plan_a_id=plan_a_id,
            plan_b_id=plan_b_id,
            added_steps=added_steps,
            removed_steps=removed_steps,
            modified_steps=modified_steps,
            changed_files=changed_files,
            summary=summary,
        )

    def compare(self, plan_a_id: str, plan_b_id: str) -> dict[str, Any]:
        """Compare two plans and return structured comparison.

        Args:
            plan_a_id: UUID of first plan
            plan_b_id: UUID of second plan

        Returns:
            Dictionary with comparison data
        """
        diff = self.diff(plan_a_id, plan_b_id)

        return {
            'plan_a_id': diff.plan_a_id,
            'plan_b_id': diff.plan_b_id,
            'added_steps': diff.added_steps,
            'removed_steps': diff.removed_steps,
            'modified_steps': [
                {'old': old, 'new': new} for old, new in diff.modified_steps
            ],
            'changed_files': list(diff.changed_files),
            'summary': diff.summary,
        }

    def format(self, diff: PlanDiff, format_type: str = 'markdown') -> str:
        """Format diff for display.

        Args:
            diff: PlanDiff to format
            format_type: Format type ("markdown" or "json")

        Returns:
            Formatted string
        """
        if format_type == 'markdown':
            return self._format_markdown(diff)
        elif format_type == 'json':
            import json

            return json.dumps(self.compare(diff.plan_a_id, diff.plan_b_id), indent=2)
        else:
            raise ValueError(f'Unknown format type: {format_type}')

    def _diff_steps(
        self, steps_a: list[dict[str, Any]], steps_b: list[dict[str, Any]]
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[tuple[dict[str, Any], dict[str, Any]]],
    ]:
        """Compare step lists."""
        added = []
        removed = []
        modified = []

        # Simple comparison by description
        descriptions_a = {step['description']: step for step in steps_a}
        descriptions_b = {step['description']: step for step in steps_b}

        # Find added steps
        for desc, step in descriptions_b.items():
            if desc not in descriptions_a:
                added.append(step)

        # Find removed steps
        for desc, step in descriptions_a.items():
            if desc not in descriptions_b:
                removed.append(step)

        # Find modified steps
        for desc in descriptions_a:
            if desc in descriptions_b:
                step_a = descriptions_a[desc]
                step_b = descriptions_b[desc]
                if step_a != step_b:
                    modified.append((step_a, step_b))

        return added, removed, modified

    def _diff_files(self, files_a: list[str], files_b: list[str]) -> set[str]:
        """Compare file lists."""
        set_a = set(files_a)
        set_b = set(files_b)

        # Return files that are in either but not both
        return set_a.symmetric_difference(set_b)

    def _generate_summary(
        self,
        plan_a: PlanArtifact,
        plan_b: PlanArtifact,
        added_steps: list[dict[str, Any]],
        removed_steps: list[dict[str, Any]],
        modified_steps: list[tuple[dict[str, Any], dict[str, Any]]],
        changed_files: set[str],
    ) -> str:
        """Generate a human-readable summary."""
        parts = []

        parts.append(
            f'Comparing plan {plan_a.metadata.id} (v{plan_a.metadata.version})'
        )
        parts.append(f'with plan {plan_b.metadata.id} (v{plan_b.metadata.version})')

        if added_steps:
            parts.append(f'Added {len(added_steps)} step(s)')
        if removed_steps:
            parts.append(f'Removed {len(removed_steps)} step(s)')
        if modified_steps:
            parts.append(f'Modified {len(modified_steps)} step(s)')
        if changed_files:
            parts.append(f'Changed {len(changed_files)} file(s)')

        if not (added_steps or removed_steps or modified_steps or changed_files):
            parts.append('No changes detected')

        return '. '.join(parts)

    def _format_markdown(self, diff: PlanDiff) -> str:
        """Format diff as Markdown."""
        lines = [
            f'# Plan Diff: {diff.plan_a_id} → {diff.plan_b_id}',
            '',
            f'**Summary:** {diff.summary}',
            '',
        ]

        if diff.added_steps:
            lines.append('## Added Steps')
            for step in diff.added_steps:
                lines.append(f'- {step["description"]}')
            lines.append('')

        if diff.removed_steps:
            lines.append('## Removed Steps')
            for step in diff.removed_steps:
                lines.append(f'- {step["description"]}')
            lines.append('')

        if diff.modified_steps:
            lines.append('## Modified Steps')
            for old_step, new_step in diff.modified_steps:
                lines.append(f'- **{old_step["description"]}**')
                lines.append(f'  - Old: {old_step}')
                lines.append(f'  - New: {new_step}')
            lines.append('')

        if diff.changed_files:
            lines.append('## Changed Files')
            for file in sorted(diff.changed_files):
                lines.append(f'- {file}')
            lines.append('')

        return '\n'.join(lines)


class PlanBinder:
    """Binds run executions to specific plan hashes."""

    def __init__(self, storage: PlanStorage):
        self._storage = storage
        self._bindings: dict[str, PlanBinding] = {}  # run_id -> PlanBinding

    def bind(self, run_id: str, plan_id: str) -> PlanBinding:
        """Bind a run execution to a specific plan hash.

        Args:
            run_id: Run ID
            plan_id: Plan UUID

        Returns:
            PlanBinding with binding information

        Raises:
            FileNotFoundError: If plan does not exist
        """
        # Load plan to get hash
        plan = self._storage.load(plan_id)

        # Create binding
        binding = PlanBinding(
            run_id=run_id,
            plan_id=plan_id,
            plan_hash=plan.metadata.content_hash,
            bound_at=datetime.now(),
            verified=True,
        )

        self._bindings[run_id] = binding

        logger.info(
            f'Bound run {run_id} to plan {plan_id} with hash {plan.metadata.content_hash}'
        )

        return binding

    def verify(self, run_id: str) -> bool:
        """Verify that the plan hash matches when execution starts.

        Args:
            run_id: Run ID

        Returns:
            True if hash matches, False otherwise

        Raises:
            ValueError: If no binding exists for run_id
        """
        if run_id not in self._bindings:
            raise ValueError(f'No binding found for run {run_id}')

        binding = self._bindings[run_id]

        # Load current plan state
        try:
            plan = self._storage.load(binding.plan_id)
            current_hash = plan.metadata.content_hash
        except FileNotFoundError:
            logger.error(f'Plan {binding.plan_id} not found during verification')
            return False

        # Verify hash
        if current_hash == binding.plan_hash:
            binding.verified = True
            logger.info(f'Plan hash verified for run {run_id}')
            return True
        else:
            binding.verified = False
            logger.warning(
                f'Plan hash mismatch for run {run_id}: expected {binding.plan_hash}, got {current_hash}'
            )
            return False

    def check_hash(self, run_id: str, plan_id: str) -> bool:
        """Check if a plan's hash matches the binding.

        Args:
            run_id: Run ID
            plan_id: Plan UUID

        Returns:
            True if hash matches, False otherwise
        """
        if run_id not in self._bindings:
            return False

        binding = self._bindings[run_id]

        if binding.plan_id != plan_id:
            return False

        try:
            plan = self._storage.load(plan_id)
            return plan.metadata.content_hash == binding.plan_hash
        except FileNotFoundError:
            return False

    def get_binding(self, run_id: str) -> Optional[PlanBinding]:
        """Get the binding for a run.

        Args:
            run_id: Run ID

        Returns:
            PlanBinding if exists, None otherwise
        """
        return self._bindings.get(run_id)

    def unbind(self, run_id: str) -> None:
        """Remove a binding.

        Args:
            run_id: Run ID
        """
        if run_id in self._bindings:
            del self._bindings[run_id]
            logger.info(f'Unbound run {run_id}')


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
class PlanContent:
    """Content of a plan."""

    title: str
    goal: str
    approach: str
    steps: list[dict[str, Any]]
    affected_files: list[str]
    risks: list[str]
    acceptance_criteria: list[str]
    scope_budget: Optional[dict[str, Any]] = None


@dataclass
class PlanArtifact:
    """Complete plan artifact with metadata and content."""

    metadata: PlanMetadata
    content: PlanContent


class PlanStorage:
    """Persistent storage for plan artifacts."""

    def __init__(self, root: Path):
        self._root = Path(root) / '.teaagent' / 'plans'
        self._root.mkdir(parents=True, exist_ok=True)
        secure_audit_dir(self._root)

    def save(self, plan: PlanArtifact) -> PlanMetadata:
        """Save a plan artifact to storage.

        Args:
            plan: Plan artifact to save

        Returns:
            PlanMetadata with assigned ID and hash
        """
        # Compute content hash
        content_hash = self._compute_content_hash(plan.content)

        # Update metadata with hash
        plan.metadata.content_hash = content_hash

        # Generate storage path
        storage_path = self._root / f'{plan.metadata.id}.json'
        plan.metadata.storage_path = storage_path

        # Serialize plan
        plan_dict = self._serialize_plan(plan)

        # Write atomically
        atomic_write_text(storage_path, json.dumps(plan_dict, indent=2, default=str))
        secure_audit_file(storage_path)

        logger.info(f'Saved plan {plan.metadata.id} to {storage_path}')

        return plan.metadata

    def load(self, plan_id: str) -> PlanArtifact:
        """Load a plan artifact from storage.

        Args:
            plan_id: Plan UUID

        Returns:
            PlanArtifact

        Raises:
            FileNotFoundError: If plan does not exist
        """
        storage_path = self._root / f'{plan_id}.json'

        if not storage_path.exists():
            raise FileNotFoundError(f'Plan {plan_id} not found at {storage_path}')

        with open(storage_path, 'r', encoding='utf-8') as f:
            plan_dict = json.load(f)

        plan = self._deserialize_plan(plan_dict)

        logger.info(f'Loaded plan {plan_id} from {storage_path}')

        return plan

    def list(self) -> list[PlanMetadata]:
        """List all plans in storage.

        Returns:
            List of PlanMetadata
        """
        plans = []

        for path in self._root.glob('*.json'):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    plan_dict = json.load(f)

                metadata = self._deserialize_metadata(plan_dict['metadata'])
                plans.append(metadata)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f'Failed to load plan metadata from {path}: {e}')

        # Sort by creation time
        plans.sort(key=lambda m: m.created_at, reverse=True)

        return plans

    def delete(self, plan_id: str) -> None:
        """Delete a plan from storage.

        Args:
            plan_id: Plan UUID

        Raises:
            FileNotFoundError: If plan does not exist
        """
        storage_path = self._root / f'{plan_id}.json'

        if not storage_path.exists():
            raise FileNotFoundError(f'Plan {plan_id} not found at {storage_path}')

        storage_path.unlink()
        logger.info(f'Deleted plan {plan_id} from {storage_path}')

    def _compute_content_hash(self, content: PlanContent) -> str:
        """Compute SHA-256 hash of plan content."""
        content_str = json.dumps(
            {
                'title': content.title,
                'goal': content.goal,
                'approach': content.approach,
                'steps': content.steps,
                'affected_files': content.affected_files,
                'risks': content.risks,
                'acceptance_criteria': content.acceptance_criteria,
            },
            sort_keys=True,
        )
        return 'sha256:' + hashlib.sha256(content_str.encode()).hexdigest()

    def _serialize_plan(self, plan: PlanArtifact) -> dict[str, Any]:
        """Serialize plan artifact to dictionary."""
        return {
            'metadata': {
                'id': plan.metadata.id,
                'version': plan.metadata.version,
                'parent_id': plan.metadata.parent_id,
                'created_at': plan.metadata.created_at.isoformat(),
                'created_by': plan.metadata.created_by,
                'title': plan.metadata.title,
                'content_hash': plan.metadata.content_hash,
                'storage_path': str(plan.metadata.storage_path),
            },
            'content': {
                'title': plan.content.title,
                'goal': plan.content.goal,
                'approach': plan.content.approach,
                'steps': plan.content.steps,
                'affected_files': plan.content.affected_files,
                'risks': plan.content.risks,
                'acceptance_criteria': plan.content.acceptance_criteria,
            },
        }

    def _deserialize_plan(self, plan_dict: dict[str, Any]) -> PlanArtifact:
        """Deserialize plan artifact from dictionary."""
        return PlanArtifact(
            metadata=self._deserialize_metadata(plan_dict['metadata']),
            content=self._deserialize_content(plan_dict['content']),
        )

    def _deserialize_metadata(self, metadata_dict: dict[str, Any]) -> PlanMetadata:
        """Deserialize metadata from dictionary."""
        return PlanMetadata(
            id=metadata_dict['id'],
            version=metadata_dict['version'],
            parent_id=metadata_dict.get('parent_id'),
            created_at=datetime.fromisoformat(metadata_dict['created_at']),
            created_by=metadata_dict['created_by'],
            title=metadata_dict['title'],
            content_hash=metadata_dict['content_hash'],
            storage_path=Path(metadata_dict['storage_path']),
        )

    def _deserialize_content(self, content_dict: dict[str, Any]) -> PlanContent:
        """Deserialize content from dictionary."""
        return PlanContent(
            title=content_dict['title'],
            goal=content_dict['goal'],
            approach=content_dict['approach'],
            steps=content_dict['steps'],
            affected_files=content_dict['affected_files'],
            risks=content_dict['risks'],
            acceptance_criteria=content_dict['acceptance_criteria'],
        )
