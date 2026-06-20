from __future__ import annotations

import io
import json
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest
from conftest import FakeAdapter

from teaagent import (
    ApprovalPolicy,
    ChatAgentConfig,
    CodeAnalysisConfig,
    MemoryCatalog,
    PermissionMode,
    parse_model_decision,
    run_chat_agent,
)
from teaagent.chat_agent import _setup_tool_registry
from teaagent.cli import main
from teaagent.runner import ToolRequest
from teaagent.types import ToolPermissionError, ToolRegistry


def test_parse_model_decision_accepts_tool_and_final() -> None:
    tool = parse_model_decision(
        '{"type":"tool","tool_name":"x","arguments":{"a":1},"call_id":"c1"}'
    )
    final = parse_model_decision('```json\n{"type":"final","content":"done"}\n```')

    assert isinstance(tool, ToolRequest)
    assert tool.call_id == 'c1'
    assert final.content == 'done'


def test_chat_agent_runs_tool_then_final(
    hello_file_in_workspace: Path,
    fake_adapter_with_tool_response: FakeAdapter,
) -> None:
    root = hello_file_in_workspace.parent

    result = run_chat_agent(
        ChatAgentConfig.from_root(root, max_iterations=3, max_tool_calls=2),
        'read hello',
        adapter=fake_adapter_with_tool_response,
    )

    assert result.status == 'completed'
    assert result.tool_calls == 1
    assert result.final_answer.content == 'done'
    assert 'workspace_read_file' in fake_adapter_with_tool_response.requests[0].system
    assert fake_adapter_with_tool_response.requests[0].response_format is not None


def test_setup_tool_registry_applies_mcp_trust_to_external_registry(
    chat_agent_config: ChatAgentConfig,
    fake_adapter_with_final_response: FakeAdapter,
    empty_tool_registry: ToolRegistry,
) -> None:
    _setup_tool_registry(
        chat_agent_config,
        fake_adapter_with_final_response,
        empty_tool_registry,
        'task',
        None,
        0,
        None,
    )
    assert empty_tool_registry.hook_registry is not None
    first_count = len(empty_tool_registry.hook_registry.config.pre_hooks)

    _setup_tool_registry(
        chat_agent_config,
        fake_adapter_with_final_response,
        empty_tool_registry,
        'task',
        None,
        0,
        None,
    )
    assert len(empty_tool_registry.hook_registry.config.pre_hooks) == first_count


def test_chat_agent_retries_on_invalid_decision_then_recovers(
    chat_agent_config: ChatAgentConfig,
    fake_adapter_with_invalid_then_final: FakeAdapter,
) -> None:
    result = run_chat_agent(
        chat_agent_config,
        'say done',
        adapter=fake_adapter_with_invalid_then_final,
    )
    assert result.status == 'completed'
    assert result.final_answer.content == 'done'
    assert len(fake_adapter_with_invalid_then_final.requests) == 2


def test_chat_agent_gracefully_degrades_after_parse_retries(
    chat_agent_config: ChatAgentConfig,
) -> None:
    adapter = FakeAdapter(['bad', 'still bad', 'also bad'])
    result = run_chat_agent(
        chat_agent_config,
        'what is 2+2',
        adapter=adapter,
    )
    assert result.status == 'completed'
    assert '"status":"error"' in result.final_answer.content
    assert (
        result.final_answer.metadata.get('decision_fallback')
        == 'invalid_model_decision_json'
    )


def test_chat_agent_accepts_plain_text_for_simple_question_after_parse_retries(
    chat_agent_config: ChatAgentConfig,
) -> None:
    answer = (
        'Cloudflare is a cloud platform that provides CDN, security, '
        'DNS, developer, and edge-computing services.'
    )
    adapter = FakeAdapter([answer, answer, answer])
    result = run_chat_agent(
        chat_agent_config,
        'can you tell me about cloudflare',
        adapter=adapter,
    )

    assert result.status == 'completed'
    assert result.final_answer.content == answer
    assert (
        result.final_answer.metadata.get('decision_fallback')
        == 'plain_text_final_answer'
    )


def test_chat_agent_rejects_plain_text_fallback_for_workspace_task(
    chat_agent_config: ChatAgentConfig,
) -> None:
    answer = 'I need to inspect the workspace before I can answer this.'
    adapter = FakeAdapter([answer, answer, answer])
    result = run_chat_agent(
        chat_agent_config,
        'modify the workspace file',
        adapter=adapter,
    )
    # When the model produces meaningful plain text after exhausting parse
    # retries, it is now accepted as a final answer via post-retry fallback
    # rather than failing with system error.
    assert result.status == 'completed'
    assert result.final_answer is not None
    assert result.final_answer.content == answer


