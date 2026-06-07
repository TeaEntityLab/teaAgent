from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from teaagent.policy import parse_permission_mode
from teaagent.subagents._types import SubagentDef

SUBAGENTS_DIR = '.teaagent/subagents'
_SUPPORTED_SUFFIXES = {'.yaml', '.yml', '.json', '.md'}
_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)


def load_subagent_defs(root: Path) -> dict[str, SubagentDef]:
    subagent_dir = root / SUBAGENTS_DIR
    if not subagent_dir.is_dir():
        return {}
    defs: dict[str, SubagentDef] = {}
    for f in sorted(subagent_dir.iterdir()):
        if not f.is_file() or f.suffix.lower() not in _SUPPORTED_SUFFIXES:
            continue
        if f.suffix.lower() == '.md':
            data = _load_markdown_frontmatter(f)
        else:
            data = _load_data_file(f)
        if not isinstance(data, dict):
            continue
        name = data.get('name')
        if not isinstance(name, str) or not name.strip():
            continue
        permission_mode = None
        pm_value = data.get('permission_mode')
        if isinstance(pm_value, str) and pm_value.strip():
            permission_mode = parse_permission_mode(pm_value)
        tools = data.get('tools')
        tool_whitelist = None
        if isinstance(tools, list):
            names = [str(item).strip() for item in tools if str(item).strip()]
            if names:
                tool_whitelist = frozenset(names)
        disallowed = data.get('disallowed_tools', data.get('disallowedTools'))
        disallowed_tools = None
        if isinstance(disallowed, list):
            dnames = [str(item).strip() for item in disallowed if str(item).strip()]
            if dnames:
                disallowed_tools = frozenset(dnames)
        isolation = str(data.get('isolation', 'shared'))
        background = bool(data.get('background', False))
        effort = data.get('effort')
        system_prompt = str(data.get('system_prompt', ''))
        if not system_prompt:
            system_prompt = str(data.get('prompt', ''))
        defs[name] = SubagentDef(
            name=name,
            description=str(data.get('description', '')),
            system_prompt=system_prompt,
            model=(
                str(data['model']) if 'model' in data and data.get('model') else None
            ),
            permission_mode=permission_mode,
            max_iterations=int(data.get('max_iterations', 5)),
            max_tool_calls=int(data.get('max_tool_calls', 8)),
            tool_whitelist=tool_whitelist,
            disallowed_tools=disallowed_tools,
            max_depth=int(data.get('max_depth', 1)),
            isolation=isolation,
            background=background,
            effort=effort,
        )
    return defs


def _load_markdown_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding='utf-8')
    match = _FRONTMATTER_RE.match(text)
    if not match:
        frontmatter_text = ''
        body = text
    else:
        frontmatter_text = match.group(1)
        body = text[match.end() :]
    data: dict[str, Any] = {}
    if frontmatter_text:
        try:
            import yaml

            parsed = yaml.safe_load(frontmatter_text)
        except ModuleNotFoundError:
            parsed = _load_simple_yaml(frontmatter_text)
        if isinstance(parsed, dict):
            data.update(parsed)
    if 'system_prompt' not in data and body.strip():
        data['system_prompt'] = body.strip()
    return data


def _load_data_file(path: Path) -> Any:
    text = path.read_text(encoding='utf-8')
    if path.suffix.lower() == '.json':
        return json.loads(text)
    try:
        import yaml

        return yaml.safe_load(text)
    except ModuleNotFoundError:
        return _load_simple_yaml(text)


def _load_simple_yaml(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            i += 1
            continue
        if ':' not in line:
            i += 1
            continue
        key, raw_value = line.split(':', 1)
        key = key.strip()
        value = raw_value.strip()
        if value == '|':
            block: list[str] = []
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if nxt.startswith('  '):
                    block.append(nxt[2:])
                    i += 1
                    continue
                break
            data[key] = '\n'.join(block)
            continue
        if value == '':
            items: list[str] = []
            i += 1
            while i < len(lines):
                nxt = lines[i]
                nstrip = nxt.strip()
                if not nstrip:
                    i += 1
                    continue
                if not nstrip.startswith('- '):
                    break
                items.append(nstrip[2:].strip())
                i += 1
            data[key] = items
            continue
        data[key] = _coerce_scalar(value)
        i += 1
    return data


def _coerce_scalar(value: str) -> Any:
    low = value.lower()
    if low in {'true', 'false'}:
        return low == 'true'
    if low in {'null', 'none'}:
        return None
    if value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
        return int(value)
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value
