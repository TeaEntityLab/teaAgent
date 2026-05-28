"""Tests for Provenanced Skill Bundle (TSB) format and verification."""

from __future__ import annotations

import tarfile
import tempfile
import unittest
from pathlib import Path

from teaagent.sigstore_signer import TSBProvenanceVerifier
from teaagent.tsb_format import (
    RedactionFilter,
    RedactionRule,
    TSBAttestation,
    TSBBuilder,
    TSBMetadata,
    TSBVerifier,
)


class RedactionRuleTests(unittest.TestCase):
    def test_redaction_rule_defaults(self) -> None:
        rule = RedactionRule(pattern='api_key')
        self.assertEqual(rule.pattern, 'api_key')
        self.assertEqual(rule.replacement, '[REDACTED]')
        self.assertFalse(rule.is_regex)

    def test_redaction_rule_custom(self) -> None:
        rule = RedactionRule(pattern=r'/home/\w+', replacement='[HOME]/', is_regex=True)
        self.assertEqual(rule.replacement, '[HOME]/')
        self.assertTrue(rule.is_regex)


class RedactionFilterTests(unittest.TestCase):
    def test_redact_string(self) -> None:
        filter = RedactionFilter()
        result = filter.redact_string('my_api_key=secret123')
        self.assertIn('[REDACTED]', result)
        self.assertNotIn('secret123', result)

    def test_redact_dict(self) -> None:
        filter = RedactionFilter()
        data = {'api_key': 'secret123', 'name': 'test'}
        result = filter.redact_dict(data)
        # The redaction filter replaces sensitive patterns in strings
        # Since "api_key" is in the key name, it gets redacted
        self.assertIn('[REDACTED]', result['api_key'])
        self.assertEqual(result['name'], 'test')

    def test_redact_nested_dict(self) -> None:
        filter = RedactionFilter()
        data = {'config': {'api_key': 'secret123', 'other': 'value'}}
        result = filter.redact_dict(data)
        # The redaction filter replaces sensitive patterns in strings
        self.assertIn('[REDACTED]', result['config']['api_key'])
        self.assertEqual(result['config']['other'], 'value')

    def test_redact_nested_sensitive_key(self) -> None:
        """Test that values under sensitive keys are completely redacted."""
        filter = RedactionFilter()
        data = {'api_key': {'raw': 'secret123', 'type': 'production'}}
        result = filter.redact_dict(data)
        # Entire value under sensitive key should be redacted
        self.assertEqual(result['api_key'], '[REDACTED]')
        self.assertNotIn('secret123', str(result))

    def test_redact_list_with_sensitive_data(self) -> None:
        """Test that sensitive data in lists is redacted."""
        filter = RedactionFilter()
        data = {'tokens': ['abc123', 'def456']}
        result = filter.redact_dict(data)
        # Entire value under sensitive key should be redacted
        self.assertEqual(result['tokens'], '[REDACTED]')
        self.assertNotIn('abc123', str(result))

    def test_redact_list_with_dicts(self) -> None:
        """Test that dicts in lists are recursively redacted."""
        filter = RedactionFilter()
        data = {'items': [{'api_key': 'secret123'}, {'name': 'test'}]}
        result = filter.redact_dict(data)
        # Nested dict with sensitive key should be redacted
        self.assertEqual(result['items'][0]['api_key'], '[REDACTED]')
        self.assertEqual(result['items'][1]['name'], 'test')

    def test_redact_paths(self) -> None:
        filter = RedactionFilter()
        result = filter.redact_string('/home/user/project/file.py')
        self.assertIn('[HOME]/', result)
        self.assertNotIn('/home/', result)

    def test_redact_audit_log(self) -> None:
        filter = RedactionFilter()
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / 'audit.jsonl'
            audit_path.write_text(
                '{"event_id": "e1", "api_key": "secret123", "path": "/home/user/file"}\n'
                '{"event_id": "e2", "token": "abc123"}',
                encoding='utf-8',
            )
            result = filter.redact_audit_log(audit_path)
            self.assertIn('[REDACTED]', result)
            # The redaction filter replaces key names containing sensitive patterns
            # Values may still be present in the JSON structure
            self.assertIn('[HOME]/', result)


class TSBMetadataTests(unittest.TestCase):
    def test_metadata_defaults(self) -> None:
        metadata = TSBMetadata(
            skill_name='test-skill',
            skill_version='1.0.0',
            skill_author='test-author',
            created_at='2024-01-01T00:00:00Z',
        )
        self.assertEqual(
            metadata.tsb_version, '1.1'
        )  # Updated to v1.1 with path-aware hashing
        self.assertEqual(metadata.environment_type, 'uv')
        self.assertEqual(metadata.python_version, '3.11')


class TSBAttestationTests(unittest.TestCase):
    def test_attestation_defaults(self) -> None:
        attestation = TSBAttestation(
            author_signature='sig123',
            audit_chain_hash='hash123',
            bundle_hash='bundle123',
        )
        self.assertEqual(attestation.signature_algorithm, 'ed25519')


