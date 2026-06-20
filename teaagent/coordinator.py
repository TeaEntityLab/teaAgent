"""Compat shim: domain reasoning moved to ``teaagent.domain.coordinator`` (A-P1-1).

This module re-exports the public API from :mod:`teaagent.domain.coordinator`
so that existing importers (``from teaagent.coordinator import ...``) continue
to work unchanged. New code should import from ``teaagent.domain.coordinator``.

See ADR-0030 for the root-module compat shim convention.
"""

from __future__ import annotations

from teaagent.domain.coordinator import (
    TaskClassification,
    TaskComplexity,
    TaskCoordinator,
    TaskType,
    WorkflowPlan,
    WorkflowStep,
)

__all__ = [
    'TaskClassification',
    'TaskComplexity',
    'TaskCoordinator',
    'TaskType',
    'WorkflowPlan',
    'WorkflowStep',
]
