"""Tests for delta update mechanism (TASK-H6-003-02)."""

import pytest

from teaagent.update.delta import (
    Delta,
    DeltaApplier,
    DeltaGenerator,
    DeltaManager,
    DeltaMetadata,
    DeltaType,
)


def test_delta_metadata_to_dict_and_from_dict():
    """Test serialization."""
    metadata = DeltaMetadata(
        from_version='0.1.0',
        to_version='0.2.0',
        delta_type=DeltaType.FILE,
        size_bytes=1024,
        checksum='abc123',
    )

    data = metadata.to_dict()
    restored = DeltaMetadata.from_dict(data)

    assert restored.from_version == metadata.from_version
    assert restored.to_version == metadata.to_version
    assert restored.delta_type == metadata.delta_type


def test_delta_to_dict_and_from_dict():
    """Test serialization."""
    metadata = DeltaMetadata(
        from_version='0.1.0',
        to_version='0.2.0',
        delta_type=DeltaType.FILE,
    )
    delta = Delta(
        metadata=metadata,
        delta_data=b'test data',
        verification_hash='hash123',
    )

    data = delta.to_dict()
    restored = Delta.from_dict(data)

    assert restored.metadata.from_version == delta.metadata.from_version
    assert restored.delta_data == delta.delta_data


@pytest.fixture
def delta_generator():
    """Fixture for DeltaGenerator."""
    return DeltaGenerator()


def test_generate_file_delta(delta_generator):
    """Test generating file delta."""
    old_files = {
        'file1.py': b'old content',
        'file2.py': b'unchanged',
    }
    new_files = {
        'file1.py': b'new content',
        'file2.py': b'unchanged',
        'file3.py': b'new file',
    }

    delta = delta_generator.generate_file_delta(old_files, new_files)

    assert delta.metadata.delta_type == DeltaType.FILE
    assert len(delta.delta_data) > 0
    assert delta.metadata.checksum is not None


def test_generate_binary_delta(delta_generator):
    """Test generating binary delta."""
    old_binary = b'old binary data'
    new_binary = b'new binary data'

    delta = delta_generator.generate_binary_delta(old_binary, new_binary)

    assert delta.metadata.delta_type == DeltaType.BINARY
    assert delta.delta_data == new_binary


def test_calculate_delta_size(delta_generator):
    """Test calculating delta size."""
    old_files = {
        'file1.py': b'old content',
        'file2.py': b'unchanged',
    }
    new_files = {
        'file1.py': b'new content',
        'file2.py': b'unchanged',
    }

    size = delta_generator.calculate_delta_size(old_files, new_files)

    assert size > 0


@pytest.fixture
def delta_applier():
    """Fixture for DeltaApplier."""
    return DeltaApplier()


def test_apply_file_delta(delta_applier):
    """Test applying file delta."""
    current_files = {
        'file1.py': b'old content',
        'file2.py': b'unchanged',
    }

    # Create delta
    generator = DeltaGenerator()
    new_files = {
        'file1.py': b'new content',
        'file2.py': b'unchanged',
        'file3.py': b'new file',
    }
    delta = generator.generate_file_delta(current_files, new_files)

    # Apply delta
    updated_files = delta_applier.apply_file_delta(current_files, delta)

    assert updated_files['file1.py'] == b'new content'
    assert 'file3.py' in updated_files


def test_apply_binary_delta(delta_applier):
    """Test applying binary delta."""
    current_binary = b'old binary data'

    # Create delta
    generator = DeltaGenerator()
    new_binary = b'new binary data'
    delta = generator.generate_binary_delta(current_binary, new_binary)

    # Apply delta
    updated_binary = delta_applier.apply_binary_delta(current_binary, delta)

    assert updated_binary == new_binary


def test_verify_delta_checksum(delta_applier):
    """Test verifying delta checksum."""
    delta = Delta(
        metadata=DeltaMetadata(
            from_version='0.1.0',
            to_version='0.2.0',
            delta_type=DeltaType.FILE,
            checksum='',  # Will be calculated
        ),
        delta_data=b'test data',
    )

    # Calculate checksum
    import hashlib

    delta.metadata.checksum = hashlib.sha256(delta.delta_data).hexdigest()

    # Verify
    result = delta_applier.verify_delta_checksum(delta)
    assert result is True


def test_verify_delta_integrity(delta_applier):
    """Test verifying delta integrity."""
    delta = Delta(
        metadata=DeltaMetadata(
            from_version='0.1.0',
            to_version='0.2.0',
            delta_type=DeltaType.FILE,
        ),
        delta_data=b'test data',
        verification_hash='hash123',
    )

    result = delta_applier.verify_delta_integrity(delta, 'hash123')
    assert result is True

    result = delta_applier.verify_delta_integrity(delta, 'wrong_hash')
    assert result is False


@pytest.fixture
def delta_manager():
    """Fixture for DeltaManager."""
    return DeltaManager()


def test_create_delta_file(delta_manager):
    """Test creating file delta."""
    old_files = {
        'file1.py': b'old content',
    }
    new_files = {
        'file1.py': b'new content',
    }

    delta = delta_manager.create_delta(
        '0.1.0',
        '0.2.0',
        old_files,
        new_files,
        DeltaType.FILE,
    )

    assert delta.metadata.from_version == '0.1.0'
    assert delta.metadata.to_version == '0.2.0'
    assert delta.metadata.delta_type == DeltaType.FILE


def test_create_delta_binary(delta_manager):
    """Test creating binary delta."""
    old_files = {
        'file1.py': b'old content',
    }
    new_files = {
        'file1.py': b'new content',
    }

    delta = delta_manager.create_delta(
        '0.1.0',
        '0.2.0',
        old_files,
        new_files,
        DeltaType.BINARY,
    )

    assert delta.metadata.delta_type == DeltaType.BINARY


def test_apply_delta(delta_manager):
    """Test applying delta through manager."""
    current_files = {
        'file1.py': b'old content',
    }
    new_files = {
        'file1.py': b'new content',
    }

    # Create delta
    delta = delta_manager.create_delta(
        '0.1.0',
        '0.2.0',
        current_files,
        new_files,
        DeltaType.FILE,
    )

    # Apply delta
    updated_files = delta_manager.apply_delta(current_files, delta)

    assert updated_files['file1.py'] == b'new content'


def test_calculate_savings(delta_manager):
    """Test calculating space savings."""
    old_files = {
        'file1.py': b'old content' * 100,
        'file2.py': b'unchanged' * 100,
        'file3.py': b'large file' * 1000,  # Large unchanged file
        'file4.py': b'another large' * 1000,  # Another large unchanged file
    }
    new_files = {
        'file1.py': b'new content' * 100,
        'file2.py': b'unchanged' * 100,
        'file3.py': b'large file' * 1000,  # Still unchanged
        'file4.py': b'another large' * 1000,  # Still unchanged
    }

    savings = delta_manager.calculate_savings(old_files, new_files)

    assert 'old_size_bytes' in savings
    assert 'new_size_bytes' in savings
    assert 'delta_size_bytes' in savings
    assert 'savings_bytes' in savings
    assert 'savings_percentage' in savings
    # With many large unchanged files, delta should be much smaller
    assert savings['savings_percentage'] > 0
