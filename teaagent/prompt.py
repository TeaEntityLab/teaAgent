from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from teaagent.errors import ToolValidationError
from teaagent.runner import FinalAnswer, ToolRequest
from teaagent.skill_loader import SkillContent, skills_to_prompt_section
from teaagent.tools import ToolRegistry

DECISION_INSTRUCTIONS = """You are TeaAgent, a coding-agent harness.
You must respond with exactly one JSON object and no prose.

Decision schema:
{"type":"tool","tool_name":"name","arguments":{},"call_id":"stable-id"}
{"type":"final","content":"answer"}

Rules:
- If the task is a simple question or chat that does not require workspace access, respond immediately with a final answer.
- Use tools only when you need to inspect or modify files, run commands, or gather information from the workspace.
- Do not use tools to explore the workspace unless the task specifically requires it.
- Use final when you have enough information to answer, or when the task is complete.
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
    skills: Optional[list[SkillContent]] = None,
) -> PromptBundle:
    system_parts = [
        DECISION_INSTRUCTIONS,
        'Available tools:',
        json.dumps(registry.mcp_metadata(), indent=2, sort_keys=True),
    ]
    if project_instructions:
        system_parts.append('Project instructions:')
        system_parts.append(project_instructions)
    if skills:
        skill_section = skills_to_prompt_section(skills)
        if skill_section:
            system_parts.append(skill_section)
    return PromptBundle(
        system='\n\n'.join(system_parts),
        user=json.dumps(
            {
                'task': task,
                'task_spec': task_spec,
                'lsp_context': context.get('lsp_context', ''),
                'memories': context.get('memories', []),
                'observations': context.get('observations', []),
            },
            indent=2,
            sort_keys=True,
        ),
    )


def load_project_instructions(root: str | Path) -> str:
    resolved = Path(root).resolve()
    start_dir = resolved if resolved.is_dir() else resolved.parent
    filenames = ('AGENTS.override.md', 'AGENTS.md', 'CLAUDE.md', 'AGENT.md')
    parts: list[str] = []

    for directory in reversed(start_dir.parents):
        for filename in filenames:
            path = directory / filename
            if path.exists():
                parts.append(path.read_text(encoding='utf-8'))
    for filename in filenames:
        path = start_dir / filename
        if path.exists():
            parts.append(path.read_text(encoding='utf-8'))
    return '\n\n'.join(part for part in parts if part.strip())


def parse_model_decision(text: str) -> ToolRequest | FinalAnswer:
    payload = extract_json_object(text)
    decision_type = payload.get('type')
    if decision_type == 'final':
        content = payload.get('content')
        if not isinstance(content, str):
            raise ToolValidationError('final decision requires string content')
        return FinalAnswer(content=content)
    if decision_type == 'tool':
        tool_name = payload.get('tool_name')
        arguments = payload.get('arguments')
        call_id = payload.get('call_id')
        if not isinstance(tool_name, str):
            raise ToolValidationError('tool decision requires string tool_name')
        if not isinstance(arguments, dict):
            raise ToolValidationError('tool decision requires object arguments')
        if call_id is not None and not isinstance(call_id, str):
            raise ToolValidationError('tool decision call_id must be string')
        return ToolRequest(
            tool_name=tool_name,
            arguments=arguments,
            call_id=call_id or f'model-{tool_name}',
        )
    raise ToolValidationError("decision type must be 'tool' or 'final'")


def extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != '{':
            continue
        try:
            payload, _end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ToolValidationError('model response did not contain a JSON object')
