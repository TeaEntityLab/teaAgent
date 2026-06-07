"""Audit-related domain types (canonical import path)."""

from teaagent.audit import AuditEvent, AuditLogger
from teaagent.audit_chain import (
    ChainVerificationResult,
    compute_event_hash,
    verify_audit_chain,
)

__all__ = [
    'AuditEvent',
    'AuditLogger',
    'ChainVerificationResult',
    'compute_event_hash',
    'verify_audit_chain',
]