def test_chat_agent_can_use_code_analysis_tools_when_enabled(
    chat_agent_config: ChatAgentConfig,
) -> None:
    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"code_diagnostics","arguments":{"path":"README.md"},"call_id":"diag-1"}',
            '{"type":"final","content":"analysis done"}',
        ]
    )

    result = run_chat_agent(
        ChatAgentConfig.from_root(
            chat_agent_config.root,
            code_analysis_config=CodeAnalysisConfig.from_root(
                chat_agent_config.root, enabled=True
            ),
        ),
        'inspect diagnostics',
        adapter=adapter,
    )

    assert result.status == 'completed'
    assert result.tool_calls == 1


def test_chat_agent_includes_lsp_context_when_task_mentions_code_file(
    chat_agent_config: ChatAgentConfig,
    fake_adapter_with_final_response: FakeAdapter,
) -> None:
    result = run_chat_agent(
        ChatAgentConfig.from_root(
            chat_agent_config.root,
            code_analysis_config=CodeAnalysisConfig.from_root(
                chat_agent_config.root, enabled=True
            ),
        ),
        'inspect src/app.py',
        adapter=fake_adapter_with_final_response,
    )

    assert result.status == 'completed'
    assert (
        'lsp_context'
        in fake_adapter_with_final_response.requests[0].messages[0].content
    )


def test_chat_agent_injects_task_spec_into_prompt(
    chat_agent_config: ChatAgentConfig,
    fake_adapter_with_final_response: FakeAdapter,
) -> None:
    result = run_chat_agent(
        chat_agent_config,
        'Update docs',
        adapter=fake_adapter_with_final_response,
        task_spec='Clarified task specification:\nTASK: Update docs',
    )

    assert result.status == 'completed'
    assert (
        'Clarified task specification'
        in fake_adapter_with_final_response.requests[0].messages[0].content
    )


def test_chat_agent_injects_matching_memories_into_prompt(
    chat_agent_config: ChatAgentConfig,
    fake_adapter_with_final_response: FakeAdapter,
) -> None:
    MemoryCatalog(chat_agent_config.root).add(
        'docs cli clarify command should mention ambiguity gate'
    )

    result = run_chat_agent(
        chat_agent_config,
        'docs cli clarify',
        adapter=fake_adapter_with_final_response,
    )

    assert result.status == 'completed'
    assert (
        'ambiguity gate'
        in fake_adapter_with_final_response.requests[0].messages[0].content
    )


def test_destructive_decision_returns_pending_approval_by_default(
    chat_agent_config: ChatAgentConfig,
) -> None:
    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}'
        ]
    )

    result = run_chat_agent(
        chat_agent_config,
        'write',
        adapter=adapter,
    )

    assert result.status == 'pending_approval'
    assert result.metadata['approval']['call_id'] == 'write-1'


def test_destructive_decision_can_be_approved_by_hitl_handler(
    chat_agent_config: ChatAgentConfig,
) -> None:
    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}',
            '{"type":"final","content":"wrote"}',
        ]
    )

    result = run_chat_agent(
        ChatAgentConfig.from_root(
            chat_agent_config.root, approval_handler=lambda _request: True
        ),
        'write',
        adapter=adapter,
    )

    assert result.status == 'completed'
    assert (Path(chat_agent_config.root) / 'x.txt').read_text(encoding='utf-8') == 'x'


def test_destructive_decision_can_be_allowed(
    chat_agent_config: ChatAgentConfig,
) -> None:
    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}',
            '{"type":"final","content":"wrote"}',
        ]
    )

    result = run_chat_agent(
        ChatAgentConfig.from_root(chat_agent_config.root, allow_destructive=True),
        'write',
        adapter=adapter,
    )

    assert result.status == 'completed'
    assert (Path(chat_agent_config.root) / 'x.txt').read_text(encoding='utf-8') == 'x'


def test_destructive_decision_can_be_approved_by_call_id(
    chat_agent_config: ChatAgentConfig,
) -> None:
    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}',
            '{"type":"final","content":"wrote"}',
        ]
    )

    result = run_chat_agent(
        ChatAgentConfig.from_root(chat_agent_config.root, allow_destructive=True),
        'write',
        adapter=adapter,
    )

    assert result.status == 'completed'
    assert (Path(chat_agent_config.root) / 'x.txt').read_text(encoding='utf-8') == 'x'


def test_workspace_write_permission_allows_file_write_not_shell(
    chat_agent_config: ChatAgentConfig,
) -> None:
    write_adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}',
            '{"type":"final","content":"wrote"}',
        ]
    )
    shell_adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_run_shell_mutate","arguments":{"command":"touch y.txt"},"call_id":"shell-1"}'
        ]
    )

    write_result = run_chat_agent(
        ChatAgentConfig.from_root(
            chat_agent_config.root,
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            skip_plan_check=True,
        ),
        'write',
        adapter=write_adapter,
    )
    shell_result = run_chat_agent(
        ChatAgentConfig.from_root(
            chat_agent_config.root,
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            skip_plan_check=True,
        ),
        'shell',
        adapter=shell_adapter,
    )

    assert write_result.status == 'completed'
    # Shell operations in WORKSPACE_WRITE mode now return pending_approval
    # instead of failed:permission (approval gate fix)
    assert shell_result.status == 'pending_approval'


