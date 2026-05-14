"""Configurable PII redaction for audit logs.

``RedactionConfig`` selects which pattern groups are active.  Pass an
instance to :class:`~teaagent.audit.AuditLogger` to override the defaults.

Usage::

    from teaagent.redaction import RedactionConfig
    from teaagent.audit import AuditLogger

    cfg = RedactionConfig(bearer_tokens=False)   # keep Bearer tokens in logs
    audit = AuditLogger(path=log_path, redaction_config=cfg)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Pattern

_Pattern = tuple[Pattern[str], str]


@dataclass(frozen=True)
class RedactionConfig:
    """Toggle individual PII pattern groups and supply extra patterns.

    All groups are enabled by default, mirroring the built-in behaviour.
    Set any group to ``False`` to preserve those values in the audit log.

    Parameters
    ----------
    bearer_tokens:
        Redact ``Bearer <token>`` values.
    api_keys:
        Redact ``sk-`` prefixed API keys.
    jwt_tokens:
        Redact three-segment JWT strings (``xxx.yyy.zzz``).
    aws_keys:
        Redact ``AKIA…`` AWS access key IDs.
    github_tokens:
        Redact ``ghp_`` and ``github_pat_`` tokens.
    query_params:
        Redact ``?api_key=…``, ``?token=…``, etc. in URLs.
    extra_patterns:
        Additional ``(compiled_pattern, replacement)`` tuples applied after
        the built-in groups.
    """

    bearer_tokens: bool = True
    api_keys: bool = True
    jwt_tokens: bool = True
    aws_keys: bool = True
    github_tokens: bool = True
    query_params: bool = True
    extra_patterns: list[_Pattern] = field(default_factory=list)

    def build_patterns(self) -> list[_Pattern]:
        """Return the active list of ``(pattern, replacement)`` pairs."""
        patterns: list[_Pattern] = []
        if self.bearer_tokens:
            patterns.append(
                (
                    re.compile(r'\bBearer\s+[A-Za-z0-9._~+/=-]{8,}'),
                    'Bearer [redacted]',
                )
            )
        if self.api_keys:
            patterns.append(
                (re.compile(r'\bsk-[A-Za-z0-9][A-Za-z0-9_-]{8,}\b'), '[redacted]')
            )
        if self.query_params:
            patterns.append(
                (
                    re.compile(
                        r'(?i)\b(api[_-]?key|token|secret|password)=([^\s&;]{4,})'
                    ),
                    r'\1=[redacted]',
                )
            )
        if self.jwt_tokens:
            patterns.append(
                (
                    re.compile(
                        r'\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b'
                    ),
                    '[redacted-JWT]',
                )
            )
        if self.aws_keys:
            patterns.append((re.compile(r'\bAKIA[0-9A-Z]{16}\b'), '[redacted]'))
        if self.github_tokens:
            patterns.append(
                (
                    re.compile(r'\b(ghp_|github_pat_)[A-Za-z0-9_]{20,}\b'),
                    '[redacted]',
                )
            )
        patterns.extend(self.extra_patterns)
        return patterns
