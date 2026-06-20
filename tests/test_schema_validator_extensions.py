from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest

from teaagent.schema import validate_object_schema, validate_schema_value
from teaagent.types import ToolValidationError

# ---------------------------------------------------------------------------
# (a) enum rejects invalid values
# ---------------------------------------------------------------------------


def test_enum_accepts_valid_value() -> None:
    schema = {
        'type': 'object',
        'properties': {'color': {'type': 'string', 'enum': ['red', 'green', 'blue']}},
        'required': ['color'],
    }
    validate_object_schema(schema, {'color': 'green'}, label='input')


def test_enum_rejects_invalid_value() -> None:
    schema = {
        'type': 'object',
        'properties': {'color': {'type': 'string', 'enum': ['red', 'green', 'blue']}},
        'required': ['color'],
    }
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {'color': 'purple'}, label='input')
    assert 'enum' in str(ctx.value).lower() or 'one of' in str(ctx.value)


def test_enum_rejects_wrong_type_value() -> None:
    schema = {
        'type': 'object',
        'properties': {'n': {'enum': [1, 2, 3]}},
        'required': ['n'],
    }
    with pytest.raises(ToolValidationError):
        validate_object_schema(schema, {'n': 4}, label='input')


# ---------------------------------------------------------------------------
# (b) pattern rejects non-matching strings
# ---------------------------------------------------------------------------


def test_pattern_accepts_matching_string() -> None:
    schema = {
        'type': 'object',
        'properties': {'slug': {'type': 'string', 'pattern': r'^[a-z-]+$'}},
        'required': ['slug'],
    }
    validate_object_schema(schema, {'slug': 'hello-world'}, label='input')


def test_pattern_rejects_non_matching_string() -> None:
    schema = {
        'type': 'object',
        'properties': {'slug': {'type': 'string', 'pattern': r'^[a-z-]+$'}},
        'required': ['slug'],
    }
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {'slug': 'Hello World!'}, label='input')
    assert 'pattern' in str(ctx.value).lower()


# ---------------------------------------------------------------------------
# (c) additionalProperties:false rejects extra fields
# ---------------------------------------------------------------------------


def test_additional_properties_false_rejects_extra_field() -> None:
    schema = {
        'type': 'object',
        'additionalProperties': False,
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    }
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {'name': 'x', 'extra': 1}, label='tool')
    assert 'extra' in str(ctx.value)
    assert 'not allowed' in str(ctx.value)


def test_additional_properties_true_allows_extra_fields() -> None:
    schema = {
        'type': 'object',
        'additionalProperties': True,
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    }
    validate_object_schema(schema, {'name': 'x', 'extra': 1}, label='tool')


def test_additional_properties_schema_validates_extra_fields() -> None:
    schema = {
        'type': 'object',
        'additionalProperties': {'type': 'integer'},
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    }
    validate_object_schema(schema, {'name': 'x', 'extra': 1}, label='tool')
    with pytest.raises(ToolValidationError):
        validate_object_schema(schema, {'name': 'x', 'extra': 'bad'}, label='tool')


# ---------------------------------------------------------------------------
# (d) oneOf / anyOf validate correctly
# ---------------------------------------------------------------------------


def test_one_of_accepts_exactly_one_match() -> None:
    schema = {
        'type': 'object',
        'properties': {
            'value': {
                'oneOf': [
                    {'type': 'string'},
                    {'type': 'integer'},
                ]
            }
        },
        'required': ['value'],
    }
    validate_object_schema(schema, {'value': 'hello'}, label='input')
    validate_object_schema(schema, {'value': 42}, label='input')


def test_one_of_rejects_no_match() -> None:
    schema = {
        'type': 'object',
        'properties': {
            'value': {
                'oneOf': [
                    {'type': 'string'},
                    {'type': 'integer'},
                ]
            }
        },
        'required': ['value'],
    }
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {'value': [1, 2]}, label='input')
    assert 'oneOf' in str(ctx.value)


