"""W3C Trace Context helpers for A2A delegation.

Generates and parses ``traceparent`` headers as defined in
`W3C Trace Context Level 1 <https://www.w3.org/TR/trace-context/>`_.

Format::

    00-{32-hex trace-id}-{16-hex parent-id}-{2-hex flags}

Usage::

    from teaagent.a2a_trace import generate_traceparent, parse_traceparent

    tp = generate_traceparent()       # '00-<trace_id>-<span_id>-01'
    info = parse_traceparent(tp)      # dict with trace_id, parent_id, flags
"""

from __future__ import annotations

import os
from typing import TypedDict


class TraceparentError(ValueError):
    """Raised when a traceparent string cannot be parsed."""


class TraceparentFields(TypedDict):
    version: str
    trace_id: str
    parent_id: str
    flags: str


def generate_traceparent(*, sampled: bool = True) -> str:
    """Generate a fresh W3C traceparent string.

    Parameters
    ----------
    sampled:
        When ``True`` (default) the flags byte is set to ``01`` (sampled).
        Pass ``False`` for ``00`` (not sampled).

    Returns
    -------
    str
        A valid traceparent string, e.g.
        ``'00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'``.
    """
    trace_id = os.urandom(16).hex()
    parent_id = os.urandom(8).hex()
    flags = '01' if sampled else '00'
    return f'00-{trace_id}-{parent_id}-{flags}'


def parse_traceparent(header: str) -> TraceparentFields:
    """Parse a W3C traceparent header string.

    Parameters
    ----------
    header:
        The value of the ``traceparent`` HTTP header.

    Returns
    -------
    :class:`TraceparentFields`
        A typed dict with ``version``, ``trace_id``, ``parent_id``, and
        ``flags`` keys.

    Raises
    ------
    :class:`TraceparentError`
        When the header does not conform to the W3C format.
    """
    parts = header.strip().split('-')
    if len(parts) != 4:
        raise TraceparentError(
            f'traceparent must have 4 dash-separated fields, got {len(parts)}: {header!r}'
        )
    version, trace_id, parent_id, flags = parts

    if len(version) != 2 or not _is_hex(version):
        raise TraceparentError(f'traceparent version must be 2 hex chars: {version!r}')
    if len(trace_id) != 32 or not _is_hex(trace_id):
        raise TraceparentError(
            f'traceparent trace-id must be 32 hex chars: {trace_id!r}'
        )
    if len(parent_id) != 16 or not _is_hex(parent_id):
        raise TraceparentError(
            f'traceparent parent-id must be 16 hex chars: {parent_id!r}'
        )
    if len(flags) != 2 or not _is_hex(flags):
        raise TraceparentError(f'traceparent flags must be 2 hex chars: {flags!r}')

    return TraceparentFields(
        version=version,
        trace_id=trace_id,
        parent_id=parent_id,
        flags=flags,
    )


def _is_hex(s: str) -> bool:
    try:
        int(s, 16)
        return True
    except ValueError:
        return False
