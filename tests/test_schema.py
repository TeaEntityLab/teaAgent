from __future__ import annotations

import unittest

from teaagent.errors import ToolValidationError
from teaagent.schema import validate_object_schema


class SchemaValidationTests(unittest.TestCase):
    def test_accepts_valid_object_with_required_field(self) -> None:
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        validate_object_schema(schema, {"name": "hello"}, label="input")

    def test_accepts_valid_object_with_optional_field_omitted(self) -> None:
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": [],
        }
        validate_object_schema(schema, {}, label="input")

    def test_rejects_non_object_schema(self) -> None:
        schema = {"type": "array", "items": {"type": "string"}}
        with self.assertRaises(ToolValidationError) as ctx:
            validate_object_schema(schema, {}, label="input")
        self.assertIn("object schema", str(ctx.exception))

    def test_rejects_non_dict_value(self) -> None:
        schema = {"type": "object", "properties": {}, "required": []}
        with self.assertRaises(ToolValidationError) as ctx:
            validate_object_schema(schema, ["not", "a", "dict"], label="input")
        self.assertIn("must be an object", str(ctx.exception))

    def test_rejects_missing_required_field(self) -> None:
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }
        with self.assertRaises(ToolValidationError) as ctx:
            validate_object_schema(schema, {}, label="tool")
        self.assertIn("path", str(ctx.exception))
        self.assertIn("required", str(ctx.exception))

    def test_rejects_unknown_field(self) -> None:
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": [],
        }
        with self.assertRaises(ToolValidationError) as ctx:
            validate_object_schema(schema, {"name": "x", "extra": 1}, label="tool.x")
        self.assertIn("extra", str(ctx.exception))
        self.assertIn("not allowed", str(ctx.exception))

    def test_rejects_unsupported_schema_type(self) -> None:
        schema = {
            "type": "object",
            "properties": {"data": {"type": "decimal"}},
            "required": ["data"],
        }
        with self.assertRaises(ToolValidationError) as ctx:
            validate_object_schema(schema, {"data": 3.14}, label="tool")
        self.assertIn("decimal", str(ctx.exception))

    def test_rejects_bool_when_integer_expected(self) -> None:
        schema = {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
            "required": ["count"],
        }
        with self.assertRaises(ToolValidationError) as ctx:
            validate_object_schema(schema, {"count": True}, label="tool")
        self.assertIn("integer", str(ctx.exception))

    def test_rejects_wrong_type(self) -> None:
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        with self.assertRaises(ToolValidationError) as ctx:
            validate_object_schema(schema, {"name": 42}, label="input")
        self.assertIn("string", str(ctx.exception))

    def test_accepts_string_or_integer_when_no_type_specified(self) -> None:
        schema = {
            "type": "object",
            "properties": {"data": {}},
            "required": ["data"],
        }
        validate_object_schema(schema, {"data": "anything"}, label="input")

    def test_accepts_array_field(self) -> None:
        schema = {
            "type": "object",
            "properties": {"items": {"type": "array"}},
            "required": ["items"],
        }
        validate_object_schema(schema, {"items": [1, 2, 3]}, label="input")

    def test_accepts_boolean_field(self) -> None:
        schema = {
            "type": "object",
            "properties": {"flag": {"type": "boolean"}},
            "required": ["flag"],
        }
        validate_object_schema(schema, {"flag": False}, label="input")

    def test_accepts_number_as_int_or_float(self) -> None:
        schema = {
            "type": "object",
            "properties": {"x": {"type": "number"}, "y": {"type": "number"}},
            "required": ["x", "y"],
        }
        validate_object_schema(schema, {"x": 1, "y": 2.5}, label="input")

    def test_label_appears_in_error_message(self) -> None:
        with self.assertRaises(ToolValidationError) as ctx:
            validate_object_schema(SchemaValidationTests._non_object_schema(), {}, label="my_tool.input")
        self.assertIn("my_tool.input", str(ctx.exception))

    @staticmethod
    def _non_object_schema():
        return {"type": "array"}


if __name__ == "__main__":
    unittest.main()
