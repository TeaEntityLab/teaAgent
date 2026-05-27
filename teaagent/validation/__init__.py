"""Validation and self-healing for code correctness.

This module provides:
- LSP/static analysis integration (ruff, mypy, tsc, eslint)
- Validation hooks for tool registry
- Self-healing loop for error correction
- Automatic test selection based on code ontology
"""

from __future__ import annotations

from teaagent.validation.tool_detector import detect_available_tools
from teaagent.validation.validators import ValidationRunner, ValidationResult

__all__ = [
    "detect_available_tools",
    "ValidationRunner",
    "ValidationResult",
]
