"""Compat shim: domain reasoning moved to ``teaagent.domain.agent_factory`` (A-P1-1).

This module re-exports the public API from :mod:`teaagent.domain.agent_factory`
so that existing importers (``from teaagent.agent_factory import ...``) continue
to work unchanged. New code should import from ``teaagent.domain.agent_factory``.

See ADR-0030 for the root-module compat shim convention.
"""

from __future__ import annotations

from teaagent.domain.agent_factory import AgentFactory, AgentSpecification

__all__ = ['AgentFactory', 'AgentSpecification']
