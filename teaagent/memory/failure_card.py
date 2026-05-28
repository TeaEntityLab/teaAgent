"""Failure card data model and storage for learning from past mistakes.

This module provides:
- FailureCard dataclass for structuring failure information
- Storage operations for failure cards in .teaagent/memory/failures.json
- Error handling for corrupted or missing storage files
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class FailureCard:
    """A failure card capturing information about a task failure.

    Attributes:
        id: Unique identifier for the failure card
        run_id: The run ID of the failed task
        timestamp: When the failure occurred (Unix timestamp)
        error_type: Type of error (e.g., TypeError, ImportError)
        file_path: Path to the file where the error occurred
        line_number: Line number where the error occurred (if available)
        error_message: The error message
        task_description: Description of the task that failed
        context_files: List of files involved in the task context
    """

    id: str
    run_id: str
    timestamp: float
    error_type: str
    file_path: str
    line_number: Optional[int]
    error_message: str
    task_description: str
    context_files: list[str]

    @classmethod
    def create(
        cls,
        run_id: str,
        error_type: str,
        file_path: str,
        error_message: str,
        task_description: str,
        context_files: list[str],
        line_number: Optional[int] = None,
    ) -> 'FailureCard':
        """Create a new failure card with generated ID and timestamp.

        Args:
            run_id: The run ID of the failed task
            error_type: Type of error
            file_path: Path to the file where the error occurred
            error_message: The error message
            task_description: Description of the task that failed
            context_files: List of files involved in the task context
            line_number: Line number where the error occurred (if available)

        Returns:
            A new FailureCard instance
        """
        return cls(
            id=str(uuid.uuid4())[:8],
            run_id=run_id,
            timestamp=datetime.now().timestamp(),
            error_type=error_type,
            file_path=file_path,
            line_number=line_number,
            error_message=error_message,
            task_description=task_description,
            context_files=context_files,
        )

    def to_dict(self) -> dict:
        """Convert failure card to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'FailureCard':
        """Create failure card from dictionary.

        Args:
            data: Dictionary containing failure card data

        Returns:
            A FailureCard instance
        """
        return cls(**data)


class FailureCardStorage:
    """Storage for failure cards in .teaagent/memory/failures.json."""

    def __init__(self, root: Path) -> None:
        """Initialize failure card storage.

        Args:
            root: The workspace root directory
        """
        self.root = Path(root).resolve()
        self.tea_dir = self.root / '.teaagent'
        self.memory_dir = self.tea_dir / 'memory'
        self.storage_file = self.memory_dir / 'failures.json'

        # Ensure directories exist
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def _read_cards(self) -> list[dict]:
        """Read failure cards from storage.

        Returns:
            List of failure card dictionaries. Returns empty list if file
            doesn't exist or is corrupted.
        """
        if not self.storage_file.exists():
            return []

        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, list):
                    return []
                return data
        except (OSError, json.JSONDecodeError) as exc:
            # Log warning but don't crash
            import sys

            print(
                f'[TeaAgent] Warning: Failed to read failure cards: {exc}',
                file=sys.stderr,
            )
            return []

    def _write_cards(self, cards: list[dict]) -> None:
        """Write failure cards to storage.

        Args:
            cards: List of failure card dictionaries to write
        """
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(cards, f, indent=2)
        except OSError as exc:
            import sys

            print(
                f'[TeaAgent] Warning: Failed to write failure cards: {exc}',
                file=sys.stderr,
            )

    def append(self, card: FailureCard) -> None:
        """Append a failure card to storage.

        Args:
            card: The failure card to append
        """
        cards = self._read_cards()
        cards.append(card.to_dict())
        self._write_cards(cards)

    def list_all(self) -> list[FailureCard]:
        """List all failure cards.

        Returns:
            List of all FailureCard instances
        """
        cards_data = self._read_cards()
        return [FailureCard.from_dict(data) for data in cards_data]

    def clear_all(self) -> None:
        """Clear all failure cards from storage."""
        self._write_cards([])

    def clear_by_id(self, card_id: str) -> bool:
        """Clear a specific failure card by ID.

        Args:
            card_id: The ID of the failure card to clear

        Returns:
            True if card was found and removed, False otherwise
        """
        cards = self._read_cards()
        original_count = len(cards)
        cards = [card for card in cards if card.get('id') != card_id]

        if len(cards) < original_count:
            self._write_cards(cards)
            return True
        return False

    def get_by_id(self, card_id: str) -> Optional[FailureCard]:
        """Get a specific failure card by ID.

        Args:
            card_id: The ID of the failure card to retrieve

        Returns:
            The FailureCard if found, None otherwise
        """
        cards = self._read_cards()
        for card_data in cards:
            if card_data.get('id') == card_id:
                return FailureCard.from_dict(card_data)
        return None

    def find_matching(
        self,
        file_paths: list[str],
        task_description: str,
        error_type: Optional[str] = None,
        limit: int = 3,
    ) -> list[FailureCard]:
        """Find failure cards matching the given criteria.

        Matching criteria (simple heuristics):
        - Same file path (highest priority)
        - Same error type
        - Keyword similarity in task description

        Args:
            file_paths: List of file paths involved in the current task
            task_description: Description of the current task
            error_type: Optional error type to match
            limit: Maximum number of results to return

        Returns:
            List of matching FailureCard instances, sorted by timestamp (most recent first)
        """
        all_cards = self.list_all()
        scored_cards = []

        for card in all_cards:
            score = 0

            # Match by file path (highest priority)
            for fp in file_paths:
                if fp and card.file_path and fp in card.file_path:
                    score += 10
                    break

            # Match by error type
            if error_type and card.error_type == error_type:
                score += 5

            # Match by keywords in task description
            task_lower = task_description.lower()
            card_task_lower = card.task_description.lower()

            # Extract words from task descriptions
            task_words = set(task_lower.split())
            card_words = set(card_task_lower.split())

            # Calculate keyword overlap
            common_words = task_words & card_words
            if common_words:
                score += len(common_words)

            # Append to scored cards if score > 0
            if score > 0:
                scored_cards.append((card, score))

        # Sort by score (descending) and timestamp (descending)
        scored_cards.sort(key=lambda c: (c[1], c[0].timestamp), reverse=True)

        # Return top N cards
        return [card for card, score in scored_cards[:limit] if score > 0]
