from __future__ import annotations

import re
from typing import Any, Optional, Union

from teaagent.errors import ToolValidationError

TYPE_MAP: dict[str, Union[type[Any], tuple[type[Any], ...]]] = {
    'array': list,
    'boolean': bool,
    'integer': int,
    'number': (int, float),
    'object': dict,
    'string': str,
}

_EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def validate_object_schema(schema: dict[str, Any], value: Any, *, label: str) -> None:
    """Validate a small JSON-schema subset used by P0 tool contracts."""
    if schema.get('type') != 'object':
        raise ToolValidationError(f'{label} schema must be an object schema.')
    validate_schema_value(
        schema,
        value,
        label=label,
        _definitions=schema.get('definitions', {}),
    )


def _resolve_ref(schema: dict[str, Any], definitions: dict[str, Any]) -> dict[str, Any]:
    """Resolve a ``$ref`` to a local definition if present."""
    ref = schema.get('$ref')
    if ref is not None and isinstance(ref, str) and ref.startswith('#/definitions/'):
        name = ref[len('#/definitions/') :]
        if name in definitions:
            resolved = definitions[name]
            if isinstance(resolved, dict):
                merged = dict(resolved)
                for k, v in schema.items():
                    if k != '$ref' and k not in merged:
                        merged[k] = v
                return merged
    return schema


def validate_schema_value(  # noqa: C901
    schema: dict[str, Any],
    value: Any,
    *,
    label: str,
    _definitions: Optional[dict[str, Any]] = None,
) -> None:
    """Validate *value* against a JSON-schema-like *schema*.

    Supports a practical subset used by P0 tool contracts:
    ``type``, ``properties``, ``required``, ``items``, ``enum``,
    ``pattern``, ``minLength``, ``format``, ``additionalProperties``,
    ``oneOf``, ``anyOf``, and local ``$ref``.
    """
    if _definitions is None:
        _definitions = {}

    # Resolve $ref first
    schema = _resolve_ref(schema, _definitions)

    expected_type = schema.get('type')

    # Type validation
    if expected_type is not None:
        python_type = TYPE_MAP.get(expected_type)
        if python_type is None:
            raise ToolValidationError(f"Unsupported schema type '{expected_type}'.")
        if expected_type == 'integer' and isinstance(value, bool):
            raise ToolValidationError(f'{label} must be an integer.')
        if not isinstance(value, python_type):
            article = 'an ' if expected_type == 'object' else ''
            raise ToolValidationError(f'{label} must be {article}{expected_type}.')

    # Enum check (always, even without type)
    if 'enum' in schema and value not in schema['enum']:
        raise ToolValidationError(f'{label} must be one of {schema["enum"]}')

    # Pattern check (string values only)
    if (
        'pattern' in schema
        and isinstance(value, str)
        and not re.search(schema['pattern'], value)
    ):
        raise ToolValidationError(
            f'{label} does not match pattern {schema["pattern"]!r}'
        )

    # minLength check (string values only)
    if (
        'minLength' in schema
        and isinstance(value, str)
        and len(value) < schema['minLength']
    ):
        raise ToolValidationError(
            f'{label} length {len(value)} is less than minimum {schema["minLength"]}'
        )

    # Format check (string values only)
    if 'format' in schema and isinstance(value, str):
        _validate_format(schema['format'], value, label)

    # oneOf check
    if 'oneOf' in schema:
        matches = sum(
            1
            for subschema in schema['oneOf']
            if _matches_schema(subschema, value, _definitions)
        )
        if matches != 1:
            raise ToolValidationError(
                f'{label} must match exactly one schema (oneOf), matched {matches}'
            )

    # anyOf check
    if 'anyOf' in schema and not any(
        _matches_schema(subschema, value, _definitions) for subschema in schema['anyOf']
    ):
        raise ToolValidationError(f'{label} must match at least one schema (anyOf)')

    # Items validation (arrays)
    if expected_type == 'array' and 'items' in schema:
        item_schema = schema['items']
        if not isinstance(item_schema, dict):
            raise ToolValidationError(f'{label}.items must be a schema object.')
        for index, item in enumerate(value):
            validate_schema_value(
                item_schema,
                item,
                label=f'{label}[{index}]',
                _definitions=_definitions,
            )

    # Object field validation
    if expected_type == 'object' and ('properties' in schema or 'required' in schema):
        validate_object_fields(schema, value, label=label, _definitions=_definitions)


def _matches_schema(
    schema: dict[str, Any],
    value: Any,
    definitions: dict[str, Any],
) -> bool:
    """Check whether *value* validates against *schema* without raising."""
    try:
        validate_schema_value(
            schema, value, label='_internal', _definitions=definitions
        )
        return True
    except Exception:
        return False


def _validate_format(fmt: str, value: str, label: str) -> None:
    """Validate a ``format`` constraint."""
    if fmt == 'email' and not _EMAIL_PATTERN.match(value):
        raise ToolValidationError(f'{label} is not a valid email address')
    # Unknown formats are ignored per JSON Schema spec


def validate_object_fields(
    schema: dict[str, Any],
    value: Any,
    *,
    label: str,
    _definitions: Optional[dict[str, Any]] = None,
) -> None:
    """Validate object fields including ``additionalProperties``."""
    if _definitions is None:
        _definitions = {}

    if not isinstance(value, dict):
        raise ToolValidationError(f'{label} must be an object.')

    properties = schema.get('properties', {})
    required = schema.get('required', [])
    # Default additionalProperties is False for backward compatibility
    additional_props = schema.get('additionalProperties', False)

    for field_name in required:
        if field_name not in value:
            raise ToolValidationError(f'{label}.{field_name} is required.')

    for field_name, field_value in value.items():
        if field_name in properties:
            validate_schema_value(
                properties[field_name],
                field_value,
                label=f'{label}.{field_name}',
                _definitions=_definitions,
            )
        elif additional_props is True:
            pass  # Any extra field is allowed
        elif additional_props is False:
            raise ToolValidationError(f'{label}.{field_name} is not allowed.')
        elif isinstance(additional_props, dict):
            # Validate against the additional property schema
            validate_schema_value(
                additional_props,
                field_value,
                label=f'{label}.{field_name}',
                _definitions=_definitions,
            )
