"""Failure card data model and storage for learning from past mistakes.

This module provides:
- FailureCard dataclass for structuring failure information
- Storage operations for failure cards in .teaagent/memory/failures.json
- Error handling for corrupted or missing storage files
- Automated invalidation rules for memory hygiene (Decision 3)
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Optional

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 30 * 86400
VALID_CONFIDENCE = frozenset({'low', 'medium', 'high'})
VALID_WARNING_BEHAVIOR = frozenset({'info', 'warning', 'block'})

# Common stopwords to filter out in failure-card matching to avoid false positives
# from unrelated tasks that share common words
STOPWORDS = frozenset({
    'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
    'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
    'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'can',
    'it', 'its', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she',
    'we', 'they', 'what', 'which', 'who', 'whom', 'when', 'where', 'why',
    'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other',
    'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so',
    'than', 'too', 'very', 'just', 'also', 'now', 'then', 'here', 'there',
    'use', 'using', 'make', 'making', 'get', 'getting', 'add', 'adding',
    'fix', 'fixing', 'update', 'updating', 'change', 'changing', 'create',
    'creating', 'implement', 'implementing', 'write', 'writing', 'test',
    'testing', 'run', 'running', 'build', 'building', 'check', 'checking',
    'ensure', 'ensuring', 'handle', 'handling', 'support', 'supporting',
    'need', 'needed', 'want', 'wanted', 'try', 'trying', 'able', 'unable',
    'new', 'old', 'first', 'last', 'next', 'previous', 'before', 'after',
    'during', 'while', 'until', 'since', 'through', 'without', 'within',
    'about', 'into', 'over', 'under', 'again', 'further', 'once', 'here',
    'there', 'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each',
    'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
    'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'also',
})


def _extract_significant_words(text: str) -> set[str]:
    """Extract significant words from text, filtering stopwords and short tokens.

    Args:
        text: The text to extract words from

    Returns:
        Set of significant words (lowercase, non-stopwords, length >= 3)
    """
    # Normalize: lowercase and extract alphanumeric words
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    # Filter stopwords
    return set(word for word in words if word not in STOPWORDS)


@dataclass
class AutoInvalidationRule:
    """Configuration for automated failure card invalidation."""

    trigger: (
        str  # 'file_signature_change', 'test_refactor', 'dependency_version_change'
    )
    confidence: str  # 'high', 'medium', 'low'
    action: str  # 'invalidate', 'warn', 'block'
    paths: Optional[list[str]] = None  # Optional path filters
    enabled: bool = True


@dataclass
class MemoryAutoInvalidationConfig:
    """Configuration for automated memory invalidation."""

    rules: list[AutoInvalidationRule]
    enabled: bool = True

    @classmethod
    def default(cls) -> 'MemoryAutoInvalidationConfig':
        """Create default conservative invalidation rules."""
        return cls(
            rules=[
                AutoInvalidationRule(
                    trigger='file_signature_change',
                    confidence='high',
                    action='invalidate',
                    enabled=True,
                ),
                AutoInvalidationRule(
                    trigger='test_refactor',
                    confidence='medium',
                    action='warn',
                    enabled=True,
                ),
                AutoInvalidationRule(
                    trigger='dependency_version_change',
                    confidence='medium',
                    action='warn',
                    enabled=True,
                ),
            ],
            enabled=True,
        )

    @classmethod
    def from_workspace_config(cls, root: Path) -> 'MemoryAutoInvalidationConfig':
        """Load configuration from workspace .teaagent/config.json if present."""
        config_path = root / '.teaagent' / 'config.json'
        if not config_path.exists():
            return cls.default()

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                memory_config = data.get('memory', {})
                auto_invalidation = memory_config.get('auto_invalidation', {})

                if not auto_invalidation.get('enabled', True):
                    return cls(enabled=False, rules=[])

                rules_data = auto_invalidation.get('custom_rules', [])
                rules = []
                for rule_data in rules_data:
                    rule = AutoInvalidationRule(
                        trigger=rule_data.get('trigger', ''),
                        confidence=rule_data.get('confidence', 'medium'),
                        action=rule_data.get('action', 'warn'),
                        paths=rule_data.get('paths'),
                        enabled=rule_data.get('enabled', True),
                    )
                    rules.append(rule)

                return cls(rules=rules, enabled=True)
        except (OSError, json.JSONDecodeError):
            return cls.default()


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
    confidence: str = 'low'
    expires_at: Optional[float] = None
    invalidated: bool = False
    invalidation_reason: Optional[str] = None
    warning_behavior: str = 'warning'
    reviewer_type: str = 'auto'
    evidence_command: Optional[str] = None
    evidence_exit_code: Optional[int] = None

    DEFAULT_TTL_SECONDS: ClassVar[int] = DEFAULT_TTL_SECONDS

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
        *,
        confidence: str = 'low',
        ttl_seconds: Optional[int] = DEFAULT_TTL_SECONDS,
        warning_behavior: str = 'warning',
        reviewer_type: str = 'auto',
        evidence_command: Optional[str] = None,
        evidence_exit_code: Optional[int] = None,
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
            confidence=confidence if confidence in VALID_CONFIDENCE else 'low',
            expires_at=(
                datetime.now().timestamp() + ttl_seconds
                if ttl_seconds is not None and ttl_seconds > 0
                else None
            ),
            warning_behavior=(
                warning_behavior
                if warning_behavior in VALID_WARNING_BEHAVIOR
                else 'warning'
            ),
            reviewer_type=reviewer_type,
            evidence_command=evidence_command,
            evidence_exit_code=evidence_exit_code,
        )

    def is_active(self, *, now: Optional[float] = None) -> bool:
        if self.invalidated:
            return False
        current = now if now is not None else datetime.now().timestamp()
        return not (self.expires_at is not None and current >= self.expires_at)

    def effective_behavior(self) -> str:
        if not self.is_active():
            return 'ignore'
        if self.reviewer_type != 'human':
            return 'warning'
        if self.confidence == 'high' and self.warning_behavior == 'block':
            return 'block'
        if self.warning_behavior in VALID_WARNING_BEHAVIOR:
            return self.warning_behavior
        return 'warning'

    def to_dict(self) -> dict:
        """Convert failure card to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'FailureCard':
        known = {item.name for item in fields(cls)}
        filtered = {key: value for key, value in data.items() if key in known}
        return cls(**filtered)


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
            logger.warning('Failed to read failure cards: %s', exc)
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
            logger.warning('Failed to write failure cards: %s', exc)

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

    def list_active(self) -> list[FailureCard]:
        return [card for card in self.list_all() if card.is_active()]

    def invalidate(self, card_id: str, *, reason: str) -> bool:
        cards = self._read_cards()
        updated = False
        for item in cards:
            if item.get('id') != card_id:
                continue
            item['invalidated'] = True
            item['invalidation_reason'] = reason
            updated = True
            break
        if updated:
            self._write_cards(cards)
        return updated

    def prune_expired(self) -> int:
        cards = self._read_cards()
        kept: list[dict] = []
        removed = 0
        for item in cards:
            card = FailureCard.from_dict(item)
            if card.is_active():
                kept.append(item)
            else:
                removed += 1
        if removed:
            self._write_cards(kept)
        return removed

    def clear_all(self) -> None:
        """Clear all failure cards from storage."""
        self._write_cards([])

    def clear_by_id(self, card_id: str) -> bool:
        """Clear a specific failure card by ID.

        Args:
            card_id: The ID of the failure card to clear

        Returns:
            True if the card was found and cleared, False otherwise
        """
        cards = self._read_cards()
        original_count = len(cards)
        cards = [item for item in cards if item.get('id') != card_id]
        if len(cards) < original_count:
            self._write_cards(cards)
            return True
        return False

    def _compute_file_signature(self, file_path: str) -> Optional[str]:
        """Compute SHA256 signature of a file for change detection."""
        try:
            full_path = self.root / file_path
            if not full_path.exists():
                return None
            with open(full_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except (OSError, IOError):
            return None

    def apply_auto_invalidation(
        self, config: Optional[MemoryAutoInvalidationConfig] = None
    ) -> dict[str, int]:
        """Apply automated invalidation rules based on file system state.

        Args:
            config: Auto-invalidation configuration. Uses workspace defaults if None.

        Returns:
            Dictionary with counts of invalidations by trigger type.
        """
        if config is None:
            config = MemoryAutoInvalidationConfig.from_workspace_config(self.root)

        if not config.enabled:
            return {}

        cards = self._read_cards()
        invalidation_counts: dict[str, int] = {}
        updated = False

        for item in cards:
            card = FailureCard.from_dict(item)
            if not card.is_active():
                continue

            for rule in config.rules:
                if not rule.enabled:
                    continue

                # Check path filters if specified
                if (
                    rule.paths
                    and card.file_path
                    and not any(card.file_path.startswith(path) for path in rule.paths)
                ):
                    continue

                # Apply rule based on trigger
                if rule.trigger == 'file_signature_change' and card.file_path:
                    current_sig = self._compute_file_signature(card.file_path)
                    if current_sig is None:
                        continue  # File deleted or inaccessible

                    # If signature changed, invalidate
                    stored_sig = item.get('file_signature')
                    if stored_sig and stored_sig != current_sig:
                        item['invalidated'] = True
                        item['invalidation_reason'] = (
                            f'File signature changed (rule: {rule.trigger})'
                        )
                        invalidation_counts[rule.trigger] = (
                            invalidation_counts.get(rule.trigger, 0) + 1
                        )
                        updated = True
                    elif not stored_sig:
                        # Store current signature for future comparison
                        item['file_signature'] = current_sig
                        updated = True

                elif rule.trigger == 'test_refactor':
                    # Check if any test files in context have changed
                    for test_file in card.context_files:
                        if 'test' in test_file.lower():
                            current_sig = self._compute_file_signature(test_file)
                            if current_sig is None:
                                continue

                            test_sig_key = f'test_signature_{test_file}'
                            stored_sig = item.get(test_sig_key)
                            if stored_sig and stored_sig != current_sig:
                                if rule.action == 'invalidate':
                                    item['invalidated'] = True
                                    item['invalidation_reason'] = (
                                        f'Test file {test_file} changed (rule: {rule.trigger})'
                                    )
                                elif rule.action == 'warn':
                                    item['warning_behavior'] = 'warning'
                                    item['invalidation_reason'] = (
                                        f'Test file {test_file} changed - review recommended'
                                    )
                                invalidation_counts[rule.trigger] = (
                                    invalidation_counts.get(rule.trigger, 0) + 1
                                )
                                updated = True
                            elif not stored_sig:
                                item[test_sig_key] = current_sig
                                updated = True

        if updated:
            self._write_cards(cards)

        return invalidation_counts

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
        all_cards = self.list_active()
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

            # Match by keywords in task description (with stopword filtering)
            task_words = _extract_significant_words(task_description)
            card_words = _extract_significant_words(card.task_description)

            # Calculate keyword overlap (only significant words)
            common_words = task_words & card_words
            if common_words:
                # Require at least 2 significant words in common to avoid false positives
                if len(common_words) >= 2:
                    score += len(common_words) * 2  # Weight significant matches higher

            # Append to scored cards if score > 0
            if score > 0:
                scored_cards.append((card, score))

        # Sort by score (descending) and timestamp (descending)
        scored_cards.sort(key=lambda c: (c[1], c[0].timestamp), reverse=True)

        # Return top N cards
        return [card for card, score in scored_cards[:limit] if score > 0]
