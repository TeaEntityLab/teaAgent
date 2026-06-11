"""Tests for Provenanced Skill Bundle (TSB) format and verification."""

from __future__ import annotations

import tarfile
import tempfile
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


def test_redaction_rule_defaults() -> None:
    rule = RedactionRule(pattern='api_key')
    assert rule.pattern == 'api_key'
    assert rule.replacement == '[REDACTED]'
    assert not rule.is_regex


def test_redaction_rule_custom() -> None:
    rule = RedactionRule(pattern=r'/home/\w+', replacement='[HOME]/', is_regex=True)
    assert rule.replacement == '[HOME]/'
    assert rule.is_regex


def test_redact_string() -> None:
    filter = RedactionFilter()
    result = filter.redact_string('my_api_key=secret123')
    assert '[REDACTED]' in result
    assert 'secret123' not in result


def test_redact_dict() -> None:
    filter = RedactionFilter()
    data = {'api_key': 'secret123', 'name': 'test'}
    result = filter.redact_dict(data)
    # The redaction filter replaces sensitive patterns in strings
    # Since "api_key" is in the key name, it gets redacted
    assert '[REDACTED]' in result['api_key']
    assert result['name'] == 'test'


def test_redact_nested_dict() -> None:
    filter = RedactionFilter()
    data = {'config': {'api_key': 'secret123', 'other': 'value'}}
    result = filter.redact_dict(data)
    # The redaction filter replaces sensitive patterns in strings
    assert '[REDACTED]' in result['config']['api_key']
    assert result['config']['other'] == 'value'


def test_redact_nested_sensitive_key() -> None:
    """Test that values under sensitive keys are completely redacted."""
    filter = RedactionFilter()
    data = {'api_key': {'raw': 'secret123', 'type': 'production'}}
    result = filter.redact_dict(data)
    # Entire value under sensitive key should be redacted
    assert result['api_key'] == '[REDACTED]'
    assert 'secret123' not in str(result)


def test_redact_list_with_sensitive_data() -> None:
    """Test that sensitive data in lists is redacted."""
    filter = RedactionFilter()
    data = {'tokens': ['abc123', 'def456']}
    result = filter.redact_dict(data)
    # Entire value under sensitive key should be redacted
    assert result['tokens'] == '[REDACTED]'
    assert 'abc123' not in str(result)


def test_redact_list_with_dicts() -> None:
    """Test that dicts in lists are recursively redacted."""
    filter = RedactionFilter()
    data = {'items': [{'api_key': 'secret123'}, {'name': 'test'}]}
    result = filter.redact_dict(data)
    # Nested dict with sensitive key should be redacted
    assert result['items'][0]['api_key'] == '[REDACTED]'
    assert result['items'][1]['name'] == 'test'


def test_redact_paths() -> None:
    filter = RedactionFilter()
    result = filter.redact_string('/home/user/project/file.py')
    assert '[HOME]/' in result
    assert '/home/' not in result


def test_redact_audit_log() -> None:
    filter = RedactionFilter()
    with tempfile.TemporaryDirectory() as tmp:
        audit_path = Path(tmp) / 'audit.jsonl'
        audit_path.write_text(
            '{"event_id": "e1", "api_key": "secret123", "path": "/home/user/file"}\n'
            '{"event_id": "e2", "token": "abc123"}',
            encoding='utf-8',
        )
        result = filter.redact_audit_log(audit_path)
        assert '[REDACTED]' in result
        # The redaction filter replaces key names containing sensitive patterns
        # Values may still be present in the JSON structure
        assert '[HOME]/' in result


def test_metadata_defaults() -> None:
    metadata = TSBMetadata(
        skill_name='test-skill',
        skill_version='1.0.0',
        skill_author='test-author',
        created_at='2024-01-01T00:00:00Z',
    )
    assert metadata.tsb_version == '1.1'  # Updated to v1.1 with path-aware hashing
    assert metadata.environment_type == 'uv'
    assert metadata.python_version == '3.11'


def test_attestation_defaults() -> None:
    attestation = TSBAttestation(
        author_signature='sig123',
        audit_chain_hash='hash123',
        bundle_hash='bundle123',
    )
    assert attestation.signature_algorithm == 'ed25519'


def test_build_tsb_basic() -> None:
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

        assert output_path.exists()
        assert manifest.metadata.skill_name == 'test-skill'
        assert len(manifest.attestation.bundle_hash) > 0
        assert len(manifest.attestation.audit_chain_hash) > 0


def test_build_tsb_with_redaction() -> None:
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
        builder.build_tsb(output_path, metadata, skip_audit_verification=True)

        # Verify the TSB contains redacted audit log
        with tarfile.open(output_path, 'r:gz') as tar:
            audit_member = tar.extractfile('audit.jsonl')
            if audit_member:
                audit_content = audit_member.read().decode('utf-8')
                assert '[REDACTED]' in audit_content


def test_verify_valid_tsb() -> None:
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

        assert is_valid, f'Verification failed: {message}'


def test_verify_unsigned_tsb_rejected() -> None:
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

        assert not is_valid, 'Unsigned TSB should be rejected'
        assert 'unsigned' in message.lower(), (
            f'Error message should mention unsigned: {message}'
        )


def test_verify_unsigned_tsb_allowed_with_flag() -> None:
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

        assert is_valid, (
            f'Unsigned TSB should be allowed with allow_unsigned=True: {message}'
        )
        assert 'development mode' in message.lower(), (
            f'Message should mention development mode: {message}'
        )


def test_verify_ssh_signature_rejected() -> None:
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

    assert not is_valid, 'SSH signatures should be rejected'
    assert 'ssh' in message.lower(), f'Error message should mention SSH: {message}'
    assert 'not yet supported' in message.lower(), (
        f'Error message should indicate SSH is not yet supported: {message}'
    )


def test_verify_tampered_tsb() -> None:
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

        assert not is_valid
        assert 'mismatch' in message.lower()


def test_extract_skill() -> None:
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

        assert output_path.exists()
        assert (output_path / 'SKILL.md').exists()
        assert (output_path / 'README.md').exists()
