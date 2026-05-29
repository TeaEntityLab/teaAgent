"""Validation and self-healing for code correctness.

This module provides:
- LSP/static analysis integration (ruff, mypy, tsc, eslint)
- Validation hooks for tool registry
- Self-healing loop for error correction
- Automatic test selection based on code ontology
"""

from __future__ import annotations

from teaagent.validation.tool_detector import detect_available_tools
from teaagent.validation.profiles import (
    PROFILE_NAMES,
    ProfileValidationReport,
    run_profile_validation,
)
from teaagent.validation.validators import ValidationResult, ValidationRunner

__all__ = [
    'PROFILE_NAMES',
    'ProfileValidationReport',
    'detect_available_tools',
    'ValidationRunner',
    'ValidationResult',
    'run_profile_validation',
]
