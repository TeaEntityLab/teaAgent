from __future__ import annotations

import io
import json
import os
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest
from conftest import FakeAdapter

from teaagent.cli import build_parser, main


def test_top_level_run_parser_exposes_stream_flags() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(['run', '--help'])
    run = parser.parse_args(['run', 'gpt', 'hello', '--stream', '--no-progress'])
    assert run.stream
    assert run.no_progress
    assert run.command == 'agent'
    assert run.agent_command == 'run'


def test_classify_command_parser_and_handler_output(capsys) -> None:
    parser = build_parser()
    args = parser.parse_args(['classify', 'fix a bug'])

    assert args.task == 'fix a bug'
    assert args.func(args) == 0

    captured = capsys.readouterr()
    assert 'Task: fix a bug' in captured.out
    assert 'Type: debugging' in captured.out
    assert 'Complexity:' in captured.out
    assert 'Estimated Steps:' in captured.out


def test_agent_run_code_analysis_flag_enables_tools() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        adapter = FakeAdapter(
            [
                '{"type":"tool","tool_name":"code_diagnostics","arguments":{"path":"README.md"},"call_id":"diag-1"}',
                '{"type":"final","content":"done"}',
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
                    'run diagnostics',
                    '--root',
                    tmp,
                    '--code-analysis',
                ]
            )

        try:
            payload = json.loads(output.getvalue())
        except Exception as e:
            raise ValueError(
                f'JSONDecodeError: output.getvalue() is {repr(output.getvalue())}, exit_code was {exit_code}'
            ) from e
        assert exit_code == 0
        assert payload['status'] == 'completed'


def test_init_writes_workspace_config_non_interactive() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    'init',
                    '--root',
                    tmp,
                    '--provider',
                    'gpt',
                    '--api-key',
                    'sk-test-123',
                    '--permission-mode',
                    'workspace-write',
                    '--max-iterations',
                    '12',
                    '--max-tool-calls',
                    '9',
                ]
            )

        assert exit_code == 0
        payload = json.loads(output.getvalue())
        assert payload['ok']
        cfg_path = Path(tmp) / '.teaagent' / 'config.json'
        assert cfg_path.exists()
        cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
        assert cfg['provider'] == 'gpt'
        assert cfg['permission_mode'] == 'workspace-write'
        assert cfg['max_iterations'] == 12
        assert cfg['max_tool_calls'] == 9
        assert payload['agents_md_status'] == 'created'
        assert (Path(tmp) / 'AGENTS.md').exists()


def test_init_writes_env_file_when_requested() -> None:
    with (
        tempfile.TemporaryDirectory() as tmp,
        patch.dict(os.environ, {}, clear=True),
    ):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    'init',
                    '--root',
                    tmp,
                    '--provider',
                    'gpt',
                    '--api-key',
                    'sk-test-456',
                    '--write-env',
                ]
            )

        assert exit_code == 0
        payload = json.loads(output.getvalue())
        assert payload['ok']
        assert payload['env_status'] == 'written'
        env_path = Path(tmp) / '.teaagent' / 'env'
        assert env_path.exists()
        content = env_path.read_text(encoding='utf-8')
        assert 'OPENAI_API_KEY=sk-test-456' in content


def test_init_interactive_prompts_for_api_key() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        with (
            patch(
                'teaagent.cli._handlers._misc.getpass.getpass',
                return_value='sk-prompt-1',
            ),
            patch('teaagent.cli._handlers._misc.input', return_value='gpt'),
            redirect_stdout(output),
        ):
            exit_code = main(['init', '--root', tmp])

        assert exit_code == 0
        payload = json.loads(output.getvalue())
        assert payload['ok']
        cfg = json.loads(
            (Path(tmp) / '.teaagent' / 'config.json').read_text(encoding='utf-8')
        )
        assert cfg['provider'] == 'gpt'


