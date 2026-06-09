"""Tests for delta update mechanism (TASK-H6-003-02)."""

import unittest

from teaagent.update.delta import (
    Delta,
    DeltaApplier,
    DeltaGenerator,
    DeltaManager,
    DeltaMetadata,
    DeltaType,
)


class TestDeltaMetadata(unittest.TestCase):
    """Test delta metadata."""

    def test_to_dict_and_from_dict(self):
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

        self.assertEqual(restored.from_version, metadata.from_version)
        self.assertEqual(restored.to_version, metadata.to_version)
        self.assertEqual(restored.delta_type, metadata.delta_type)


class TestDelta(unittest.TestCase):
    """Test delta object."""

    def test_to_dict_and_from_dict(self):
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

        self.assertEqual(restored.metadata.from_version, delta.metadata.from_version)
        self.assertEqual(restored.delta_data, delta.delta_data)


class TestDeltaGenerator(unittest.TestCase):
    """Test delta generator."""

    def setUp(self):
        """Set up test fixtures."""
        self.generator = DeltaGenerator()

    def test_generate_file_delta(self):
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

        delta = self.generator.generate_file_delta(old_files, new_files)

        self.assertEqual(delta.metadata.delta_type, DeltaType.FILE)
        self.assertGreater(len(delta.delta_data), 0)
        self.assertIsNotNone(delta.metadata.checksum)

    def test_generate_binary_delta(self):
        """Test generating binary delta."""
        old_binary = b'old binary data'
        new_binary = b'new binary data'

        delta = self.generator.generate_binary_delta(old_binary, new_binary)

        self.assertEqual(delta.metadata.delta_type, DeltaType.BINARY)
        self.assertEqual(delta.delta_data, new_binary)

    def test_calculate_delta_size(self):
        """Test calculating delta size."""
        old_files = {
            'file1.py': b'old content',
            'file2.py': b'unchanged',
        }
        new_files = {
            'file1.py': b'new content',
            'file2.py': b'unchanged',
        }

        size = self.generator.calculate_delta_size(old_files, new_files)

        self.assertGreater(size, 0)


class TestDeltaApplier(unittest.TestCase):
    """Test delta applier."""

    def setUp(self):
        """Set up test fixtures."""
        self.applier = DeltaApplier()

    def test_apply_file_delta(self):
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
        updated_files = self.applier.apply_file_delta(current_files, delta)

        self.assertEqual(updated_files['file1.py'], b'new content')
        self.assertIn('file3.py', updated_files)

    def test_apply_binary_delta(self):
        """Test applying binary delta."""
        current_binary = b'old binary data'

        # Create delta
        generator = DeltaGenerator()
        new_binary = b'new binary data'
        delta = generator.generate_binary_delta(current_binary, new_binary)

        # Apply delta
        updated_binary = self.applier.apply_binary_delta(current_binary, delta)

        self.assertEqual(updated_binary, new_binary)

    def test_verify_delta_checksum(self):
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
        result = self.applier.verify_delta_checksum(delta)
        self.assertTrue(result)

    def test_verify_delta_integrity(self):
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

        result = self.applier.verify_delta_integrity(delta, 'hash123')
        self.assertTrue(result)

        result = self.applier.verify_delta_integrity(delta, 'wrong_hash')
        self.assertFalse(result)


class TestDeltaManager(unittest.TestCase):
    """Test delta manager."""

    def setUp(self):
        """Set up test fixtures."""
        self.manager = DeltaManager()

    def test_create_delta_file(self):
        """Test creating file delta."""
        old_files = {
            'file1.py': b'old content',
        }
        new_files = {
            'file1.py': b'new content',
        }

        delta = self.manager.create_delta(
            '0.1.0',
            '0.2.0',
            old_files,
            new_files,
            DeltaType.FILE,
        )

        self.assertEqual(delta.metadata.from_version, '0.1.0')
        self.assertEqual(delta.metadata.to_version, '0.2.0')
        self.assertEqual(delta.metadata.delta_type, DeltaType.FILE)

    def test_create_delta_binary(self):
        """Test creating binary delta."""
        old_files = {
            'file1.py': b'old content',
        }
        new_files = {
            'file1.py': b'new content',
        }

        delta = self.manager.create_delta(
            '0.1.0',
            '0.2.0',
            old_files,
            new_files,
            DeltaType.BINARY,
        )

        self.assertEqual(delta.metadata.delta_type, DeltaType.BINARY)

    def test_apply_delta(self):
        """Test applying delta through manager."""
        current_files = {
            'file1.py': b'old content',
        }
        new_files = {
            'file1.py': b'new content',
        }

        # Create delta
        delta = self.manager.create_delta(
            '0.1.0',
            '0.2.0',
            current_files,
            new_files,
            DeltaType.FILE,
        )

        # Apply delta
        updated_files = self.manager.apply_delta(current_files, delta)

        self.assertEqual(updated_files['file1.py'], b'new content')

    def test_calculate_savings(self):
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

        savings = self.manager.calculate_savings(old_files, new_files)

        self.assertIn('old_size_bytes', savings)
        self.assertIn('new_size_bytes', savings)
        self.assertIn('delta_size_bytes', savings)
        self.assertIn('savings_bytes', savings)
        self.assertIn('savings_percentage', savings)
        # With many large unchanged files, delta should be much smaller
        self.assertGreater(savings['savings_percentage'], 0)


if __name__ == '__main__':
    unittest.main()
