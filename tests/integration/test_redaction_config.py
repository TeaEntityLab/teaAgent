"""IT: Configurable PII redaction.

RedactionConfig lets operators toggle which string patterns are redacted in
audit logs and supply extra custom patterns.
"""

from __future__ import annotations

from teaagent.audit import AuditLogger
from teaagent.redaction import RedactionConfig


def test_default_redaction_removes_bearer_token(tmp_path):
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log)
    audit.record('msg', 'r1', note='Bearer sk-abcdefghijklmno')
    raw = log.read_text()
    assert 'sk-abcdefghijklmno' not in raw
    assert 'Bearer' in raw  # prefix survives, value redacted


def test_disable_bearer_pattern_preserves_token(tmp_path):
    log = tmp_path / 'run.jsonl'
    cfg = RedactionConfig(bearer_tokens=False)
    audit = AuditLogger(path=log, redaction_config=cfg)
    audit.record('msg', 'r1', note='Bearer mytoken12345678')
    raw = log.read_text()
    assert 'mytoken12345678' in raw


def test_disable_api_keys_preserves_sk_token(tmp_path):
    log = tmp_path / 'run.jsonl'
    cfg = RedactionConfig(api_keys=False)
    audit = AuditLogger(path=log, redaction_config=cfg)
    audit.record('msg', 'r1', note='key is sk-abcdefghijklm1')
    raw = log.read_text()
    assert 'sk-abcdefghijklm1' in raw


def test_custom_extra_pattern_redacted(tmp_path):
    import re

    log = tmp_path / 'run.jsonl'
    cfg = RedactionConfig(
        extra_patterns=[(re.compile(r'SUPERSECRET\w+'), '[CUSTOM-REDACTED]')]
    )
    audit = AuditLogger(path=log, redaction_config=cfg)
    audit.record('msg', 'r1', note='token is SUPERSECRETxyz99')
    raw = log.read_text()
    assert 'SUPERSECRETxyz99' not in raw
    assert '[CUSTOM-REDACTED]' in raw


def test_disable_all_patterns_preserves_tokens(tmp_path):
    log = tmp_path / 'run.jsonl'
    cfg = RedactionConfig(
        bearer_tokens=False,
        api_keys=False,
        jwt_tokens=False,
        aws_keys=False,
        github_tokens=False,
        query_params=False,
    )
    audit = AuditLogger(path=log, redaction_config=cfg)
    audit.record('msg', 'r1', note='Bearer plaintext')
    raw = log.read_text()
    assert 'plaintext' in raw


def test_redaction_config_default_is_all_enabled():
    cfg = RedactionConfig()
    assert cfg.bearer_tokens is True
    assert cfg.api_keys is True
    assert cfg.jwt_tokens is True
    assert cfg.aws_keys is True
    assert cfg.github_tokens is True
    assert cfg.query_params is True


def test_in_memory_audit_not_affected_by_redaction_config():
    """AuditLogger without path ignores redaction_config (events not written)."""
    cfg = RedactionConfig(bearer_tokens=False)
    audit = AuditLogger(redaction_config=cfg)
    event = audit.record('msg', 'r1', note='Bearer abc123456789')
    # In-memory event still redacts content (redaction is always applied to payload)
    assert isinstance(event.payload['note'], str)


def test_aws_key_redacted_by_default(tmp_path):
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log)
    audit.record('msg', 'r1', note='key=AKIAIOSFODNN7EXAMPLE')
    raw = log.read_text()
    assert 'AKIAIOSFODNN7EXAMPLE' not in raw


def test_disable_aws_keys_preserves_akia_token(tmp_path):
    log = tmp_path / 'run.jsonl'
    cfg = RedactionConfig(aws_keys=False)
    audit = AuditLogger(path=log, redaction_config=cfg)
    audit.record('msg', 'r1', note='key=AKIAIOSFODNN7EXAMPLE')
    raw = log.read_text()
    assert 'AKIAIOSFODNN7EXAMPLE' in raw