def test_one_of_rejects_multiple_matches() -> None:
    # number matches both integer and number subschemas.
    schema = {
        'type': 'object',
        'properties': {
            'value': {
                'oneOf': [
                    {'type': 'integer'},
                    {'type': 'number'},
                ]
            }
        },
        'required': ['value'],
    }
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {'value': 5}, label='input')
    assert 'oneOf' in str(ctx.value)


def test_any_of_accepts_at_least_one_match() -> None:
    schema = {
        'type': 'object',
        'properties': {
            'value': {
                'anyOf': [
                    {'type': 'string'},
                    {'type': 'integer'},
                ]
            }
        },
        'required': ['value'],
    }
    validate_object_schema(schema, {'value': 'hello'}, label='input')
    validate_object_schema(schema, {'value': 42}, label='input')


def test_any_of_rejects_no_match() -> None:
    schema = {
        'type': 'object',
        'properties': {
            'value': {
                'anyOf': [
                    {'type': 'string'},
                    {'type': 'integer'},
                ]
            }
        },
        'required': ['value'],
    }
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {'value': [1, 2]}, label='input')
    assert 'anyOf' in str(ctx.value)


# ---------------------------------------------------------------------------
# (e) existing type/properties/required behavior is unchanged
# ---------------------------------------------------------------------------


def test_existing_type_check_still_works() -> None:
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    }
    validate_object_schema(schema, {'name': 'ok'}, label='input')
    with pytest.raises(ToolValidationError):
        validate_object_schema(schema, {'name': 42}, label='input')


def test_existing_required_check_still_works() -> None:
    schema = {
        'type': 'object',
        'properties': {'path': {'type': 'string'}},
        'required': ['path'],
    }
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {}, label='tool')
    assert 'required' in str(ctx.value)


def test_existing_array_items_check_still_works() -> None:
    schema = {
        'type': 'object',
        'properties': {'items': {'type': 'array', 'items': {'type': 'string'}}},
        'required': ['items'],
    }
    validate_object_schema(schema, {'items': ['a', 'b']}, label='input')
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {'items': ['a', 2]}, label='input')
    assert 'input.items[1]' in str(ctx.value)


def test_existing_unknown_field_rejection_still_works() -> None:
    # Default (no additionalProperties) remains False for backward compat.
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': [],
    }
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {'name': 'x', 'extra': 1}, label='tool')
    assert 'extra' in str(ctx.value)
    assert 'not allowed' in str(ctx.value)


# ---------------------------------------------------------------------------
# (f) subagent_batch items schema enforces its declared constraints
# ---------------------------------------------------------------------------


def _batch_input_schema() -> dict:
    """Re-declare the subagent_batch input schema shape under test."""
    return {
        'type': 'object',
        'properties': {
            'tasks': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'task': {'type': 'string', 'minLength': 1},
                        'def_name': {'type': 'string'},
                        'max_iterations': {'type': 'integer'},
                        'max_tool_calls': {'type': 'integer'},
                        'isolation': {
                            'type': 'string',
                            'enum': [
                                'shared',
                                'worktree',
                                'directory-snapshot',
                                'docker',
                                'auto',
                            ],
                        },
                    },
                    'required': ['task'],
                },
            },
        },
        'required': ['tasks'],
    }


def test_batch_items_accepts_valid_task() -> None:
    schema = _batch_input_schema()
    validate_object_schema(
        schema, {'tasks': [{'task': 'do thing', 'isolation': 'shared'}]}, label='batch'
    )


def test_batch_items_rejects_missing_task() -> None:
    schema = _batch_input_schema()
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {'tasks': [{'def_name': 'x'}]}, label='batch')
    assert 'task' in str(ctx.value)
    assert 'required' in str(ctx.value)


def test_batch_items_rejects_empty_task_string() -> None:
    schema = _batch_input_schema()
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(schema, {'tasks': [{'task': ''}]}, label='batch')
    assert 'length' in str(ctx.value).lower()


def test_batch_items_rejects_wrong_task_type() -> None:
    schema = _batch_input_schema()
    with pytest.raises(ToolValidationError):
        validate_object_schema(schema, {'tasks': [{'task': 42}]}, label='batch')


