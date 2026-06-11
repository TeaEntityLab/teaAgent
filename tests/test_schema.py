from __future__ import annotations

import pytest

from teaagent.schema import validate_object_schema
from teaagent.types import ToolValidationError


def test_accepts_valid_object_with_required_field() -> None:
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    }
    validate_object_schema(schema, {'name': 'hello'}, label='input')


def test_accepts_valid_object_with_optional_field_omitted() -> None:
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': [],
    }
    validate_object_schema(schema, {}, label='input')


def test_rejects_non_object_schema() -> None:
    schema = {'type': 'array', 'items': {'type': 'string'}}
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {}, label='input')
    assert 'object schema' in str(ctx.value)


def test_rejects_non_dict_value() -> None:
    schema = {'type': 'object', 'properties': {}, 'required': []}
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, ['not', 'a', 'dict'], label='input')
    assert 'must be an object' in str(ctx.value)


def test_rejects_missing_required_field() -> None:
    schema = {
        'type': 'object',
        'properties': {'path': {'type': 'string'}},
        'required': ['path'],
    }
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {}, label='tool')
    assert 'path' in str(ctx.value)
    assert 'required' in str(ctx.value)


def test_rejects_unknown_field() -> None:
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': [],
    }
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {'name': 'x', 'extra': 1}, label='tool.x')
    assert 'extra' in str(ctx.value)
    assert 'not allowed' in str(ctx.value)


def test_rejects_unsupported_schema_type() -> None:
    schema = {
        'type': 'object',
        'properties': {'data': {'type': 'decimal'}},
        'required': ['data'],
    }
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {'data': 3.14}, label='tool')
    assert 'decimal' in str(ctx.value)


def test_rejects_bool_when_integer_expected() -> None:
    schema = {
        'type': 'object',
        'properties': {'count': {'type': 'integer'}},
        'required': ['count'],
    }
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {'count': True}, label='tool')
    assert 'integer' in str(ctx.value)


def test_rejects_wrong_type() -> None:
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    }
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {'name': 42}, label='input')
    assert 'string' in str(ctx.value)


def test_accepts_string_or_integer_when_no_type_specified() -> None:
    schema = {
        'type': 'object',
        'properties': {'data': {}},
        'required': ['data'],
    }
    validate_object_schema(schema, {'data': 'anything'}, label='input')


def test_accepts_array_field() -> None:
    schema = {
        'type': 'object',
        'properties': {'items': {'type': 'array'}},
        'required': ['items'],
    }
    validate_object_schema(schema, {'items': [1, 2, 3]}, label='input')


def test_validates_array_item_type_when_items_schema_is_present() -> None:
    schema = {
        'type': 'object',
        'properties': {'items': {'type': 'array', 'items': {'type': 'string'}}},
        'required': ['items'],
    }

    validate_object_schema(schema, {'items': ['a', 'b']}, label='input')

    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {'items': ['a', 2]}, label='input')
    assert 'input.items[1]' in str(ctx.value)
    assert 'string' in str(ctx.value)


def test_validates_nested_object_fields() -> None:
    schema = {
        'type': 'object',
        'properties': {
            'item': {
                'type': 'object',
                'properties': {'name': {'type': 'string'}},
                'required': ['name'],
            }
        },
        'required': ['item'],
    }

    validate_object_schema(schema, {'item': {'name': 'ok'}}, label='input')

    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {'item': {'name': 1}}, label='input')
    assert 'input.item.name' in str(ctx.value)


def test_accepts_boolean_field() -> None:
    schema = {
        'type': 'object',
        'properties': {'flag': {'type': 'boolean'}},
        'required': ['flag'],
    }
    validate_object_schema(schema, {'flag': False}, label='input')


def test_accepts_number_as_int_or_float() -> None:
    schema = {
        'type': 'object',
        'properties': {'x': {'type': 'number'}, 'y': {'type': 'number'}},
        'required': ['x', 'y'],
    }
    validate_object_schema(schema, {'x': 1, 'y': 2.5}, label='input')


def test_label_appears_in_error_message() -> None:
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(_non_object_schema(), {}, label='my_tool.input')
    assert 'my_tool.input' in str(ctx.value)


def _non_object_schema():
    return {'type': 'array'}
