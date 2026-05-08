from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from teaagent.prompt import (
    PromptBundle,
    assemble_agent_prompt,
    extract_json_object,
    load_project_instructions,
    parse_model_decision,
)
from teaagent.errors import ToolValidationError
from teaagent.runner import FinalAnswer, ToolRequest
from teaagent.tools import ToolAnnotations, ToolRegistry
from teaagent.workspace_tools import build_workspace_tool_registry


class ExtractJSONObjectTests(unittest.TestCase):
    def test_parses_bare_json_object(self) -> None:
        result = extract_json_object('{"a": 1}')
        self.assertEqual(result, {"a": 1})

    def test_parses_fenced_json_with_language_tag(self) -> None:
        result = extract_json_object('pre\n```json\n{"key":"val"}\n```\npost')
        self.assertEqual(result, {"key": "val"})

    def test_parses_fenced_json_without_language_tag(self) -> None:
        result = extract_json_object('```\n{"nested":{"inner":true}}\n```')
        self.assertEqual(result, {"nested": {"inner": True}})

    def test_parses_embedded_json_between_braces(self) -> None:
        result = extract_json_object('some text {"type":"tool"} trailing')
        self.assertEqual(result, {"type": "tool"})

    def test_embedded_json_with_multiple_json_objects_fails_with_decode_error(self) -> None:
        with self.assertRaises(json.JSONDecodeError):
            extract_json_object('prefix {"x":1} suffix {"y":2}')

    def test_parses_nested_braces_correctly(self) -> None:
        result = extract_json_object('prefix {"a":{"b":3}}')
        self.assertEqual(result, {"a": {"b": 3}})

    def test_raises_on_no_json(self) -> None:
        with self.assertRaises(ToolValidationError) as ctx:
            extract_json_object("just plain text")
        self.assertIn("JSON object", str(ctx.exception))

    def test_raises_on_bare_braces_with_invalid_json(self) -> None:
        with self.assertRaises(json.JSONDecodeError):
            extract_json_object("{invalid json}")

    def test_raises_on_fenced_block_with_invalid_json(self) -> None:
        with self.assertRaises(json.JSONDecodeError):
            extract_json_object("```json\n{not valid}\n```")


class LoadProjectInstructionsTests(unittest.TestCase):
    def test_returns_empty_when_no_agents_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = load_project_instructions(tmp)
            self.assertEqual(result, "")

    def test_returns_content_when_agents_md_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "AGENTS.md"
            path.write_text("Project rules here\n", encoding="utf-8")
            result = load_project_instructions(tmp)
            self.assertEqual(result, "Project rules here\n")


class AssembleAgentPromptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = build_workspace_tool_registry()

    def test_returns_prompt_bundle_with_task(self) -> None:
        bundle = assemble_agent_prompt(task="do thing", context={}, registry=self.registry)

        self.assertIsInstance(bundle, PromptBundle)
        self.assertIn("TeaAgent", bundle.system)
        self.assertIn("Available tools", bundle.system)
        self.assertIn("do thing", bundle.user)
        self.assertIn("observations", bundle.user)

    def test_includes_project_instructions_in_system_prompt(self) -> None:
        bundle = assemble_agent_prompt(
            task="x",
            context={},
            registry=self.registry,
            project_instructions="Custom rules.",
        )

        self.assertIn("Project instructions", bundle.system)
        self.assertIn("Custom rules.", bundle.system)

    def test_includes_task_spec_in_user_prompt(self) -> None:
        bundle = assemble_agent_prompt(
            task="x",
            context={"task_spec": "Clarified: do X"},
            registry=self.registry,
            task_spec="Clarified: do X",
        )

        self.assertIn("Clarified: do X", bundle.user)

    def test_includes_memories_in_user_prompt(self) -> None:
        bundle = assemble_agent_prompt(
            task="x",
            context={"memories": [{"id": "m1", "content": "note"}]},
            registry=self.registry,
        )

        self.assertIn("note", bundle.user)

    def test_includes_observations_in_user_prompt(self) -> None:
        bundle = assemble_agent_prompt(
            task="x",
            context={"observations": [{"call_id": "c1", "tool_name": "t", "result": {"ok": True}}]},
            registry=self.registry,
        )

        self.assertIn("ok", bundle.user)

    def test_omits_project_instructions_when_none(self) -> None:
        bundle = assemble_agent_prompt(task="x", context={}, registry=self.registry)

        self.assertNotIn("Project instructions", bundle.system)

    def test_tool_metadata_in_system_prompt(self) -> None:
        registry = ToolRegistry()
        registry.register(
            name="say_hello",
            description="Say hello",
            input_schema={"type": "object", "properties": {}, "required": []},
            output_schema={"type": "object", "properties": {}, "required": []},
            annotations=ToolAnnotations(read_only=True),
            handler=lambda args: {"message": "hello"},
        )
        bundle = assemble_agent_prompt(task="greet", context={}, registry=registry)

        self.assertIn("say_hello", bundle.system)
        self.assertIn("readOnlyHint", bundle.system)


