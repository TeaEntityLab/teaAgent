from __future__ import annotations

from typing import Any

from teaagent.errors import ToolValidationError

TYPE_MAP = {
    "array": list,
    "boolean": bool,
    "integer": int,
    "number": (int, float),
    "object": dict,
    "string": str,
}


def validate_object_schema(schema: dict[str, Any], value: Any, *, label: str) -> None:
    """Validate a small JSON-schema subset used by P0 tool contracts."""

    if schema.get("type") != "object":
        raise ToolValidationError(f"{label} schema must be an object schema.")
    if not isinstance(value, dict):
        raise ToolValidationError(f"{label} must be an object.")

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    for field_name in required:
        if field_name not in value:
            raise ToolValidationError(f"{label}.{field_name} is required.")

    for field_name, field_value in value.items():
        if field_name not in properties:
            raise ToolValidationError(f"{label}.{field_name} is not allowed.")
        expected_type = properties[field_name].get("type")
        if expected_type is None:
            continue
        python_type = TYPE_MAP.get(expected_type)
        if python_type is None:
            raise ToolValidationError(f"Unsupported schema type '{expected_type}'.")
        if expected_type == "integer" and isinstance(field_value, bool):
            raise ToolValidationError(f"{label}.{field_name} must be an integer.")
        if not isinstance(field_value, python_type):
            raise ToolValidationError(f"{label}.{field_name} must be {expected_type}.")
