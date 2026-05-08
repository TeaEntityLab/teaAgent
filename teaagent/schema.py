from __future__ import annotations

from typing import Any, Union

from teaagent.errors import ToolValidationError

TYPE_MAP: dict[str, Union[type[Any], tuple[type[Any], ...]]] = {
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
    validate_schema_value(schema, value, label=label)


def validate_schema_value(schema: dict[str, Any], value: Any, *, label: str) -> None:
    expected_type = schema.get("type")
    if expected_type is None:
        return
    python_type = TYPE_MAP.get(expected_type)
    if python_type is None:
        raise ToolValidationError(f"Unsupported schema type '{expected_type}'.")
    if expected_type == "integer" and isinstance(value, bool):
        raise ToolValidationError(f"{label} must be an integer.")
    if not isinstance(value, python_type):
        article = "an " if expected_type == "object" else ""
        raise ToolValidationError(f"{label} must be {article}{expected_type}.")

    if expected_type == "array" and "items" in schema:
        item_schema = schema["items"]
        if not isinstance(item_schema, dict):
            raise ToolValidationError(f"{label}.items must be a schema object.")
        for index, item in enumerate(value):
            validate_schema_value(item_schema, item, label=f"{label}[{index}]")
    if expected_type == "object" and ("properties" in schema or "required" in schema):
        validate_object_fields(schema, value, label=label)


def validate_object_fields(schema: dict[str, Any], value: Any, *, label: str) -> None:
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
        validate_schema_value(properties[field_name], field_value, label=f"{label}.{field_name}")
