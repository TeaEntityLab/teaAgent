from __future__ import annotations

import unittest

from teaagent.errors import ToolValidationError
from teaagent.tools import ToolAnnotations, ToolRegistry


class ToolRegistryRegistrationTests(unittest.TestCase):
    def _valid_instance(self) -> ToolRegistry:
        return ToolRegistry()

    def _valid_kwargs(self, **overrides):
        kwargs = dict(
            name="my_tool",
            description="A test tool.",
            input_schema={"type": "object", "properties": {}, "required": []},
            output_schema={"type": "object", "properties": {}, "required": []},
            annotations=ToolAnnotations(read_only=True),
            handler=lambda args: {"ok": True},
        )
        kwargs.update(overrides)
        return kwargs

    def test_register_and_get_by_name(self) -> None:
        registry = self._valid_instance()
        registry.register(**self._valid_kwargs())

        tool = registry.get("my_tool")
        self.assertEqual(tool.name, "my_tool")
        self.assertEqual(tool.description, "A test tool.")

    def test_register_multiple_distinct_tools(self) -> None:
        registry = self._valid_instance()
        registry.register(**self._valid_kwargs(name="tool_a"))
        registry.register(**self._valid_kwargs(name="tool_b"))
        registry.register(**self._valid_kwargs(name="tool_c"))

        self.assertEqual(len(registry._tools), 3)

    def test_register_rejects_empty_name(self) -> None:
        registry = self._valid_instance()
        with self.assertRaises(ValueError) as ctx:
            registry.register(**self._valid_kwargs(name=""))
        self.assertIn("non-empty", str(ctx.exception))

    def test_register_rejects_name_with_whitespace(self) -> None:
        registry = self._valid_instance()
        with self.assertRaises(ValueError) as ctx:
            registry.register(**self._valid_kwargs(name="bad name"))
        self.assertIn("no spaces", str(ctx.exception))

    def test_register_rejects_duplicate_name(self) -> None:
        registry = self._valid_instance()
        registry.register(**self._valid_kwargs(name="dup"))

        with self.assertRaises(ValueError) as ctx:
            registry.register(**self._valid_kwargs(name="dup"))
        self.assertIn("already registered", str(ctx.exception))

    def test_register_rejects_empty_description(self) -> None:
        registry = self._valid_instance()
        with self.assertRaises(ValueError) as ctx:
            registry.register(**self._valid_kwargs(description=""))
        self.assertIn("description is required", str(ctx.exception))

    def test_get_unknown_tool_raises_key_error(self) -> None:
        registry = self._valid_instance()
        with self.assertRaises(KeyError) as ctx:
            registry.get("nonexistent")
        self.assertIn("not registered", str(ctx.exception))

    def test_execute_validates_input_and_runs_handler(self) -> None:
        registry = self._valid_instance()
        registry.register(**self._valid_kwargs(
            name="echo",
            input_schema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
            output_schema={
                "type": "object",
                "properties": {"reply": {"type": "string"}},
                "required": ["reply"],
            },
            handler=lambda args: {"reply": args["message"]},
        ))

        result = registry.execute("echo", {"message": "hello"})
        self.assertEqual(result, {"reply": "hello"})

    def test_execute_validates_array_output_items(self) -> None:
        registry = self._valid_instance()
        registry.register(**self._valid_kwargs(
            name="bad_array",
            output_schema={
                "type": "object",
                "properties": {"items": {"type": "array", "items": {"type": "string"}}},
                "required": ["items"],
            },
            handler=lambda args: {"items": ["ok", 1]},
        ))

        with self.assertRaises(ToolValidationError) as ctx:
            registry.execute("bad_array", {})
        self.assertIn("tool.bad_array.output.items[1]", str(ctx.exception))

    def test_execute_unknown_tool_raises_key_error(self) -> None:
        registry = self._valid_instance()
        with self.assertRaises(KeyError):
            registry.execute("ghost", {})

    def test_mcp_metadata_returns_list_of_tool_dicts(self) -> None:
        registry = self._valid_instance()
        registry.register(**self._valid_kwargs(name="tool_a"))
        registry.register(**self._valid_kwargs(name="tool_b"))
        metadata = registry.mcp_metadata()

        self.assertEqual(len(metadata), 2)
        self.assertEqual(metadata[0]["name"], "tool_a")
        self.assertIn("readOnlyHint", metadata[0]["annotations"])

    def test_mcp_metadata_empty_registry(self) -> None:
        registry = self._valid_instance()
        self.assertEqual(registry.mcp_metadata(), [])


if __name__ == "__main__":
    unittest.main()