class ParseModelDecisionTests(unittest.TestCase):
    def test_parses_final_decision(self) -> None:
        result = parse_model_decision('{"type":"final","content":"all done"}')
        self.assertIsInstance(result, FinalAnswer)
        self.assertEqual(result.content, "all done")

    def test_parses_tool_decision(self) -> None:
        result = parse_model_decision(
            '{"type":"tool","tool_name":"read","arguments":{"path":"f.txt"},"call_id":"c1"}'
        )
        self.assertIsInstance(result, ToolRequest)
        self.assertEqual(result.tool_name, "read")
        self.assertEqual(result.arguments, {"path": "f.txt"})
        self.assertEqual(result.call_id, "c1")

    def test_tool_without_call_id_generates_default(self) -> None:
        result = parse_model_decision('{"type":"tool","tool_name":"x","arguments":{}}')
        self.assertIsInstance(result, ToolRequest)
        self.assertTrue(result.call_id.startswith("model-x"))

    def test_raises_on_unknown_type(self) -> None:
        with self.assertRaises(ToolValidationError) as ctx:
            parse_model_decision('{"type":"unknown"}')
        self.assertIn("must be 'tool' or 'final'", str(ctx.exception))

    def test_raises_on_final_without_string_content(self) -> None:
        with self.assertRaises(ToolValidationError) as ctx:
            parse_model_decision('{"type":"final","content":42}')
        self.assertIn("string content", str(ctx.exception))

    def test_raises_on_tool_without_string_name(self) -> None:
        with self.assertRaises(ToolValidationError) as ctx:
            parse_model_decision('{"type":"tool","tool_name":123,"arguments":{}}')
        self.assertIn("string tool_name", str(ctx.exception))

    def test_raises_on_tool_without_object_arguments(self) -> None:
        with self.assertRaises(ToolValidationError) as ctx:
            parse_model_decision('{"type":"tool","tool_name":"x","arguments":"bad"}')
        self.assertIn("object arguments", str(ctx.exception))

    def test_raises_on_tool_with_non_string_call_id(self) -> None:
        with self.assertRaises(ToolValidationError) as ctx:
            parse_model_decision('{"type":"tool","tool_name":"x","arguments":{},"call_id":123}')
        self.assertIn("call_id", str(ctx.exception))

    def test_parses_fenced_json_final(self) -> None:
        result = parse_model_decision('```json\n{"type":"final","content":"done"}\n```')
        self.assertIsInstance(result, FinalAnswer)
        self.assertEqual(result.content, "done")

    def test_parses_embedded_json_tool(self) -> None:
        result = parse_model_decision('thinking...\n{"type":"tool","tool_name":"y","arguments":{"a":1}}\ndone')
        self.assertIsInstance(result, ToolRequest)
        self.assertEqual(result.tool_name, "y")


if __name__ == "__main__":
    unittest.main()
