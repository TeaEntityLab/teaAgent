"""Compat shim: domain reasoning moved to ``teaagent.domain.workflow_engine`` (A-P1-1).

This module re-exports the public API from :mod:`teaagent.domain.workflow_engine`
so that existing importers (``from teaagent.workflow_engine import ...``) continue
to work unchanged. New code should import from ``teaagent.domain.workflow_engine``.

See ADR-0030 for the root-module compat shim convention.
"""

from __future__ import annotations

from teaagent.domain.workflow_engine import (
    StepExecution,
    ValidationResult,
    WorkflowEngine,
    WorkflowExecution,
    WorkflowState,
    workflow_execution_from_dict,
    workflow_execution_to_dict,
)

__all__ = [
    'StepExecution',
    'ValidationResult',
    'WorkflowEngine',
    'WorkflowExecution',
    'WorkflowState',
    'workflow_execution_from_dict',
    'workflow_execution_to_dict',
]
