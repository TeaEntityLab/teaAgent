from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from teaagent.errors import ToolValidationError
from teaagent.runner import FinalAnswer, ToolRequest
from teaagent.skill_loader import (
    SkillContent,
    SkillIndexEntry,
    skill_index_to_prompt_section,
    skills_to_prompt_section,
)
from teaagent.tools import ToolRegistry

logger = logging.getLogger(__name__)


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

DECISION_JSON_SCHEMA: dict[str, Any] = {
    'type': 'object',
    'oneOf': [
        {
            'type': 'object',
            'properties': {
                'type': {'const': 'tool'},
                'tool_name': {'type': 'string'},
                'arguments': {'type': 'object'},
                'call_id': {'type': 'string'},
            },
            'required': ['type', 'tool_name', 'arguments'],
            'additionalProperties': False,
        },
        {
            'type': 'object',
            'properties': {
                'type': {'const': 'final'},
                'content': {'type': 'string'},
            },
            'required': ['type', 'content'],
            'additionalProperties': False,
        },
    ],
}


@dataclass(frozen=True)
class PromptBundle:
    system: str
    user: str


async def run_aci_injector(
    task: str,
    retriever: Any,
    cache_db_path: str,
    timeout_ms: int = 1500,
) -> str:  # pragma: no cover
    """Run ACI (Anticipatory Context Injection) with timeout protection.

    Performs parallel RAG retrieval and cache lookup. If retrieval exceeds
    timeout, degrades to cache-only injection to ensure zero latency.

    Args:
        task: Current task description.
        retriever: RAG retriever instance (e.g., InMemoryRetriever).
        cache_db_path: Path to SQLite cache database.
        timeout_ms: Hard timeout in milliseconds (default 1500ms).

    Returns:
        String containing injected context for system prompt.
    """

    async def fetch_rag_context() -> str:
        await asyncio.sleep(0)
        results = retriever.search(task, limit=3)
        if not results:
            return ''
        return '\n'.join(
            f'- {r.document.text[:200]}... (score: {r.score:.2f})' for r in results
        )

    async def fetch_cache_context() -> str:
        await asyncio.sleep(0)
        try:
            conn = sqlite3.connect(cache_db_path)
            cursor = conn.cursor()
            cursor.execute(
                'SELECT text, source FROM prefetch_cache ORDER BY created_at DESC LIMIT 5'
            )
            rows = cursor.fetchall()
            conn.close()
            if not rows:
                return ''
            return '\n'.join(
                f'- Cache [{source}]: {text[:150]}...' for text, source in rows
            )
        except (OSError, ValueError, sqlite3.Error) as exc:
            logger.debug('Cache context fetch failed: %s', exc)
            return ''

    try:
        rag_task = asyncio.create_task(fetch_rag_context())
        cache_task = asyncio.create_task(fetch_cache_context())

        done, pending = await asyncio.wait(  # type: ignore
            [rag_task, cache_task],
            timeout=timeout_ms / 1000,
            return_when=asyncio.ALL_COMPLETED,
        )

        for task in pending:  # type: ignore
            task.cancel()  # type: ignore

        context_parts = []
        if rag_task in done:
            rag_result = rag_task.result()
            if rag_result:
                context_parts.append(f'RAG Context:\n{rag_result}')

        if cache_task in done:
            cache_result = cache_task.result()
            if cache_result:
                context_parts.append(f'Cache Context:\n{cache_result}')

        if context_parts:
            return '\n\n'.join(context_parts)
        return ''

    except asyncio.TimeoutError:
        cache_result = await fetch_cache_context()
        if cache_result:
            return f'Cache Context (degraded):\n{cache_result}'
        return ''
    except (OSError, ValueError, TypeError, ConnectionError) as exc:
        logger.debug('Async context fetch failed: %s', exc)
        return ''