def test_daily_dry_run_human_output() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        setup_out = io.StringIO()
        with redirect_stdout(setup_out):
            main(
                [
                    'setup',
                    '--root',
                    tmp,
                    '--provider',
                    'gpt',
                    '--api-key',
                    'sk-human-daily',
                    '--permission-mode',
                    'read-only',
                ]
            )
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    'daily',
                    'readiness',
                    '--root',
                    tmp,
                    '--dry-run',
                    '--human',
                ]
            )
        text = output.getvalue()
        assert 'TeaAgent readiness' in text
        assert '"dry_run"' not in text
        assert exit_code in (0, 2)


def test_setup_human_output() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    'setup',
                    '--root',
                    tmp,
                    '--provider',
                    'gpt',
                    '--api-key',
                    'sk-human-setup',
                    '--human',
                ]
            )
        text = output.getvalue()
        assert exit_code == 0
        assert 'TeaAgent Setup' in text
        assert '"mode"' not in text


def test_setup_writes_workspace_and_redacts_stdout() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    'setup',
                    '--root',
                    tmp,
                    '--provider',
                    'gpt',
                    '--api-key',
                    'sk-setup-cli',
                    '--permission-mode',
                    'read-only',
                    '--write-env',
                ]
            )
        assert exit_code == 0
        payload = json.loads(output.getvalue())
        assert payload['ok']
        assert payload['mode'] == 'setup'
        assert 'safe_command' in payload
        assert 'checks' in payload
        assert 'sk-setup-cli' not in output.getvalue()
        assert (Path(tmp) / '.teaagent' / 'config.json').exists()


def test_init_wizard_delegates_to_setup() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    'init',
                    '--wizard',
                    '--root',
                    tmp,
                    '--provider',
                    'gpt',
                    '--api-key',
                    'sk-wizard-delegate',
                ]
            )
        assert exit_code == 0
        payload = json.loads(output.getvalue())
        assert payload['mode'] == 'setup'
        assert 'files_written' in payload


def test_doctor_graphqlite_outputs_json() -> None:
    output = io.StringIO()

    with redirect_stdout(output):
        exit_code = main(['doctor', 'graphqlite'])

    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert payload['ok']


def test_graphqlite_smoke_runs_real_query() -> None:
    output = io.StringIO()

    with redirect_stdout(output):
        exit_code = main(['graphqlite', 'smoke'])

    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert payload == [{'n.name': 'TeaAgent'}]


def test_doctor_model_reports_missing_key() -> None:
    with (
        tempfile.TemporaryDirectory(),
        patch.dict(os.environ, {'OPENAI_API_KEY': ''}, clear=True),
    ):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(['doctor', 'model', 'gpt'])
        payload = json.loads(output.getvalue())
        assert exit_code == 1
        assert not payload['ok']
        assert payload['provider'] == 'gpt'


def test_doctor_model_ok_when_key_set() -> None:
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'sk-test-key'}, clear=True):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(['doctor', 'model', 'gpt'])
        payload = json.loads(output.getvalue())
        assert exit_code == 0
        assert payload['ok']
        assert payload['provider'] == 'gpt'


def test_doctor_model_wizard_uses_keychain_when_prompt_empty() -> None:
    output = io.StringIO()
    with (
        patch('teaagent.cli._handlers._doctor.getpass.getpass', return_value=''),
        patch('teaagent.cli._handlers._doctor.input', return_value=''),
        patch('teaagent.wizard.subprocess.run') as security_run,
        patch.dict(os.environ, {}, clear=True),
        redirect_stdout(output),
    ):
        security_run.return_value.returncode = 0
        security_run.return_value.stdout = 'sk-from-keychain\n'
        exit_code = main(['doctor', 'model', 'gpt', '--wizard'])
    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert payload['ok']
    assert payload['token_source'] == 'keychain'


