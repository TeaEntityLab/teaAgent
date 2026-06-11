from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from teaagent.prompt import (
    PromptBundle,
    assemble_agent_prompt,
    extract_json_object,
    load_project_instructions,
    parse_model_decision,
)
from teaagent.runner import FinalAnswer, ToolRequest
from teaagent.types import ToolAnnotations, ToolRegistry, ToolValidationError
from teaagent.workspace_tools import build_workspace_tool_registry


@pytest.fixture
def registry():
    return build_workspace_tool_registry()


def test_parses_bare_json_object() -> None:
    result = extract_json_object('{"a": 1}')
    assert result == {'a': 1}


def test_parses_fenced_json_with_language_tag() -> None:
    result = extract_json_object('pre\n```json\n{"key":"val"}\n```\npost')
    assert result == {'key': 'val'}


def test_parses_fenced_json_without_language_tag() -> None:
    result = extract_json_object('```\n{"nested":{"inner":true}}\n```')
    assert result == {'nested': {'inner': True}}


def test_parses_embedded_json_between_braces() -> None:
    result = extract_json_object('some text {"type":"tool"} trailing')
    assert result == {'type': 'tool'}


def test_embedded_json_with_multiple_json_objects_returns_first_object() -> None:
    result = extract_json_object('prefix {"x":1} suffix {"y":2}')
    assert result == {'x': 1}


def test_ignores_invalid_brace_before_valid_object() -> None:
    result = extract_json_object(
        'thinking {not json} then {"type":"final","content":"ok"}'
    )
    assert result == {'type': 'final', 'content': 'ok'}


def test_parses_nested_braces_correctly() -> None:
    result = extract_json_object('prefix {"a":{"b":3}}')
    assert result == {'a': {'b': 3}}


def test_raises_on_no_json() -> None:
    with pytest.raises(ToolValidationError) as ctx:
        extract_json_object('just plain text')
    assert 'JSON object' in str(ctx.value)


def test_raises_on_bare_braces_with_invalid_json() -> None:
    with pytest.raises(ToolValidationError):
        extract_json_object('{invalid json}')


def test_raises_on_fenced_block_with_invalid_json() -> None:
    with pytest.raises(ToolValidationError):
        extract_json_object('```json\n{not valid}\n```')


def test_parses_json_when_prior_text_contains_braces() -> None:
    result = extract_json_object('thinking "literal { brace" then {"ok": true}')
    assert result == {'ok': True}


def test_repairs_trailing_comma_and_unquoted_key() -> None:
    result = extract_json_object('prefix {type:"final", content:"ok",} suffix')
    assert result == {'type': 'final', 'content': 'ok'}


def test_returns_empty_when_no_agents_md() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = load_project_instructions(tmp)
        assert result == ''


def test_returns_content_when_agents_md_exists() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'AGENTS.md'
        path.write_text('Project rules here\n', encoding='utf-8')
        result = load_project_instructions(tmp)
        assert result == 'Project rules here\n'


def test_loads_hierarchical_instructions_from_parent_to_child() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        child = root / 'a' / 'b'
        child.mkdir(parents=True)
        (root / 'AGENTS.md').write_text('root rules\n', encoding='utf-8')
        (root / 'a' / 'AGENTS.md').write_text('a rules\n', encoding='utf-8')
        (child / 'AGENTS.md').write_text('b rules\n', encoding='utf-8')

        result = load_project_instructions(child)

        assert 'root rules' in result
        assert 'a rules' in result
        assert 'b rules' in result
        assert result.index('root rules') < result.index('a rules')
        assert result.index('a rules') < result.index('b rules')


def test_loads_fallback_instruction_filenames() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        child = root / 'repo'
        child.mkdir(parents=True)
        (root / 'AGENT.md').write_text('legacy root rules\n', encoding='utf-8')
        (child / 'CLAUDE.md').write_text('child claude rules\n', encoding='utf-8')

        result = load_project_instructions(child)

        assert 'legacy root rules' in result
        assert 'child claude rules' in result


def test_returns_prompt_bundle_with_task(registry) -> None:
    bundle = assemble_agent_prompt(task='do thing', context={}, registry=registry)

    assert isinstance(bundle, PromptBundle)
    assert 'TeaAgent' in bundle.system
    assert 'Available tools' in bundle.system
    assert 'do thing' in bundle.user
    assert 'observations' in bundle.user


