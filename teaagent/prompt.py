from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Optional

from teaagent.errors import ToolValidationError
from teaagent.runner import FinalAnswer, ToolRequest
from teaagent.tools import ToolRegistry


DECISION_INSTRUCTIONS = """You are TeaAgent, a coding-agent harness.
You must respond with exactly one JSON object and no prose.

Decision schema:
{"type":"tool","tool_name":"name","arguments":{},"call_id":"stable-id"}
{"type":"final","content":"answer"}

Rules:
- Use tools when workspace inspection or execution is needed.
- Use final only when the task is complete or cannot proceed.
- Do not invent tool names or arguments.
- Destructive tools may be blocked unless the user explicitly enables destructive actions.
"""


@dataclass(frozen=True)
class PromptBundle:
    system: str
    user: str


def assemble_agent_prompt(
    *,
    task: str,
    context: dict[str, Any],
    registry: ToolRegistry,
    project_instructions: Optional[str] = None,
    task_spec: Optional[str] = None,
) -> PromptBundle:
    system_parts = [DECISION_INSTRUCTIONS, "Available tools:", json.dumps(registry.mcp_metadata(), indent=2, sort_keys=True)]
    if project_instructions:
        system_parts.append("Project instructions:")
        system_parts.append(project_instructions)
    return PromptBundle(
        system="\n\n".join(system_parts),
        user=json.dumps(
            {
                "task": task,
                "task_spec": task_spec,
                "memories": context.get("memories", []),
                "observations": context.get("observations", []),
            },
            indent=2,
            sort_keys=True,
        ),
    )


def load_project_instructions(root: str | Path) -> str:
    path = Path(root) / "AGENTS.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def parse_model_decision(text: str) -> ToolRequest | FinalAnswer:
    payload = extract_json_object(text)
    decision_type = payload.get("type")
    if decision_type == "final":
        content = payload.get("content")
        if not isinstance(content, str):
            raise ToolValidationError("final decision requires string content")
        return FinalAnswer(content=content)
    if decision_type == "tool":
        tool_name = payload.get("tool_name")
        arguments = payload.get("arguments")
        call_id = payload.get("call_id")
        if not isinstance(tool_name, str):
            raise ToolValidationError("tool decision requires string tool_name")
        if not isinstance(arguments, dict):
            raise ToolValidationError("tool decision requires object arguments")
        if call_id is not None and not isinstance(call_id, str):
            raise ToolValidationError("tool decision call_id must be string")
        return ToolRequest(tool_name=tool_name, arguments=arguments, call_id=call_id or f"model-{tool_name}")
    raise ToolValidationError("decision type must be 'tool' or 'final'")


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return json.loads(stripped)
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ToolValidationError("model response did not contain a JSON object")