def run_aci_injector_sync(
    task: str,
    retriever: Any,
    cache_db_path: str,
    timeout_ms: int = 1500,
) -> str:
    """Synchronous wrapper for run_aci_injector."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(
        run_aci_injector(task, retriever, cache_db_path, timeout_ms)
    )


def assemble_agent_prompt(
    *,
    task: str,
    context: dict[str, Any],
    registry: ToolRegistry,
    project_instructions: Optional[str] = None,
    task_spec: Optional[str] = None,
    skills: Optional[list[SkillContent]] = None,
    skill_index: Optional[list[SkillIndexEntry]] = None,
    aci_retriever: Optional[Any] = None,
    aci_cache_db: Optional[str] = None,
    decision_summary: str = '',
) -> PromptBundle:
    system_parts = [
        DECISION_INSTRUCTIONS,
        'Available tools:',
        json.dumps(registry.mcp_metadata(), indent=2, sort_keys=True),
    ]

    if aci_retriever and aci_cache_db:
        aci_context = run_aci_injector_sync(task, aci_retriever, aci_cache_db)
        if aci_context:
            system_parts.append(f'Anticipatory Context:\n{aci_context}')

    if project_instructions:
        system_parts.append('Project instructions:')
        system_parts.append(project_instructions)
    if decision_summary:
        system_parts.append(decision_summary)
    if skill_index:
        index_section = skill_index_to_prompt_section(skill_index)
        if index_section:
            system_parts.append(index_section)
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


def load_project_instructions(
    root: str | Path, affected_paths: Optional[list[Path]] = None
) -> str:
    """Load project instructions from AGENTS.md and modular .teaagent/rules/ directory.

    Args:
        root: Project root directory.
        affected_paths: Optional list of file paths being modified. If provided, only loads
            relevant modular rules based on path matching.

    Returns:
        Combined project instructions as a single string.
    """
    resolved = Path(root).resolve()
    start_dir = resolved if resolved.is_dir() else resolved.parent
    filenames = ('AGENTS.override.md', 'AGENTS.md', 'CLAUDE.md', 'AGENT.md')
    parts: list[str] = []

    # Load base project instructions
    for directory in reversed(start_dir.parents):
        for filename in filenames:
            path = directory / filename
            if path.exists():
                parts.append(path.read_text(encoding='utf-8'))
    for filename in filenames:
        path = start_dir / filename
        if path.exists():
            parts.append(path.read_text(encoding='utf-8'))

    # Load modular rules from .teaagent/rules/
    rules_dir = start_dir / '.teaagent' / 'rules'
    if rules_dir.exists() and rules_dir.is_dir():
        if affected_paths:
            # Path-aware rule injection: only load rules relevant to affected paths
            relevant_rules = _load_relevant_rules(rules_dir, affected_paths, start_dir)
            parts.extend(relevant_rules)
        else:
            # Load all rules if no specific paths provided
            for rule_file in sorted(rules_dir.glob('*.md')):
                parts.append(rule_file.read_text(encoding='utf-8'))

    return '\n\n'.join(part for part in parts if part.strip())


def _load_relevant_rules(
    rules_dir: Path, affected_paths: list[Path], project_root: Path
) -> list[str]:
    """Load modular rules based on path matching.

    Args:
        rules_dir: Directory containing modular rule files.
        affected_paths: List of file paths being modified.
        project_root: Project root directory for resolving relative paths.

    Returns:
        List of relevant rule file contents.
    """
    relevant_rules: list[str] = []

    for rule_file in sorted(rules_dir.glob('*.md')):
        rule_name = rule_file.stem
        rule_content = rule_file.read_text(encoding='utf-8')

        # Check if any affected path matches this rule
        # Rule files can be named after directories (e.g., db.md for teaagent/db/)
        # or contain path patterns in their content
        is_relevant = False

        for affected_path in affected_paths:
            try:
                rel_path = affected_path.relative_to(project_root)
                # Check if rule name matches any part of the path
                if rule_name in str(rel_path):
                    is_relevant = True
                    break
                # Check if rule content mentions the path
                if str(rel_path) in rule_content:
                    is_relevant = True
                    break
            except ValueError:
                # Path is outside project root, include rule as safety measure
                is_relevant = True
                break

        if is_relevant:
            relevant_rules.append(rule_content)

    return relevant_rules


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
            repaired = _try_repair_json_at(text, index)
            if repaired is None:
                continue
            return repaired
        if isinstance(payload, dict):
            return payload
    raise ToolValidationError('model response did not contain a JSON object')


def _try_repair_json_at(text: str, start: int) -> dict[str, Any] | None:
    candidate = _slice_json_object_candidate(text, start)
    if candidate is None:
        return None
    repaired = _repair_json_text(candidate)
    try:
        payload = json.loads(repaired)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _slice_json_object_candidate(text: str, start: int) -> str | None:
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
                continue
            if ch == '\\':
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
            if depth < 0:
                return None
    return None


def _repair_json_text(candidate: str) -> str:
    repaired = candidate
    # Quote bare object keys: {type:"final"} -> {"type":"final"}
    repaired = re.sub(
        r'([{\[,]\s*)([A-Za-z_][A-Za-z0-9_\-]*)(\s*:)', r'\1"\2"\3', repaired
    )
    # Remove trailing commas before object/array close.
    repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)
    return repaired
