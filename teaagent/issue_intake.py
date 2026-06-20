"""Compat shim: domain reasoning moved to ``teaagent.domain.issue_intake`` (A-P1-1).

This module re-exports the public API from :mod:`teaagent.domain.issue_intake`
so that existing importers (``from teaagent.issue_intake import ...``) continue
to work unchanged. New code should import from ``teaagent.domain.issue_intake``.

See ADR-0030 for the root-module compat shim convention.
"""

from __future__ import annotations

from teaagent.domain.issue_intake import (
    GITHUB_AVAILABLE,
    AcceptanceChecklist,
    AmbiguityCategory,
    AmbiguityDetector,
    AmbiguityReport,
    ChecklistGenerator,
    CommandSuggester,
    CommandSuggestion,
    IssueParser,
    IssueType,
    ParsedIssue,
    PlanArtifact,
    PlanGenerator,
    PlanStep,
)

__all__ = [
    'AcceptanceChecklist',
    'AmbiguityCategory',
    'AmbiguityDetector',
    'AmbiguityReport',
    'ChecklistGenerator',
    'CommandSuggestion',
    'CommandSuggester',
    'GITHUB_AVAILABLE',
    'IssueParser',
    'IssueType',
    'ParsedIssue',
    'PlanArtifact',
    'PlanGenerator',
    'PlanStep',
]