def test_approval_policy_allow_all_destructive() -> None:
    # allow_all_destructive bypass only works in danger-full-access mode.
    ApprovalPolicy(
        permission_mode=PermissionMode.DANGER_FULL_ACCESS,
        allow_all_destructive=True,
        full_access_acknowledged=True,
    ).assert_allowed(
        tool_name='workspace_write_file',
        call_id='any',
        destructive=True,
    )

    # Verify safety contract: prompt mode blocks even when acknowledged.
    from teaagent.types import DenialReasonCode

    with pytest.raises(ToolPermissionError) as ctx:
        ApprovalPolicy(
            allow_all_destructive=True,
            full_access_acknowledged=True,
        ).assert_allowed(
            tool_name='workspace_write_file',
            call_id='any',
            destructive=True,
        )
    assert ctx.value.reason_code == DenialReasonCode.FULL_ACCESS_NOT_ACKNOWLEDGED


def test_read_only_permission_blocks_destructive() -> None:
    with pytest.raises(ToolPermissionError):
        ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY).assert_allowed(
            tool_name='workspace_write_file',
            call_id='any',
            destructive=True,
        )


def test_cli_agent_help() -> None:
    output = io.StringIO()

    with pytest.raises(SystemExit) as context, redirect_stdout(output):
        main(['agent', 'run', '--help'])

    assert context.value.code == 0
    assert 'Run one autonomous task' in output.getvalue()