def test_includes_project_instructions_in_system_prompt(registry) -> None:
    bundle = assemble_agent_prompt(
        task='x',
        context={},
        registry=registry,
        project_instructions='Custom rules.',
    )

    assert 'Project instructions' in bundle.system
    assert 'Custom rules.' in bundle.system


def test_includes_task_spec_in_user_prompt(registry) -> None:
    bundle = assemble_agent_prompt(
        task='x',
        context={'task_spec': 'Clarified: do X'},
        registry=registry,
        task_spec='Clarified: do X',
    )

    assert 'Clarified: do X' in bundle.user


def test_includes_memories_in_user_prompt(registry) -> None:
    bundle = assemble_agent_prompt(
        task='x',
        context={'memories': [{'id': 'm1', 'content': 'note'}]},
        registry=registry,
    )

    assert 'note' in bundle.user


def test_includes_observations_in_user_prompt(registry) -> None:
    bundle = assemble_agent_prompt(
        task='x',
        context={
            'observations': [
                {'call_id': 'c1', 'tool_name': 't', 'result': {'ok': True}}
            ]
        },
        registry=registry,
    )

    assert 'ok' in bundle.user


def test_omits_project_instructions_when_none(registry) -> None:
    bundle = assemble_agent_prompt(task='x', context={}, registry=registry)

    assert 'Project instructions' not in bundle.system


def test_tool_metadata_in_system_prompt() -> None:
    registry = ToolRegistry()
    registry.register(
        name='say_hello',
        description='Say hello',
        input_schema={'type': 'object', 'properties': {}, 'required': []},
        output_schema={'type': 'object', 'properties': {}, 'required': []},
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: {'message': 'hello'},
    )
    bundle = assemble_agent_prompt(task='greet', context={}, registry=registry)

    assert 'say_hello' in bundle.system
    assert 'readOnlyHint' in bundle.system


def test_parses_final_decision() -> None:
    result = parse_model_decision('{"type":"final","content":"all done"}')
    assert isinstance(result, FinalAnswer)
    assert result.content == 'all done'


def test_parses_tool_decision() -> None:
    result = parse_model_decision(
        '{"type":"tool","tool_name":"read","arguments":{"path":"f.txt"},"call_id":"c1"}'
    )
    assert isinstance(result, ToolRequest)
    assert result.tool_name == 'read'
    assert result.arguments == {'path': 'f.txt'}
    assert result.call_id == 'c1'


def test_tool_without_call_id_generates_default() -> None:
    result = parse_model_decision('{"type":"tool","tool_name":"x","arguments":{}}')
    assert isinstance(result, ToolRequest)
    assert result.call_id.startswith('model-x')


def test_raises_on_unknown_type() -> None:
    with pytest.raises(ToolValidationError) as ctx:
        parse_model_decision('{"type":"unknown"}')
    assert "must be 'tool' or 'final'" in str(ctx.value)


def test_raises_on_final_without_string_content() -> None:
    with pytest.raises(ToolValidationError) as ctx:
        parse_model_decision('{"type":"final","content":42}')
    assert 'string content' in str(ctx.value)


def test_raises_on_tool_without_string_name() -> None:
    with pytest.raises(ToolValidationError) as ctx:
        parse_model_decision('{"type":"tool","tool_name":123,"arguments":{}}')
    assert 'string tool_name' in str(ctx.value)


def test_raises_on_tool_without_object_arguments() -> None:
    with pytest.raises(ToolValidationError) as ctx:
        parse_model_decision('{"type":"tool","tool_name":"x","arguments":"bad"}')
    assert 'object arguments' in str(ctx.value)


def test_raises_on_tool_with_non_string_call_id() -> None:
    with pytest.raises(ToolValidationError) as ctx:
        parse_model_decision(
            '{"type":"tool","tool_name":"x","arguments":{},"call_id":123}'
        )
    assert 'call_id' in str(ctx.value)


def test_parses_fenced_json_final() -> None:
    result = parse_model_decision('```json\n{"type":"final","content":"done"}\n```')
    assert isinstance(result, FinalAnswer)
    assert result.content == 'done'


def test_parses_embedded_json_tool() -> None:
    result = parse_model_decision(
        'thinking...\n{"type":"tool","tool_name":"y","arguments":{"a":1}}\ndone'
    )
    assert isinstance(result, ToolRequest)
    assert result.tool_name == 'y'