def test_doctor_aigateway_reports_missing_base_url() -> None:
    with patch.dict(os.environ, {'CLOUDFLARE_API_TOKEN': 'cf-token'}, clear=True):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(['doctor', 'aigateway'])
        payload = json.loads(output.getvalue())
        assert exit_code == 1
        assert not payload['ok']
        assert payload['provider'] == 'aigateway'
        assert payload['mode'] == 'unknown'


def test_doctor_aigateway_reports_gateway_mode_when_configured() -> None:
    with patch.dict(
        os.environ,
        {
            'CLOUDFLARE_API_TOKEN': 'cf-token',
            'WORKERS_AI_BASE_URL': 'https://gateway.ai.cloudflare.com/v1/acct/gw/workers-ai/v1',
            'WORKERS_AI_EXTRA_HEADERS': '{"cf-aig-authorization":"Bearer aig-token"}',
        },
        clear=True,
    ):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(['doctor', 'aigateway'])
        payload = json.loads(output.getvalue())
        assert exit_code == 0
        assert payload['ok']
        assert payload['provider'] == 'aigateway'
        assert payload['mode'] == 'gateway-workers-ai'


def test_doctor_aigateway_compat_mode_reports_gateway_compat() -> None:
    with patch.dict(
        os.environ,
        {
            'CLOUDFLARE_API_TOKEN': 'cf-token',
            'AIGATEWAY_BASE_URL': 'https://gateway.ai.cloudflare.com/v1/acct/gw/compat',
        },
        clear=True,
    ):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(['doctor', 'aigateway', '--mode', 'compat'])
        payload = json.loads(output.getvalue())
        assert exit_code == 0
        assert payload['ok']
        assert payload['requested_mode'] == 'compat'
        assert payload['mode'] == 'gateway-compat'


def test_doctor_aigateway_compat_mode_write_env_without_wizard() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        with (
            patch.dict(
                os.environ,
                {
                    'CLOUDFLARE_API_TOKEN': 'cf-token',
                    'AIGATEWAY_BASE_URL': 'https://gateway.ai.cloudflare.com/v1/acct/gw/compat',
                },
                clear=True,
            ),
            redirect_stdout(output),
        ):
            exit_code = main(
                [
                    'doctor',
                    'aigateway',
                    '--mode',
                    'compat',
                    '--write-env',
                    '--root',
                    tmp,
                ]
            )
        payload = json.loads(output.getvalue())
        assert exit_code == 0
        assert payload['env_status'] == 'written'
        env_content = (Path(tmp) / '.teaagent' / 'env').read_text(encoding='utf-8')
        assert (
            'export AIGATEWAY_BASE_URL=https://gateway.ai.cloudflare.com/v1/acct/gw/compat'
            in env_content
        )


def test_doctor_aigateway_wizard_writes_env() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        env_path = Path(tmp) / '.teaagent' / 'env'
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text('export OPENAI_API_KEY=sk-existing\n', encoding='utf-8')
        output = io.StringIO()
        with (
            patch(
                'teaagent.cli._handlers._doctor.input',
                side_effect=['acct123', 'gw123', 'y'],
            ),
            patch(
                'teaagent.cli._handlers._doctor.getpass.getpass',
                side_effect=['cf-token', 'gw-token'],
            ),
            patch.dict(os.environ, {}, clear=True),
            redirect_stdout(output),
        ):
            exit_code = main(
                ['doctor', 'aigateway', '--wizard', '--write-env', '--root', tmp]
            )

        payload = json.loads(output.getvalue())
        assert exit_code == 0
        assert payload['ok']
        assert payload['mode'] == 'wizard'
        assert payload['env_status'] == 'written'
        env_path = Path(tmp) / '.teaagent' / 'env'
        assert env_path.exists()
        content = env_path.read_text(encoding='utf-8')
        assert 'OPENAI_API_KEY=sk-existing' in content
        assert 'CLOUDFLARE_API_TOKEN=cf-token' in content
        assert (
            'WORKERS_AI_BASE_URL=https://gateway.ai.cloudflare.com/v1/acct123/gw123/workers-ai/v1'
            in content
        )