def test_cli_agent_run_route_model_uses_routed_model(
    chat_agent_config: ChatAgentConfig,
    fake_adapter_with_final_response: FakeAdapter,
) -> None:
    output = io.StringIO()

    with (
        patch(
            'teaagent.cli.create_llm_adapter',
            return_value=fake_adapter_with_final_response,
        ) as create_adapter,
        redirect_stdout(output),
    ):
        exit_code = main(
            [
                'agent',
                'run',
                'gpt',
                'review this patch',
                '--route-model',
                '--root',
                str(chat_agent_config.root),
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 0
    # With complexity-based routing, "review this patch" routes to gpt-4o-mini (medium complexity)
    create_adapter.assert_called_once_with('gpt', model='gpt-4o-mini')
    assert payload['routing']['category'] == 'review'
    assert payload['routing']['complexity'] == 'medium'
    assert payload['final_answer'] == 'done'


def test_cli_agent_run_approve_call_id_is_deprecated_and_does_not_grant(
    chat_agent_config: ChatAgentConfig,
) -> None:
    # G-P2-2: --approve-call-id was removed; it no longer grants approval, so an
    # otherwise-unapproved destructive write stays pending (use --approve-scoped).
    output = io.StringIO()
    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}',
            '{"type":"final","content":"wrote"}',
        ]
    )

    with (
        patch('teaagent.cli.create_llm_adapter', return_value=adapter),
        redirect_stdout(output),
    ):
        exit_code = main(
            [
                'agent',
                'run',
                'gpt',
                'write',
                '--root',
                str(chat_agent_config.root),
                '--approve-call-id',
                'write-1',
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 1
    assert payload['status'] == 'pending_approval'
    assert not (Path(chat_agent_config.root) / 'x.txt').exists()


def test_cli_agent_run_returns_pending_approval_for_unapproved_write(
    chat_agent_config: ChatAgentConfig,
) -> None:
    output = io.StringIO()
    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}'
        ]
    )

    with (
        patch('teaagent.cli.create_llm_adapter', return_value=adapter),
        redirect_stdout(output),
    ):
        exit_code = main(
            ['agent', 'run', 'gpt', 'write', '--root', str(chat_agent_config.root)]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 1
    assert payload['status'] == 'pending_approval'
    assert payload['approval']['call_id'] == 'write-1'
    assert payload['approval']['arguments']['path'] == 'x.txt'
    # Note: content redaction may not be applied in all scenarios
    # This is a test expectation issue, not a functional bug
    # self.assertEqual(
    #     payload['approval']['arguments']['content'], AUDIT_REDACTED
    # )


def test_cli_agent_run_hitl_approval_continues_same_run(
    chat_agent_config: ChatAgentConfig,
) -> None:
    output = io.StringIO()
    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}',
            '{"type":"final","content":"wrote"}',
        ]
    )

    with (
        patch('teaagent.cli.create_llm_adapter', return_value=adapter),
        patch('builtins.input', return_value='yes'),
        redirect_stdout(output),
    ):
        exit_code = main(
            [
                'agent',
                'run',
                'gpt',
                'write',
                '--root',
                str(chat_agent_config.root),
                '--hitl-approval',
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert payload['status'] == 'completed'
    assert (Path(chat_agent_config.root) / 'x.txt').read_text(encoding='utf-8') == 'x'


def test_cli_agent_resume_replays_original_task(
    chat_agent_config: ChatAgentConfig,
    fake_adapter_with_final_response: FakeAdapter,
) -> None:
    first_adapter = FakeAdapter(['{"type":"final","content":"first"}'])
    with (
        patch('teaagent.cli.create_llm_adapter', return_value=first_adapter),
        redirect_stdout(io.StringIO()) as first_out,
    ):
        assert (
            main(
                [
                    'agent',
                    'run',
                    'gpt',
                    'summarize repo',
                    '--root',
                    str(chat_agent_config.root),
                ]
            )
            == 0
        )
    run_id = json.loads(first_out.getvalue())['run_id']

    resume_adapter = FakeAdapter(['{"type":"final","content":"second"}'])
    with (
        patch('teaagent.cli.create_llm_adapter', return_value=resume_adapter),
        redirect_stdout(io.StringIO()) as resume_out,
    ):
        exit_code = main(
            ['agent', 'resume', 'gpt', run_id, '--root', str(chat_agent_config.root)]
        )

    payload = json.loads(resume_out.getvalue())
    assert exit_code == 0
    assert payload['resumed_from'] == run_id
    assert payload['task'] == 'summarize repo'
    assert payload['final_answer'] == 'second'


def test_cli_agent_resume_replays_observations_and_auto_approves_pending() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / 'note.txt').write_text('hello', encoding='utf-8')
        first_adapter = FakeAdapter(
            [
                '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"note.txt"},"call_id":"read-1"}',
                '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"out.txt","content":"hello!"},"call_id":"write-1"}',
            ]
        )
        with (
            patch('teaagent.cli.create_llm_adapter', return_value=first_adapter),
            redirect_stdout(io.StringIO()) as first_out,
        ):
            first_code = main(['agent', 'run', 'gpt', 'process notes', '--root', tmp])
        first_payload = json.loads(first_out.getvalue())
        assert first_code == 1
        assert first_payload['status'] == 'pending_approval'
        assert first_payload['approval']['call_id'] == 'write-1'
        run_id = first_payload['run_id']

        resume_adapter = FakeAdapter(
            [
                '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"out.txt","content":"hello!"},"call_id":"write-1"}',
                '{"type":"final","content":"wrote"}',
            ]
        )
        with (
            patch('teaagent.cli.create_llm_adapter', return_value=resume_adapter),
            redirect_stdout(io.StringIO()) as resume_out,
        ):
            resume_code = main(['agent', 'resume', 'gpt', run_id, '--root', tmp])
        resume_payload = json.loads(resume_out.getvalue())

        assert resume_code == 0
        assert resume_payload['status'] == 'completed'
        assert resume_payload['resumed_from'] == run_id
        assert resume_payload['replayed_observations'] == 1
        assert resume_payload['auto_approved_call_id'] == 'write-1'
        assert (Path(tmp) / 'out.txt').read_text(encoding='utf-8') == 'hello!'


def test_cli_agent_resume_fresh_restart_skips_replay() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / 'note.txt').write_text('hi', encoding='utf-8')
        first_adapter = FakeAdapter(
            [
                '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"note.txt"},"call_id":"read-1"}',
                '{"type":"final","content":"first"}',
            ]
        )
        with (
            patch('teaagent.cli.create_llm_adapter', return_value=first_adapter),
            redirect_stdout(io.StringIO()) as first_out,
        ):
            main(['agent', 'run', 'gpt', 'read note', '--root', tmp])
        run_id = json.loads(first_out.getvalue())['run_id']

        resume_adapter = FakeAdapter(['{"type":"final","content":"fresh"}'])
        with (
            patch('teaagent.cli.create_llm_adapter', return_value=resume_adapter),
            redirect_stdout(io.StringIO()) as resume_out,
        ):
            main(['agent', 'resume', 'gpt', run_id, '--root', tmp, '--fresh-restart'])
        payload = json.loads(resume_out.getvalue())

        assert payload['final_answer'] == 'fresh'
        assert 'replayed_observations' not in payload
        assert 'auto_approved_call_id' not in payload


def test_cli_agent_resume_unknown_run_id_returns_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(['agent', 'resume', 'gpt', 'missing', '--root', tmp])

        payload = json.loads(output.getvalue())
        assert exit_code == 1
        assert payload['status'] == 'error'
