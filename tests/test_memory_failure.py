"""Integration tests for failure experience loop features."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from teaagent.memory.failure_card import FailureCard, FailureCardStorage


class TestFailureCard:
    """Test FailureCard data model."""
    
    def test_create_failure_card(self) -> None:
        """Test creating a failure card."""
        card = FailureCard.create(
            run_id="test-run-123",
            error_type="TypeError",
            file_path="src/test.py",
            error_message="Test error message",
            task_description="Test task",
            context_files=["src/test.py"],
            line_number=42,
        )
        
        assert card.run_id == "test-run-123"
        assert card.error_type == "TypeError"
        assert card.file_path == "src/test.py"
        assert card.error_message == "Test error message"
        assert card.task_description == "Test task"
        assert card.context_files == ["src/test.py"]
        assert card.line_number == 42
        assert card.id is not None
        assert card.timestamp > 0
    
    def test_serialization(self) -> None:
        """Test failure card serialization and deserialization."""
        card = FailureCard.create(
            run_id="test-run-123",
            error_type="TypeError",
            file_path="src/test.py",
            error_message="Test error message",
            task_description="Test task",
            context_files=["src/test.py"],
        )
        
        # Serialize
        card_dict = card.to_dict()
        assert isinstance(card_dict, dict)
        assert card_dict["run_id"] == "test-run-123"
        
        # Deserialize
        restored_card = FailureCard.from_dict(card_dict)
        assert restored_card.run_id == card.run_id
        assert restored_card.error_type == card.error_type
        assert restored_card.file_path == card.file_path


class TestFailureCardStorage:
    """Test FailureCardStorage operations."""
    
    @pytest.fixture
    def temp_root(self) -> Path:
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_append_and_list(self, temp_root: Path) -> None:
        """Test appending and listing failure cards."""
        storage = FailureCardStorage(temp_root)
        
        # Append a card
        card = FailureCard.create(
            run_id="run-1",
            error_type="TypeError",
            file_path="src/test.py",
            error_message="Test error",
            task_description="Test task",
            context_files=[],
        )
        storage.append(card)
        
        # List cards
        cards = storage.list_all()
        assert len(cards) == 1
        assert cards[0].run_id == "run-1"
    
    def test_append_multiple(self, temp_root: Path) -> None:
        """Test appending multiple failure cards."""
        storage = FailureCardStorage(temp_root)
        
        # Append multiple cards
        for i in range(3):
            card = FailureCard.create(
                run_id=f"run-{i}",
                error_type="TypeError",
                file_path="src/test.py",
                error_message=f"Error {i}",
                task_description="Test task",
                context_files=[],
            )
            storage.append(card)
        
        # List cards
        cards = storage.list_all()
        assert len(cards) == 3
    
    def test_clear_all(self, temp_root: Path) -> None:
        """Test clearing all failure cards."""
        storage = FailureCardStorage(temp_root)
        
        # Add cards
        card = FailureCard.create(
            run_id="run-1",
            error_type="TypeError",
            file_path="src/test.py",
            error_message="Test error",
            task_description="Test task",
            context_files=[],
        )
        storage.append(card)
        
        # Clear all
        storage.clear_all()
        cards = storage.list_all()
        assert len(cards) == 0
    
    def test_clear_by_id(self, temp_root: Path) -> None:
        """Test clearing a specific failure card by ID."""
        storage = FailureCardStorage(temp_root)
        
        # Add cards
        card1 = FailureCard.create(
            run_id="run-1",
            error_type="TypeError",
            file_path="src/test.py",
            error_message="Error 1",
            task_description="Task 1",
            context_files=[],
        )
        card2 = FailureCard.create(
            run_id="run-2",
            error_type="ValueError",
            file_path="src/test2.py",
            error_message="Error 2",
            task_description="Task 2",
            context_files=[],
        )
        storage.append(card1)
        storage.append(card2)
        
        # Clear by ID
        result = storage.clear_by_id(card1.id)
        assert result is True
        
        cards = storage.list_all()
        assert len(cards) == 1
        assert cards[0].run_id == "run-2"
    
    def test_get_by_id(self, temp_root: Path) -> None:
        """Test getting a specific failure card by ID."""
        storage = FailureCardStorage(temp_root)
        
        # Add a card
        card = FailureCard.create(
            run_id="run-1",
            error_type="TypeError",
            file_path="src/test.py",
            error_message="Test error",
            task_description="Test task",
            context_files=[],
        )
        storage.append(card)
        
        # Get by ID
        retrieved = storage.get_by_id(card.id)
        assert retrieved is not None
        assert retrieved.run_id == "run-1"
        
        # Get non-existent ID
        non_existent = storage.get_by_id("non-existent")
        assert non_existent is None
    
    def test_missing_file(self, temp_root: Path) -> None:
        """Test reading from missing storage file."""
        storage = FailureCardStorage(temp_root)
        cards = storage.list_all()
        assert cards == []
    
    def test_corrupted_file(self, temp_root: Path) -> None:
        """Test reading from corrupted storage file."""
        storage = FailureCardStorage(temp_root)
        
        # Write corrupted JSON
        storage_file = storage.storage_file
        storage_file.write_text("invalid json")
        
        # Should return empty list
        cards = storage.list_all()
        assert cards == []


class TestFailureCardMatching:
    """Test failure card matching logic."""
    
    @pytest.fixture
    def temp_root(self) -> Path:
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_match_by_file_path(self, temp_root: Path) -> None:
        """Test matching by file path."""
        storage = FailureCardStorage(temp_root)
        
        # Add a card
        card = FailureCard.create(
            run_id="run-1",
            error_type="TypeError",
            file_path="src/auth.py",
            error_message="Test error",
            task_description="Fix auth module",
            context_files=[],
        )
        storage.append(card)
        
        # Match by file path
        matching = storage.find_matching(
            file_paths=["src/auth.py"],
            task_description="Update auth module",
        )
        assert len(matching) == 1
        assert matching[0].run_id == "run-1"
    
    def test_match_by_error_type(self, temp_root: Path) -> None:
        """Test matching by error type."""
        storage = FailureCardStorage(temp_root)
        
        # Add a card
        card = FailureCard.create(
            run_id="run-1",
            error_type="ImportError",
            file_path="src/test.py",
            error_message="Cannot import X",
            task_description="Test task",
            context_files=[],
        )
        storage.append(card)
        
        # Match by error type
        matching = storage.find_matching(
            file_paths=[],
            task_description="New task",
            error_type="ImportError",
        )
        assert len(matching) == 1
        assert matching[0].error_type == "ImportError"
    
    def test_match_by_keywords(self, temp_root: Path) -> None:
        """Test matching by task description keywords."""
        storage = FailureCardStorage(temp_root)
        
        # Add a card
        card = FailureCard.create(
            run_id="run-1",
            error_type="TypeError",
            file_path="src/test.py",
            error_message="Test error",
            task_description="Add OAuth2 support to auth module",
            context_files=[],
        )
        storage.append(card)
        
        # Match by keywords
        matching = storage.find_matching(
            file_paths=[],
            task_description="Update OAuth2 in auth",
        )
        assert len(matching) == 1
    
    def test_no_match(self, temp_root: Path) -> None:
        """Test when no cards match."""
        storage = FailureCardStorage(temp_root)
        
        # Add a card
        card = FailureCard.create(
            run_id="run-1",
            error_type="TypeError",
            file_path="src/test.py",
            error_message="Test error",
            task_description="Test task",
            context_files=[],
        )
        storage.append(card)
        
        # No match
        matching = storage.find_matching(
            file_paths=["src/other.py"],
            task_description="Completely different task",
        )
        assert len(matching) == 0
    
    def test_result_limit(self, temp_root: Path) -> None:
        """Test result limit."""
        storage = FailureCardStorage(temp_root)
        
        # Add multiple cards
        for i in range(5):
            card = FailureCard.create(
                run_id=f"run-{i}",
                error_type="TypeError",
                file_path="src/test.py",
                error_message=f"Error {i}",
                task_description="Test task",
                context_files=[],
            )
            storage.append(card)
        
        # Limit to 3
        matching = storage.find_matching(
            file_paths=["src/test.py"],
            task_description="Test task",
            limit=3,
        )
        assert len(matching) == 3
    
    def test_sorting_by_timestamp(self, temp_root: Path) -> None:
        """Test that results are sorted by timestamp (most recent first)."""
        storage = FailureCardStorage(temp_root)
        
        # Add cards with different timestamps
        import time
        card1 = FailureCard.create(
            run_id="run-1",
            error_type="TypeError",
            file_path="src/test.py",
            error_message="Error 1",
            task_description="Test task",
            context_files=[],
        )
        time.sleep(0.01)  # Small delay
        card2 = FailureCard.create(
            run_id="run-2",
            error_type="TypeError",
            file_path="src/test.py",
            error_message="Error 2",
            task_description="Test task",
            context_files=[],
        )
        storage.append(card1)
        storage.append(card2)
        
        # Most recent should be first
        matching = storage.find_matching(
            file_paths=["src/test.py"],
            task_description="Test task",
        )
        assert len(matching) == 2
        assert matching[0].run_id == "run-2"  # More recent