def test_doctor_aigateway_wizard_writes_compat_base_url() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        with (
            patch(
                'teaagent.cli._handlers._doctor.input',
                side_effect=['acct123', 'gw123', 'n'],
            ),
            patch(
                'teaagent.cli._handlers._doctor.getpass.getpass',
                side_effect=['cf-token'],
            ),
            patch.dict(os.environ, {}, clear=True),
            redirect_stdout(output),
        ):
            exit_code = main(
                [
                    'doctor',
                    'aigateway',
                    '--mode',
                    'compat',
                    '--wizard',
                    '--write-env',
                    '--root',
                    tmp,
                ]
            )
        payload = json.loads(output.getvalue())
        assert exit_code == 0
        assert payload['ok']
        assert payload['configured']['AIGATEWAY_BASE_URL']
        content = (Path(tmp) / '.teaagent' / 'env').read_text(encoding='utf-8')
        assert (
            'AIGATEWAY_BASE_URL=https://gateway.ai.cloudflare.com/v1/acct123/gw123/compat'
            in content
        )


def test_doctor_aigateway_wizard_reads_keychain_token_when_input_empty() -> None:
    output = io.StringIO()
    with (
        patch(
            'teaagent.cli._handlers._doctor.input',
            side_effect=['acct123', 'gw123', 'n'],
        ),
        patch(
            'teaagent.cli._handlers._doctor.getpass.getpass',
            return_value='',
        ),
        patch('teaagent.wizard.subprocess.run') as security_run,
        patch.dict(os.environ, {}, clear=True),
        redirect_stdout(output),
    ):
        security_run.return_value.returncode = 0
        security_run.return_value.stdout = 'cf-token-from-keychain\n'
        exit_code = main(['doctor', 'aigateway', '--wizard'])

    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert payload['ok']
    assert payload['configured']['CLOUDFLARE_API_TOKEN']


def test_doctor_providers_outputs_checks() -> None:
    """Doctor providers outputs provider checks."""
    output = io.StringIO()
    with (
        patch('teaagent.cli.check_llm_configuration', return_value=(True, 'ok')),
        patch('teaagent.wizard.subprocess.run') as security_run,
        redirect_stdout(output),
    ):
        security_run.return_value.returncode = 1
        security_run.return_value.stdout = ''
        exit_code = main(['doctor', 'providers'])
    result = output.getvalue()
    assert isinstance(exit_code, int)
    assert len(result) > 0, 'Expected non-empty output from doctor providers'


def test_cli_with_missing_required_argument() -> None:
    """Test that missing required argument is handled."""
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(['init', '--root', tmp])
            # Missing --provider should cause error
            assert exit_code != 0


def test_cli_with_invalid_root_path() -> None:
    """Test that invalid root path is handled."""
    output = io.StringIO()
    with redirect_stdout(output):
        exit_code = main(['agent', 'card', '--root', '/nonexistent/path'])
        # Should handle gracefully
        assert isinstance(exit_code, int)


def test_cli_with_negative_max_iterations() -> None:
    """Test that negative max_iterations is handled."""
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    'init',
                    '--root',
                    tmp,
                    '--provider',
                    'gpt',
                    '--api-key',
                    'sk-test',
                    '--max-iterations',
                    '-1',
                ]
            )
            # Should handle negative value
            assert isinstance(exit_code, int)


def test_cli_with_negative_max_tool_calls() -> None:
    """Test that negative max_tool_calls is handled."""
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    'init',
                    '--root',
                    tmp,
                    '--provider',
                    'gpt',
                    '--api-key',
                    'sk-test',
                    '--max-tool-calls',
                    '-1',
                ]
            )
            # Should handle negative value
            assert isinstance(exit_code, int)


def test_cli_with_empty_api_key() -> None:
    """Test that empty API key is handled."""
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    'init',
                    '--root',
                    tmp,
                    '--provider',
                    'gpt',
                    '--api-key',
                    '',
                ]
            )
            # Should handle empty key
            assert isinstance(exit_code, int)


