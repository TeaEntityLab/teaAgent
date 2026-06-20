"""Compat shim: domain reasoning moved to ``teaagent.domain.intent`` (A-P1-1).

This module re-exports the public API from :mod:`teaagent.domain.intent` so
that existing importers (``from teaagent.intent import ...``) continue to work
unchanged. New code should import from ``teaagent.domain.intent``.

The interactive clarification behavior added in U-P1-1 is preserved: the
``clarify_task`` / ``ClarificationResult`` symbols consumed by the CLI
handlers are re-exported here unchanged.

See ADR-0030 for the root-module compat shim convention.
"""

from __future__ import annotations

from teaagent.domain.intent import (
    ACTION_WORDS,
    VAGUE_WORDS,
    ClarificationResult,
    IntentScore,
    build_task_spec,
    clamp,
    clarify_task,
    next_question,
)

__all__ = [
    'ACTION_WORDS',
    'ClarificationResult',
    'IntentScore',
    'VAGUE_WORDS',
    'build_task_spec',
    'clamp',
    'clarify_task',
    'next_question',
]
