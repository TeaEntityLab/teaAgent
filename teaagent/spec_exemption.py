"""Risk-adaptive spec exemption system (CPP-P1-005).

Low-risk tasks can proceed with an explicit exemption receipt instead of
requiring a full spec ceremony.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional
from uuid import uuid4

from teaagent.audit import AuditLogger, secure_audit_dir, secure_audit_file, utc_now
from teaagent.storage import atomic_write_text

logger = logging.getLogger(__name__)

ExemptionReason = Literal[
    'small_clear_task',
    'read_only',
    'docs_only',
    'low_risk_refactor',
    'known_pattern',
]

RiskLevel = Literal['low', 'medium']

_VALID_REASONS: frozenset[str] = frozenset(
    {'small_clear_task', 'read_only', 'docs_only', 'low_risk_refactor', 'known_pattern'}
)

_VALID_RISK_LEVELS: frozenset[str] = frozenset({'low', 'medium'})


@dataclass
class SpecExemptionReceipt:
    """Receipt documenting that a spec requirement has been explicitly waived."""

    exemption_id: str
    reason: ExemptionReason
    spec_requirement_waived: str
    risk_level: RiskLevel = 'low'
    granted_at: str = ''

    task_description: str = ''
    changed_files: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.exemption_id:
            self.exemption_id = uuid4().hex
        if not self.granted_at:
            self.granted_at = utc_now()
        if self.reason not in _VALID_REASONS:
            raise ValueError(
                f"Invalid exemption reason '{self.reason}'. "
                f'Must be one of: {sorted(_VALID_REASONS)}'
            )
        if self.risk_level not in _VALID_RISK_LEVELS:
            raise ValueError(
                f"Invalid risk_level '{self.risk_level}'. "
                f'Must be one of: {sorted(_VALID_RISK_LEVELS)}'
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            'exemption_id': self.exemption_id,
            'reason': self.reason,
            'spec_requirement_waived': self.spec_requirement_waived,
            'risk_level': self.risk_level,
            'granted_at': self.granted_at,
            'task_description': self.task_description,
            'changed_files': list(self.changed_files),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpecExemptionReceipt:
        return cls(
            exemption_id=data.get('exemption_id', ''),
            reason=data.get('reason', 'small_clear_task'),
            spec_requirement_waived=data.get('spec_requirement_waived', ''),
            risk_level=data.get('risk_level', 'low'),
            granted_at=data.get('granted_at', ''),
            task_description=data.get('task_description', ''),
            changed_files=list(data.get('changed_files', [])),
        )


def _exemptions_dir(root: str | Path = '.') -> Path:
    d = Path(root).resolve() / '.teaagent' / 'spec-exemptions'
    d.mkdir(parents=True, exist_ok=True)
    secure_audit_dir(d)
    return d


def _exemption_path(exemption_id: str, root: str | Path = '.') -> Path:
    return _exemptions_dir(root) / f'{exemption_id}.json'


def grant_spec_exemption(
    reason: ExemptionReason,
    risk_level: RiskLevel,
    spec_requirement: str,
    *,
    task_description: str = '',
    changed_files: Optional[list[str]] = None,
    audit_logger: Optional[AuditLogger] = None,
    root: str | Path = '.',
) -> SpecExemptionReceipt:
    """Issue a spec exemption receipt and persist it to disk."""
    if risk_level not in _VALID_RISK_LEVELS:
        raise ValueError(
            f"Invalid risk_level '{risk_level}'. Must be one of "
            f'{sorted(_VALID_RISK_LEVELS)}'
        )
    if reason not in _VALID_REASONS:
        raise ValueError(
            f"Invalid reason '{reason}'. Must be one of {sorted(_VALID_REASONS)}"
        )

    receipt = SpecExemptionReceipt(
        exemption_id=uuid4().hex,
        reason=reason,
        spec_requirement_waived=spec_requirement,
        risk_level=risk_level,
        task_description=task_description,
        changed_files=list(changed_files or []),
    )

    path = _exemption_path(receipt.exemption_id, root)
    atomic_write_text(path, json.dumps(receipt.to_dict(), indent=2))
    secure_audit_file(path)
    logger.info(
        f'Spec exemption granted: {receipt.exemption_id} '
        f'(reason={receipt.reason}, risk={receipt.risk_level})'
    )

    if audit_logger is not None:
        audit_logger.record(
            'spec_exemption_granted',
            receipt.exemption_id,
            **receipt.to_dict(),
        )

    return receipt


def load_exemption(
    exemption_id: str, *, root: str | Path = '.'
) -> SpecExemptionReceipt:
    path = _exemption_path(exemption_id, root)
    if not path.is_file():
        raise FileNotFoundError(f'Exemption {exemption_id} not found at {path}')
    data = json.loads(path.read_text(encoding='utf-8'))
    return SpecExemptionReceipt.from_dict(data)


def delete_exemption(exemption_id: str, *, root: str | Path = '.') -> None:
    path = _exemption_path(exemption_id, root)
    if not path.is_file():
        raise FileNotFoundError(f'Exemption {exemption_id} not found at {path}')
    path.unlink()
    logger.info(f'Deleted spec exemption {exemption_id}')


_SMALL_TASK_LINE_COUNT = 20

_DOCS_ONLY_EXTENSIONS: frozenset[str] = frozenset(
    {'.md', '.rst', '.txt', '.adoc', '.markdown'}
)

_READ_ONLY_KEYWORDS: frozenset[str] = frozenset(
    {
        'read',
        'inspect',
        'analyze',
        'summarize',
        'review',
        'find',
        'search',
        'list',
        'show',
        'explore',
        'audit',
        'check',
        'report',
        'display',
        'describe',
        'look at',
        'examine',
        'output',
        'print',
    }
)

_SMALL_TASK_KEYWORDS: frozenset[str] = frozenset(
    {
        'fix typo',
        'typo',
        'spelling',
        'format',
        'lint',
        'comment',
        'docstring',
        'add test',
        'update test',
        'trivial',
        'minor',
        'simple',
    }
)

_KNOWN_PATTERN_INDICATORS: frozenset[str] = frozenset(
    {
        'rename',
        'refactor',
        'extract method',
        'extract function',
        'move file',
        'add logging',
        'add error handling',
        'add validation',
    }
)


def _is_markdown_ext(filename: str) -> bool:
    return Path(filename).suffix in _DOCS_ONLY_EXTENSIONS


def _has_read_only_keyword(description: str) -> bool:
    lower = description.lower()
    return any(kw in lower for kw in _READ_ONLY_KEYWORDS)


def _all_files_are_docs(changed_files: list[str]) -> bool:
    if not changed_files:
        return False
    return all(_is_markdown_ext(f) for f in changed_files)


def _matches_small_task_keyword(description: str) -> bool:
    lower = description.lower()
    return any(kw in lower for kw in _SMALL_TASK_KEYWORDS)


def _matches_known_pattern_keyword(description: str) -> bool:
    lower = description.lower()
    return any(indicator in lower for indicator in _KNOWN_PATTERN_INDICATORS)


def _build_read_only_exemption(
    task_description: str,
    changed_files: list[str],
) -> SpecExemptionReceipt:
    return SpecExemptionReceipt(
        exemption_id=uuid4().hex,
        reason='read_only',
        spec_requirement_waived='plan-before-write',
        risk_level='low',
        task_description=task_description,
        changed_files=list(changed_files),
    )


def _build_docs_only_exemption(
    task_description: str,
    changed_files: list[str],
) -> SpecExemptionReceipt:
    return SpecExemptionReceipt(
        exemption_id=uuid4().hex,
        reason='docs_only',
        spec_requirement_waived='plan-before-write',
        risk_level='low',
        task_description=task_description,
        changed_files=list(changed_files),
    )


def _build_small_task_exemption(
    task_description: str,
    changed_files: list[str],
) -> SpecExemptionReceipt:
    return SpecExemptionReceipt(
        exemption_id=uuid4().hex,
        reason='small_clear_task',
        spec_requirement_waived='plan-before-write',
        risk_level='low',
        task_description=task_description,
        changed_files=list(changed_files),
    )


def _build_known_pattern_exemption(
    task_description: str,
    changed_files: list[str],
) -> SpecExemptionReceipt:
    return SpecExemptionReceipt(
        exemption_id=uuid4().hex,
        reason='known_pattern',
        spec_requirement_waived='plan-before-write',
        risk_level='medium',
        task_description=task_description,
        changed_files=list(changed_files),
    )


class ExemptionDetector:
    """Auto-detects when a task qualifies for spec exemption via deterministic heuristics."""

    @staticmethod
    def detect(
        task_description: str,
        changed_files: list[str],
        *,
        line_count: Optional[int] = None,
        permission_mode: Optional[str] = None,
    ) -> Optional[SpecExemptionReceipt]:
        if permission_mode == 'danger-full-access':
            return None

        if permission_mode == 'read-only' or _has_read_only_keyword(task_description):
            return _build_read_only_exemption(task_description, changed_files)

        if _all_files_are_docs(changed_files):
            return _build_docs_only_exemption(task_description, changed_files)

        if line_count is not None and line_count < _SMALL_TASK_LINE_COUNT:
            return _build_small_task_exemption(task_description, changed_files)

        if _matches_small_task_keyword(task_description):
            return _build_small_task_exemption(task_description, changed_files)

        if changed_files and len(changed_files) <= 1:
            return _build_small_task_exemption(task_description, changed_files)

        if _matches_known_pattern_keyword(task_description):
            return _build_known_pattern_exemption(task_description, changed_files)

        return None
