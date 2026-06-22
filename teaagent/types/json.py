"""Aliases for JSON-shaped boundaries (tool args/results, report payloads).

These name the *intentionally dynamic* JSON boundary so a signature reads as
"a JSON object" rather than a bare ``dict[str, Any]`` that merely looks
un-annotated. Structure at these boundaries is schemaless at the type level and
validated at runtime (e.g. ``docs/audit-event.schema.json``, tool input/output
schemas), so widening to a concrete model here would be inaccurate.

Use these for genuine JSON payloads only; prefer concrete types / ``Protocol``
classes anywhere the shape is actually known.
"""

from __future__ import annotations

from typing import Any

# A decoded JSON value (object / array / string / number / bool / null). Kept as
# Any at this leaf: the value is schemaless until runtime validation.
JsonValue = Any

# A JSON object — the common case for tool arguments, tool results, and the
# report/payload dicts assembled across the codebase.
JsonMapping = dict[str, JsonValue]

__all__ = ['JsonMapping', 'JsonValue']