def test_batch_items_rejects_extra_field() -> None:
    schema = _batch_input_schema()
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(
            schema, {'tasks': [{'task': 'ok', 'bogus': 1}]}, label='batch'
        )
    assert 'bogus' in str(ctx.value)


def test_batch_items_rejects_invalid_isolation_enum() -> None:
    schema = _batch_input_schema()
    with pytest.raises(ToolValidationError) as ctx:
        validate_object_schema(
            schema,
            {'tasks': [{'task': 'ok', 'isolation': 'space-station'}]},
            label='batch',
        )
    assert 'one of' in str(ctx.value) or 'enum' in str(ctx.value).lower()


def test_batch_items_rejects_non_integer_max_iterations() -> None:
    schema = _batch_input_schema()
    with pytest.raises(ToolValidationError):
        validate_object_schema(
            schema,
            {'tasks': [{'task': 'ok', 'max_iterations': 'fast'}]},
            label='batch',
        )


# ---------------------------------------------------------------------------
# Integration: the real subagent_batch tool enforces its schema at runtime.
# ---------------------------------------------------------------------------


def _make_batch_registry(root: Path) -> Any:
    from unittest.mock import MagicMock

    from teaagent.chat_agent import ChatAgentConfig
    from teaagent.subagents import SubagentManager
    from teaagent.subagents._tools import register_subagent_tools
    from teaagent.types import ToolRegistry

    registry = ToolRegistry()
    config = ChatAgentConfig(root=root)
    adapter = MagicMock()
    adapter.provider = 'fake'
    adapter.complete = MagicMock(
        return_value=MagicMock(
            content='{"type":"final","content":"done"}',
            input_tokens=0,
            output_tokens=0,
            tool_calls=[],
        )
    )
    manager = SubagentManager(root=root, parent_config=config, parent_adapter=adapter)
    register_subagent_tools(
        registry, adapter=adapter, config=config, depth=0, manager=manager
    )
    return registry


def test_real_subagent_batch_rejects_invalid_isolation_via_registry() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        (root / '.teaagent').mkdir(exist_ok=True)
        registry = _make_batch_registry(root)
        with pytest.raises(ToolValidationError):
            registry.execute(
                'subagent_batch',
                {'tasks': [{'task': 'ok', 'isolation': 'space-station'}]},
            )


def test_real_subagent_batch_rejects_missing_task_via_registry() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        (root / '.teaagent').mkdir(exist_ok=True)
        registry = _make_batch_registry(root)
        with pytest.raises(ToolValidationError):
            registry.execute('subagent_batch', {'tasks': [{'def_name': 'x'}]})


# ---------------------------------------------------------------------------
# Bonus: format and $ref (feasible without new dependencies)
# ---------------------------------------------------------------------------


def test_format_rejects_invalid_email() -> None:
    schema = {
        'type': 'object',
        'properties': {'email': {'type': 'string', 'format': 'email'}},
        'required': ['email'],
    }
    validate_object_schema(schema, {'email': 'a@b.com'}, label='input')
    with pytest.raises(ToolValidationError):
        validate_object_schema(schema, {'email': 'not-an-email'}, label='input')


def test_format_ignores_unknown_format() -> None:
    schema = {
        'type': 'object',
        'properties': {'x': {'type': 'string', 'format': 'frobnicate'}},
        'required': ['x'],
    }
    validate_object_schema(schema, {'x': 'anything'}, label='input')


def test_ref_resolves_local_definition() -> None:
    schema: dict = {
        'type': 'object',
        'definitions': {
            'Name': {'type': 'string', 'minLength': 1},
        },
        'properties': {'name': {'$ref': '#/definitions/Name'}},
        'required': ['name'],
    }
    validate_object_schema(schema, {'name': 'ok'}, label='input')
    with pytest.raises(ToolValidationError):
        validate_object_schema(schema, {'name': ''}, label='input')
    with pytest.raises(ToolValidationError):
        validate_object_schema(schema, {'name': 42}, label='input')


def test_validate_schema_value_without_type_still_checks_enum() -> None:
    schema = {'enum': [1, 2, 3]}
    validate_schema_value(schema, 2, label='x')
    with pytest.raises(ToolValidationError):
        validate_schema_value(schema, 9, label='x')
