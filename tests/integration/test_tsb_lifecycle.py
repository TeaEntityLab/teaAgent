"""Integration tests for TSB lifecycle workflow (publish → verify → extract)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from teaagent.tsb_format import TSBBuilder, TSBMetadata, TSBManifest, TSBVerifier


class TSBLifecycleIntegrationTests(unittest.TestCase):
    """Integration tests for complete TSB lifecycle."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.skill_path = self.temp_dir / "skill"
        self.skill_path.mkdir()
        
        # Create sample skill files
        (self.skill_path / "SKILL.md").write_text("# Test Skill\n\nA test skill for TSB integration.", encoding="utf-8")
        (self.skill_path / "main.py").write_text("def main():\n    print('Hello')\n", encoding="utf-8")
        (self.skill_path / "utils" / "helper.py").parent.mkdir(parents=True, exist_ok=True)
        (self.skill_path / "utils" / "helper.py").write_text("def helper():\n    pass\n", encoding="utf-8")
        
        # Create audit log (simple JSONL)
        self.audit_log_path = self.temp_dir / "audit.jsonl"
        audit_events = [
            {"event_id": "1", "event_type": "tool_call", "run_id": "test-run", "created_at": "2024-01-01T00:00:00Z", "payload": {"tool": "read_file", "path": "test.py"}, "prev_hash": "genesis"},
            {"event_id": "2", "event_type": "tool_call", "run_id": "test-run", "created_at": "2024-01-01T00:01:00Z", "payload": {"tool": "write_file", "path": "test.py"}, "prev_hash": "hash1"},
        ]
        audit_log_content = "\n".join(json.dumps(event) for event in audit_events)
        self.audit_log_path.write_text(audit_log_content, encoding="utf-8")
        
        # Create SSH key for signing (mock)
        self.key_path = self.temp_dir / "test_key"
        self.key_path.write_text("mock_key_content", encoding="utf-8")

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_full_tsb_lifecycle_without_signature(self) -> None:
        """Test complete TSB lifecycle: build → verify → extract without signature."""
        # Build TSB
        metadata = TSBMetadata(
            skill_name="test-skill",
            skill_version="1.0.0",
            skill_author="test-author",
            created_at="2024-01-01T00:00:00Z",
        )
        
        builder = TSBBuilder(
            skill_path=self.skill_path,
            audit_log_path=self.audit_log_path,
            author_key_path=None,  # No signature
        )
        
        output_path = self.temp_dir / "test.tsb"
        manifest = builder.build_tsb(output_path, metadata, skip_audit_verification=True)
        
        # Verify manifest structure
        self.assertIsInstance(manifest, TSBManifest)
        self.assertEqual(manifest.metadata.skill_name, "test-skill")
        self.assertEqual(manifest.metadata.tsb_version, "1.1")
        self.assertEqual(len(manifest.files), 3)  # SKILL.md, main.py, utils/helper.py
        
        # Verify TSB
        verifier = TSBVerifier(output_path)
        is_valid, message = verifier.verify(verify_signature=False, skip_audit_verification=True)
        
        self.assertTrue(is_valid, f"Verification failed: {message}")
        self.assertIn("TSB verification successful", message)
        
        # Extract skill
        extract_path = self.temp_dir / "extracted"
        verifier.extract_skill(extract_path)
        
        # Verify extracted files
        self.assertTrue((extract_path / "SKILL.md").exists())
        self.assertTrue((extract_path / "main.py").exists())
        self.assertTrue((extract_path / "utils" / "helper.py").exists())
        
        # Verify file contents
        self.assertEqual(
            (extract_path / "SKILL.md").read_text(encoding="utf-8"),
            "# Test Skill\n\nA test skill for TSB integration."
        )
        self.assertEqual(
            (extract_path / "main.py").read_text(encoding="utf-8"),
            "def main():\n    print('Hello')\n"
        )

    def test_tsb_with_path_aware_hashing(self) -> None:
        """Test that TSB v1.1 includes relative paths in hash calculation."""
        # Build TSB
        metadata = TSBMetadata(
            skill_name="test-skill",
            skill_version="1.0.0",
            skill_author="test-author",
            created_at="2024-01-01T00:00:00Z",
        )
        
        builder = TSBBuilder(
            skill_path=self.skill_path,
            audit_log_path=self.audit_log_path,
            author_key_path=None,
        )
        
        output_path = self.temp_dir / "test.tsb"
        manifest = builder.build_tsb(output_path, metadata, skip_audit_verification=True)
        
        # Rename a file and rebuild
        (self.skill_path / "main.py").rename(self.skill_path / "renamed.py")
        output_path2 = self.temp_dir / "test2.tsb"
        manifest2 = builder.build_tsb(output_path2, metadata, skip_audit_verification=True)
        
        # Hashes should be different due to path-aware hashing
        self.assertNotEqual(
            manifest.attestation.bundle_hash,
            manifest2.attestation.bundle_hash,
            "Bundle hashes should differ when file paths change"
        )

    def test_tsb_verification_with_tampered_manifest(self) -> None:
        """Test that TSB verification detects file content changes."""
        # Build TSB
        metadata = TSBMetadata(
            skill_name="test-skill",
            skill_version="1.0.0",
            skill_author="test-author",
            created_at="2024-01-01T00:00:00Z",
        )
        
        builder = TSBBuilder(
            skill_path=self.skill_path,
            audit_log_path=self.audit_log_path,
            author_key_path=None,
        )
        
        output_path = self.temp_dir / "test.tsb"
        builder.build_tsb(output_path, metadata, skip_audit_verification=True)
        
        # Tamper with the TSB by modifying a file
        import tarfile
        import io
        
        # Read the original tarball
        with tarfile.open(output_path, "r:gz") as tar:
            members = tar.getmembers()
            files_data = {}
            for member in members:
                if member.isfile():
                    files_data[member.name] = tar.extractfile(member).read()
        
        # Create a new tarball with modified file
        with tarfile.open(output_path, "w:gz") as tar:
            for member in members:
                if member.isfile():
                    info = tarfile.TarInfo(name=member.name)
                    # Modify the content of SKILL.md
                    if "SKILL.md" in member.name:
                        modified_content = b"# Tampered Skill\n\nThis skill has been modified."
                        info.size = len(modified_content)
                        tar.addfile(info, io.BytesIO(modified_content))
                    else:
                        info.size = len(files_data[member.name])
                        tar.addfile(info, io.BytesIO(files_data[member.name]))
                elif member.isdir():
                    info = tarfile.TarInfo(name=member.name)
                    info.type = tarfile.DIRTYPE
                    tar.addfile(info)
        
        # Verification should fail due to hash mismatch
        verifier = TSBVerifier(output_path)
        is_valid, message = verifier.verify(verify_signature=False, skip_audit_verification=True)
        
        self.assertFalse(is_valid, "Verification should fail with modified file content")
        self.assertIn("Bundle hash mismatch", message)

    def test_tsb_path_traversal_protection_in_extract(self) -> None:
        """Test that extract_skill() blocks path traversal attacks."""
        # Build a valid TSB first
        metadata = TSBMetadata(
            skill_name="test-skill",
            skill_version="1.0.0",
            skill_author="test-author",
            created_at="2024-01-01T00:00:00Z",
        )
        
        builder = TSBBuilder(
            skill_path=self.skill_path,
            audit_log_path=self.audit_log_path,
            author_key_path=None,
        )
        
        output_path = self.temp_dir / "test.tsb"
        builder.build_tsb(output_path, metadata, skip_audit_verification=True)
        
        # Inject a malicious tar member with path traversal
        import tarfile
        import io
        
        # Read the original tarball
        with tarfile.open(output_path, "r:gz") as tar:
            members = tar.getmembers()
            files_data = {}
            for member in members:
                if member.isfile():
                    files_data[member.name] = tar.extractfile(member).read()
        
        # Create a new tarball with a malicious member
        with tarfile.open(output_path, "w:gz") as tar:
            # Add original files
            for member in members:
                if member.isfile():
                    info = tarfile.TarInfo(name=member.name)
                    info.size = len(files_data[member.name])
                    tar.addfile(info, io.BytesIO(files_data[member.name]))
                elif member.isdir():
                    info = tarfile.TarInfo(name=member.name)
                    info.type = tarfile.DIRTYPE
                    tar.addfile(info)
            
            # Add malicious file with path traversal
            malicious_info = tarfile.TarInfo(name="../malicious.txt")
            malicious_info.size = len(b"malicious content")
            tar.addfile(malicious_info, io.BytesIO(b"malicious content"))
        
        # Extraction should raise an error for path traversal
        # The filter='data' parameter raises tarfile.OutsideDestinationError
        verifier = TSBVerifier(output_path)
        extract_path = self.temp_dir / "extracted"
        
        # The path traversal is blocked by the filter, which raises OutsideDestinationError
        # This is the correct security behavior
        with self.assertRaises((ValueError, tarfile.OutsideDestinationError)):
            verifier.extract_skill(extract_path)

    def test_tsb_deterministic_hash_across_multiple_builds(self) -> None:
        """Test that TSB hash is deterministic across multiple builds."""
        metadata = TSBMetadata(
            skill_name="test-skill",
            skill_version="1.0.0",
            skill_author="test-author",
            created_at="2024-01-01T00:00:00Z",
        )
        
        builder = TSBBuilder(
            skill_path=self.skill_path,
            audit_log_path=self.audit_log_path,
            author_key_path=None,
        )
        
        # Build twice
        output_path1 = self.temp_dir / "test1.tsb"
        output_path2 = self.temp_dir / "test2.tsb"
        
        manifest1 = builder.build_tsb(output_path1, metadata, skip_audit_verification=True)
        manifest2 = builder.build_tsb(output_path2, metadata, skip_audit_verification=True)
        
        # Hashes should be identical
        self.assertEqual(
            manifest1.attestation.bundle_hash,
            manifest2.attestation.bundle_hash,
            "Bundle hashes should be deterministic"
        )


if __name__ == "__main__":
    unittest.main()