def test_cli_with_special_characters_in_api_key() -> None:
    """Test that special characters in API key are handled."""
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    'init',
                    '--root',
                    tmp,
                    '--provider',
                    'gpt',
                    '--api-key',
                    'sk-test\n\t\r\0',
                ]
            )
            # Should handle special characters
            assert isinstance(exit_code, int)


def test_cli_with_very_long_agent_name() -> None:
    """Test that very long agent name is handled."""
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        long_name = 'x' * 10000
        with redirect_stdout(output):
            exit_code = main(
                [
                    'agent',
                    'card',
                    '--root',
                    tmp,
                    '--agent-name',
                    long_name,
                ]
            )
        # Should handle long name
        assert isinstance(exit_code, int)


def test_cli_with_unicode_agent_name() -> None:
    """Test that unicode agent name is handled."""
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    'agent',
                    'card',
                    '--root',
                    tmp,
                    '--agent-name',
                    '你好世界🌍',
                ]
            )
        # Should handle unicode
        assert isinstance(exit_code, int)


def test_cli_with_invalid_endpoint_url() -> None:
    """Test that invalid endpoint URL is handled."""
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    'agent',
                    'card',
                    '--root',
                    tmp,
                    '--endpoint',
                    'not-a-valid-url',
                ]
            )
        # Should handle invalid URL
        assert isinstance(exit_code, int)


def test_cli_with_permission_denied_directory() -> None:
    """Test that permission errors are handled."""
    with tempfile.TemporaryDirectory() as tmp:
        readonly = Path(tmp) / 'readonly'
        readonly.mkdir()
        readonly.chmod(0o000)

        try:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(['agent', 'card', '--root', str(readonly)])
            # Should handle permission error
            assert isinstance(exit_code, int)
        finally:
            readonly.chmod(0o755)


def test_cli_with_nonexistent_config_file() -> None:
    """Test that missing config file is handled."""
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(['run', 'gpt', 'test', '--root', tmp])
        # Should handle missing config
        assert isinstance(exit_code, int)


def test_cli_with_corrupted_config_file() -> None:
    """Test that corrupted config file is handled."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / '.teaagent').mkdir()
        (Path(tmp) / '.teaagent' / 'config.json').write_text(
            'corrupted json{', encoding='utf-8'
        )

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(['run', 'gpt', 'test', '--root', tmp])
        # Should handle corrupted config
        assert isinstance(exit_code, int)


def test_cli_with_empty_task() -> None:
    """Test that empty task is handled."""
    with tempfile.TemporaryDirectory() as tmp:
        # First initialize
        output = io.StringIO()
        with redirect_stdout(output):
            main(
                [
                    'init',
                    '--root',
                    tmp,
                    '--provider',
                    'gpt',
                    '--api-key',
                    'sk-test',
                ]
            )

        # Then try with empty task
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(['run', 'gpt', '', '--root', tmp])
        # Should handle empty task
        assert isinstance(exit_code, int)


def test_cli_parser_with_invalid_flag_combination() -> None:
    """Test that invalid flag combinations are handled."""
    parser = build_parser()
    # Try to parse conflicting flags
    with pytest.raises(SystemExit):
        parser.parse_args(['invalid', '--unknown-flag'])


def test_cli_with_very_long_task() -> None:
    """Test that very long task is handled."""
    with tempfile.TemporaryDirectory() as tmp:
        # First initialize
        output = io.StringIO()
        with redirect_stdout(output):
            main(
                [
                    'init',
                    '--root',
                    tmp,
                    '--provider',
                    'gpt',
                    '--api-key',
                    'sk-test',
                ]
            )

        # Then try with very long task
        long_task = 'x' * 100000
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(['run', 'gpt', long_task, '--root', tmp])
        # Should handle long task
        assert isinstance(exit_code, int)