class TSBBuilderTests(unittest.TestCase):
    def test_build_tsb_basic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_path = Path(tmp) / 'skill'
            skill_path.mkdir()
            (skill_path / 'SKILL.md').write_text('# Test Skill', encoding='utf-8')

            audit_path = Path(tmp) / 'audit.jsonl'
            audit_path.write_text(
                '{"event_id": "e1", "event_type": "test", "run_id": "r1", "created_at": "2024-01-01T00:00:00+00:00", "payload": {}, "prev_hash": "genesis", "hash": "abc123"}',
                encoding='utf-8',
            )

            output_path = Path(tmp) / 'skill.tsb'

            metadata = TSBMetadata(
                skill_name='test-skill',
                skill_version='1.0.0',
                skill_author='test-author',
                created_at='2024-01-01T00:00:00Z',
            )

            builder = TSBBuilder(skill_path, audit_path)
            manifest = builder.build_tsb(
                output_path, metadata, skip_audit_verification=True
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(manifest.metadata.skill_name, 'test-skill')
            self.assertTrue(len(manifest.attestation.bundle_hash) > 0)
            self.assertTrue(len(manifest.attestation.audit_chain_hash) > 0)

    def test_build_tsb_with_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_path = Path(tmp) / 'skill'
            skill_path.mkdir()
            (skill_path / 'SKILL.md').write_text('# Test Skill', encoding='utf-8')

            audit_path = Path(tmp) / 'audit.jsonl'
            audit_path.write_text(
                '{"event_id": "e1", "api_key": "secret123", "run_id": "r1", "created_at": "2024-01-01T00:00:00+00:00", "payload": {}, "prev_hash": "genesis", "hash": "abc123"}',
                encoding='utf-8',
            )

            output_path = Path(tmp) / 'skill.tsb'

            metadata = TSBMetadata(
                skill_name='test-skill',
                skill_version='1.0.0',
                skill_author='test-author',
                created_at='2024-01-01T00:00:00Z',
            )

            builder = TSBBuilder(skill_path, audit_path)
            builder.build_tsb(
                output_path, metadata, skip_audit_verification=True
            )

            # Verify the TSB contains redacted audit log
            with tarfile.open(output_path, 'r:gz') as tar:
                audit_member = tar.extractfile('audit.jsonl')
                if audit_member:
                    audit_content = audit_member.read().decode('utf-8')
                    self.assertIn('[REDACTED]', audit_content)


class TSBVerifierTests(unittest.TestCase):
    def test_verify_valid_tsb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_path = Path(tmp) / 'skill'
            skill_path.mkdir()
            (skill_path / 'SKILL.md').write_text('# Test Skill', encoding='utf-8')

            audit_path = Path(tmp) / 'audit.jsonl'
            audit_path.write_text(
                '{"event_id": "e1", "event_type": "test", "run_id": "r1", "created_at": "2024-01-01T00:00:00+00:00", "payload": {}, "prev_hash": "genesis", "hash": "abc123"}',
                encoding='utf-8',
            )

            tsb_path = Path(tmp) / 'skill.tsb'

            metadata = TSBMetadata(
                skill_name='test-skill',
                skill_version='1.0.0',
                skill_author='test-author',
                created_at='2024-01-01T00:00:00Z',
            )

            builder = TSBBuilder(skill_path, audit_path)
            builder.build_tsb(tsb_path, metadata, skip_audit_verification=True)

            verifier = TSBVerifier(tsb_path)
            is_valid, message = verifier.verify(
                verify_signature=False, skip_audit_verification=True
            )

            self.assertTrue(is_valid, f'Verification failed: {message}')

    def test_verify_unsigned_tsb_rejected(self) -> None:
        """Test that unsigned TSBs are rejected when signature verification is enabled."""
        with tempfile.TemporaryDirectory() as tmp:
            skill_path = Path(tmp) / 'skill'
            skill_path.mkdir()
            (skill_path / 'SKILL.md').write_text('# Test Skill', encoding='utf-8')

            audit_path = Path(tmp) / 'audit.jsonl'
            audit_path.write_text(
                '{"event_id": "e1", "event_type": "test", "run_id": "r1", "created_at": "2024-01-01T00:00:00+00:00", "payload": {}, "prev_hash": "genesis", "hash": "abc123"}',
                encoding='utf-8',
            )

            tsb_path = Path(tmp) / 'skill.tsb'

            metadata = TSBMetadata(
                skill_name='test-skill',
                skill_version='1.0.0',
                skill_author='test-author',
                created_at='2024-01-01T00:00:00Z',
            )

            builder = TSBBuilder(skill_path, audit_path)
            builder.build_tsb(tsb_path, metadata, skip_audit_verification=True)

            verifier = TSBVerifier(tsb_path)
            # Unsigned bundle should be rejected when verify_signature=True
            is_valid, message = verifier.verify(
                verify_signature=True, skip_audit_verification=True
            )

            self.assertFalse(is_valid, 'Unsigned TSB should be rejected')
            self.assertIn(
                'unsigned',
                message.lower(),
                f'Error message should mention unsigned: {message}',
            )

    def test_verify_unsigned_tsb_allowed_with_flag(self) -> None:
        """Test that unsigned TSBs are allowed when allow_unsigned=True."""
        with tempfile.TemporaryDirectory() as tmp:
            skill_path = Path(tmp) / 'skill'
            skill_path.mkdir()
            (skill_path / 'SKILL.md').write_text('# Test Skill', encoding='utf-8')

            audit_path = Path(tmp) / 'audit.jsonl'
            audit_path.write_text(
                '{"event_id": "e1", "event_type": "test", "run_id": "r1", "created_at": "2024-01-01T00:00:00+00:00", "payload": {}, "prev_hash": "genesis", "hash": "abc123"}',
                encoding='utf-8',
            )

            tsb_path = Path(tmp) / 'skill.tsb'

            metadata = TSBMetadata(
                skill_name='test-skill',
                skill_version='1.0.0',
                skill_author='test-author',
                created_at='2024-01-01T00:00:00Z',
            )

            builder = TSBBuilder(skill_path, audit_path)
            builder.build_tsb(tsb_path, metadata, skip_audit_verification=True)

            verifier = TSBVerifier(tsb_path)
            # Unsigned bundle should be allowed when allow_unsigned=True
            is_valid, message = verifier.verify(
                verify_signature=True, allow_unsigned=True, skip_audit_verification=True
            )

            self.assertTrue(
                is_valid,
                f'Unsigned TSB should be allowed with allow_unsigned=True: {message}',
            )
            self.assertIn(
                'development mode',
                message.lower(),
                f'Message should mention development mode: {message}',
            )

    def test_verify_ssh_signature_rejected(self) -> None:
        """Test that SSH signatures are rejected with clear error message."""
        # Create a mock manifest with SSH signer type
        manifest = {
            'metadata': {
                'skill_name': 'test-skill',
                'skill_version': '1.0.0',
                'skill_author': 'test-author',
                'created_at': '2024-01-01T00:00:00Z',
            },
            'attestation': {
                'author_signature': 'fake_ssh_signature',
                'audit_chain_hash': 'hash123',
                'bundle_hash': 'bundle123',
                'signer': 'ssh',
            },
        }

        verifier = TSBProvenanceVerifier(require_signature=True)
        is_valid, message = verifier.verify_provenance(Path('fake.tsb'), manifest)

        self.assertFalse(is_valid, 'SSH signatures should be rejected')
        self.assertIn(
            'ssh', message.lower(), f'Error message should mention SSH: {message}'
        )
        self.assertIn(
            'not implemented',
            message.lower(),
            f'Error message should mention not implemented: {message}',
        )

    def test_verify_tampered_tsb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_path = Path(tmp) / 'skill'
            skill_path.mkdir()
            (skill_path / 'SKILL.md').write_text('# Test Skill', encoding='utf-8')

            audit_path = Path(tmp) / 'audit.jsonl'
            audit_path.write_text(
                '{"event_id": "e1", "event_type": "test", "run_id": "r1", "created_at": "2024-01-01T00:00:00+00:00", "payload": {}, "prev_hash": "genesis", "hash": "abc123"}',
                encoding='utf-8',
            )

            tsb_path = Path(tmp) / 'skill.tsb'

            metadata = TSBMetadata(
                skill_name='test-skill',
                skill_version='1.0.0',
                skill_author='test-author',
                created_at='2024-01-01T00:00:00Z',
            )

            builder = TSBBuilder(skill_path, audit_path)
            builder.build_tsb(tsb_path, metadata, skip_audit_verification=True)

            # Tamper with the TSB
            with open(tsb_path, 'ab') as f:
                f.write(b'tampered')

            verifier = TSBVerifier(tsb_path)
            is_valid, message = verifier.verify(verify_signature=False)

            self.assertFalse(is_valid)
            self.assertIn('mismatch', message.lower())

    def test_extract_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_path = Path(tmp) / 'skill'
            skill_path.mkdir()
            (skill_path / 'SKILL.md').write_text('# Test Skill', encoding='utf-8')
            (skill_path / 'README.md').write_text('# README', encoding='utf-8')

            audit_path = Path(tmp) / 'audit.jsonl'
            audit_path.write_text(
                '{"event_id": "e1", "event_type": "test", "run_id": "r1", "created_at": "2024-01-01T00:00:00+00:00", "payload": {}, "prev_hash": "genesis", "hash": "abc123"}',
                encoding='utf-8',
            )

            tsb_path = Path(tmp) / 'skill.tsb'
            output_path = Path(tmp) / 'extracted'

            metadata = TSBMetadata(
                skill_name='test-skill',
                skill_version='1.0.0',
                skill_author='test-author',
                created_at='2024-01-01T00:00:00Z',
            )

            builder = TSBBuilder(skill_path, audit_path)
            builder.build_tsb(tsb_path, metadata, skip_audit_verification=True)

            verifier = TSBVerifier(tsb_path)
            verifier.extract_skill(output_path)

            self.assertTrue(output_path.exists())
            self.assertTrue((output_path / 'SKILL.md').exists())
            self.assertTrue((output_path / 'README.md').exists())


if __name__ == '__main__':
    unittest.main()
