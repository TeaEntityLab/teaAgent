"""Shared output utilities for CLI handlers.

This module provides common output formatting functions for CLI handlers.
For domain-specific output formatting (e.g., TTY-aware tables, security redaction),
handlers should define their own specialized functions.
"""

from __future__ import annotations

import json
from typing import Any


def print_json(value: Any) -> None:
    """Print value as JSON to stdout.

    This is a shared utility for CLI handlers that need to output JSON.
    Uses ensure_ascii=False for proper Unicode support and sort_keys=True
    for consistent output ordering.

    Args:
        value: The value to print as JSON (typically a dict or list).
    """
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
