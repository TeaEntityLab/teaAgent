from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main


class CLITests(unittest.TestCase):
    def test_agent_run_code_analysis_flag_enables_tools(self) -> None:
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

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload['status'], 'completed')

    def test_init_writes_workspace_config_non_interactive(self) -> None:
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

            self.assertEqual(exit_code, 0)
            payload = json.loads(output.getvalue())
            self.assertTrue(payload['ok'])
            cfg_path = Path(tmp) / '.teaagent' / 'config.json'
            self.assertTrue(cfg_path.exists())
            cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
            self.assertEqual(cfg['provider'], 'gpt')
            self.assertEqual(cfg['permission_mode'], 'workspace-write')
            self.assertEqual(cfg['max_iterations'], 12)
            self.assertEqual(cfg['max_tool_calls'], 9)
            self.assertEqual(payload['agents_md_status'], 'created')
            self.assertTrue((Path(tmp) / 'AGENTS.md').exists())

    def test_init_writes_env_file_when_requested(self) -> None:
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

            self.assertEqual(exit_code, 0)
            payload = json.loads(output.getvalue())
            self.assertTrue(payload['ok'])
            self.assertEqual(payload['env_status'], 'written')
            env_path = Path(tmp) / '.teaagent' / 'env'
            self.assertTrue(env_path.exists())
            content = env_path.read_text(encoding='utf-8')
            self.assertIn('OPENAI_API_KEY=sk-test-456', content)

    def test_init_interactive_prompts_for_api_key(self) -> None:
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

            self.assertEqual(exit_code, 0)
            payload = json.loads(output.getvalue())
            self.assertTrue(payload['ok'])
            cfg = json.loads(
                (Path(tmp) / '.teaagent' / 'config.json').read_text(encoding='utf-8')
            )
            self.assertEqual(cfg['provider'], 'gpt')

    def test_doctor_graphqlite_outputs_json(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(['doctor', 'graphqlite'])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload['ok'])

    def test_graphqlite_smoke_runs_real_query(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(['graphqlite', 'smoke'])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload, [{'n.name': 'TeaAgent'}])

    def test_doctor_model_reports_missing_key(self) -> None:
        with (
            tempfile.TemporaryDirectory() as _tmp,
            patch.dict(os.environ, {'OPENAI_API_KEY': ''}, clear=True),
        ):
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(['doctor', 'model', 'gpt'])
            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 1)
            self.assertFalse(payload['ok'])
            self.assertEqual(payload['provider'], 'gpt')

    def test_doctor_model_ok_when_key_set(self) -> None:
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'sk-test-key'}, clear=True):
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(['doctor', 'model', 'gpt'])
            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload['ok'])
            self.assertEqual(payload['provider'], 'gpt')

    def test_doctor_model_wizard_uses_keychain_when_prompt_empty(self) -> None:
        output = io.StringIO()
        with (
            patch('teaagent.cli._handlers._doctor.getpass.getpass', return_value=''),
            patch('teaagent.cli._handlers._doctor.input', return_value=''),
            patch('teaagent.cli._handlers._doctor.subprocess.run') as security_run,
            patch.dict(os.environ, {}, clear=True),
            redirect_stdout(output),
        ):
            security_run.return_value.returncode = 0
            security_run.return_value.stdout = 'sk-from-keychain\n'
            exit_code = main(['doctor', 'model', 'gpt', '--wizard'])
        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['token_source'], 'keychain')

    def test_doctor_aigateway_reports_missing_base_url(self) -> None:
        with patch.dict(os.environ, {'CLOUDFLARE_API_TOKEN': 'cf-token'}, clear=True):
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(['doctor', 'aigateway'])
            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 1)
            self.assertFalse(payload['ok'])
            self.assertEqual(payload['provider'], 'aigateway')
            self.assertEqual(payload['mode'], 'unknown')

    def test_doctor_aigateway_reports_gateway_mode_when_configured(self) -> None:
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
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload['ok'])
            self.assertEqual(payload['provider'], 'aigateway')
            self.assertEqual(payload['mode'], 'gateway-workers-ai')

    def test_doctor_aigateway_compat_mode_reports_gateway_compat(self) -> None:
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
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload['ok'])
            self.assertEqual(payload['requested_mode'], 'compat')
            self.assertEqual(payload['mode'], 'gateway-compat')

    def test_doctor_aigateway_compat_mode_write_env_without_wizard(self) -> None:
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
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload['env_status'], 'written')
            env_content = (Path(tmp) / '.teaagent' / 'env').read_text(encoding='utf-8')
            self.assertIn(
                'export AIGATEWAY_BASE_URL=https://gateway.ai.cloudflare.com/v1/acct/gw/compat',
                env_content,
            )

    def test_doctor_aigateway_wizard_writes_env(self) -> None:
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
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload['ok'])
            self.assertEqual(payload['mode'], 'wizard')
            self.assertEqual(payload['env_status'], 'written')
            env_path = Path(tmp) / '.teaagent' / 'env'
            self.assertTrue(env_path.exists())
            content = env_path.read_text(encoding='utf-8')
            self.assertIn('OPENAI_API_KEY=sk-existing', content)
            self.assertIn('CLOUDFLARE_API_TOKEN=cf-token', content)
            self.assertIn(
                'WORKERS_AI_BASE_URL=https://gateway.ai.cloudflare.com/v1/acct123/gw123/workers-ai/v1',
                content,
            )

    def test_doctor_aigateway_wizard_writes_compat_base_url(self) -> None:
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
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload['ok'])
            self.assertTrue(payload['configured']['AIGATEWAY_BASE_URL'])
            content = (Path(tmp) / '.teaagent' / 'env').read_text(encoding='utf-8')
            self.assertIn(
                'AIGATEWAY_BASE_URL=https://gateway.ai.cloudflare.com/v1/acct123/gw123/compat',
                content,
            )

    def test_doctor_aigateway_wizard_reads_keychain_token_when_input_empty(
        self,
    ) -> None:
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
            patch('teaagent.cli._handlers._doctor.subprocess.run') as security_run,
            patch.dict(os.environ, {}, clear=True),
            redirect_stdout(output),
        ):
            security_run.return_value.returncode = 0
            security_run.return_value.stdout = 'cf-token-from-keychain\n'
            exit_code = main(['doctor', 'aigateway', '--wizard'])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload['ok'])
        self.assertTrue(payload['configured']['CLOUDFLARE_API_TOKEN'])

    def test_doctor_providers_outputs_checks(self) -> None:
        output = io.StringIO()
        with (
            patch('teaagent.cli.check_llm_configuration', return_value=(True, 'ok')),
            patch('teaagent.cli._handlers._doctor.subprocess.run') as security_run,
            redirect_stdout(output),
        ):
            security_run.return_value.returncode = 1
            security_run.return_value.stdout = ''
            exit_code = main(['doctor', 'providers'])
        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload['ok'])
        self.assertTrue(payload['checks'])
        self.assertIn('env_loaded', payload['checks'][0])
        self.assertIn('keychain_present', payload['checks'][0])

    def test_doctor_providers_wizard_sets_env(self) -> None:
        output = io.StringIO()
        with (
            patch(
                'teaagent.cli._handlers._doctor.getpass.getpass',
                return_value='sk-test-provider',
            ),
            patch.dict(os.environ, {'OPENAI_API_KEY': ''}, clear=True),
            redirect_stdout(output),
        ):
            exit_code = main(['doctor', 'providers', '--wizard', '--provider', 'gpt'])
        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload['ok'])
        self.assertIn('gpt', payload['configured'])

    def test_doctor_providers_wizard_batch_write_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / '.teaagent' / 'env'
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text('export GEMINI_API_KEY=sk-existing\n', encoding='utf-8')
            output = io.StringIO()
            with (
                patch(
                    'teaagent.cli._handlers._doctor.getpass.getpass',
                    side_effect=['sk-openai', 'sk-anthropic'],
                ),
                patch.dict(
                    os.environ,
                    {'OPENAI_API_KEY': '', 'ANTHROPIC_API_KEY': ''},
                    clear=True,
                ),
                redirect_stdout(output),
            ):
                exit_code = main(
                    [
                        'doctor',
                        'providers',
                        '--wizard',
                        '--provider',
                        'gpt',
                        '--provider',
                        'claude',
                        '--write-env',
                        '--root',
                        tmp,
                    ]
                )
            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(set(payload['configured']), {'gpt', 'claude'})
            self.assertEqual(payload['env_status'], 'written')
            env_content = (Path(tmp) / '.teaagent' / 'env').read_text(encoding='utf-8')
            self.assertIn('export OPENAI_API_KEY=sk-openai', env_content)
            self.assertIn('export ANTHROPIC_API_KEY=sk-anthropic', env_content)
            self.assertIn('export GEMINI_API_KEY=sk-existing', env_content)

    def test_doctor_providers_wizard_fails_when_selected_provider_missing(self) -> None:
        output = io.StringIO()
        with (
            patch('teaagent.cli._handlers._doctor.getpass.getpass', return_value=''),
            patch('teaagent.cli._handlers._doctor.subprocess.run') as security_run,
            patch.dict(os.environ, {'OPENAI_API_KEY': ''}, clear=True),
            redirect_stdout(output),
        ):
            security_run.return_value.returncode = 1
            security_run.return_value.stdout = ''
            exit_code = main(['doctor', 'providers', '--wizard', '--provider', 'gpt'])
        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['unresolved'][0]['provider'], 'gpt')

    def test_doctor_project_wizard_outputs_next_steps(self) -> None:
        output = io.StringIO()
        with (
            patch(
                'teaagent.cli._handlers._doctor.input',
                side_effect=['gpt', 'prompt'],
            ),
            redirect_stdout(output),
        ):
            exit_code = main(['doctor', 'project', '--wizard', '--root', '.'])
        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['provider'], 'gpt')
        self.assertTrue(payload['next_steps'])

    def test_doctor_mcp_wizard_outputs_launch_command(self) -> None:
        output = io.StringIO()
        with (
            patch(
                'teaagent.cli._handlers._doctor.input',
                side_effect=['127.0.0.1', '7330', 'n'],
            ),
            redirect_stdout(output),
        ):
            exit_code = main(['doctor', 'mcp', '--wizard', '--root', '.'])
        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertIn('teaagent mcp serve --http', payload['launch_command'])

    def test_doctor_mcp_wizard_redacts_auth_token_in_launch_command(self) -> None:
        output = io.StringIO()
        with (
            patch(
                'teaagent.cli._handlers._doctor.input',
                side_effect=['127.0.0.1', '7330', 'y'],
            ),
            patch(
                'teaagent.cli._handlers._doctor.getpass.getpass', return_value='secret'
            ),
            redirect_stdout(output),
        ):
            exit_code = main(['doctor', 'mcp', '--wizard', '--root', '.'])
        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertIn('--auth-token <redacted>', payload['launch_command'])
        self.assertNotIn('secret', payload['launch_command'])

    def test_doctor_env_order_reports_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(['doctor', 'env-order', '--root', tmp])
            payload = json.loads(output.getvalue())
            self.assertIn(exit_code, (0, 1))
            self.assertIn('checks', payload)
            self.assertIn('recommended_order', payload)

    def test_model_smoke_outputs_provider_and_content(self) -> None:
        adapter = FakeAdapter(['hello from fake'])
        output = io.StringIO()

        with (
            patch('teaagent.cli.create_llm_adapter', return_value=adapter),
            redirect_stdout(output),
        ):
            exit_code = main(
                ['model', 'smoke', 'gpt', '--prompt', 'say hi', '--max-tokens', '16']
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload['provider'], 'fake')
        self.assertEqual(payload['model'], 'fake-model')
        self.assertEqual(payload['content'], 'hello from fake')

    def test_cli_help_includes_description(self) -> None:
        output = io.StringIO()

        with self.assertRaises(SystemExit) as context, redirect_stdout(output):
            main(['--help'])

        self.assertEqual(context.exception.code, 0)
        self.assertIn('TeaAgent harness', output.getvalue())

    def test_cli_version_outputs_version(self) -> None:
        output = io.StringIO()

        with self.assertRaises(SystemExit) as context, redirect_stdout(output):
            main(['--version'])

        self.assertEqual(context.exception.code, 0)
        self.assertIn('teaagent', output.getvalue())

    def test_graphqlite_query_executes_cypher(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                ['graphqlite', 'query', 'MATCH (n:SmokeTest) RETURN n.name']
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertIsInstance(payload, list)

    def test_graphqlite_migrate_shows_status(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(['graphqlite', 'migrate', '--database', ':memory:'])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertIn('applied', payload)
        self.assertIn('pending', payload)
        self.assertIn('total', payload)

    def test_ultrawork_show_unknown_via_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(['ultrawork', 'show', 'unknown-id', '--root', tmp])

            self.assertEqual(exit_code, 1)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload['status'], 'error')

    def test_ultrawork_stop_unknown_via_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(['ultrawork', 'stop', 'unknown-id', '--root', tmp])

            self.assertEqual(exit_code, 1)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload['status'], 'error')

    def test_agent_status_unknown_run_id_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(['agent', 'status', 'no-such-run', '--root', tmp])

            self.assertEqual(exit_code, 1)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload['status'], 'error')

    def test_mcp_http_rejects_remote_bind_without_auth(self) -> None:
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(stderr):
            exit_code = main(
                ['mcp', 'serve', '--http', '--host', '0.0.0.0', '--root', tmp]
            )

        self.assertEqual(exit_code, 1)
        self.assertIn('non-loopback host without --auth-token', stderr.getvalue())

    def test_mcp_http_allows_remote_bind_with_auth(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch('teaagent.cli.serve_mcp_http', return_value=0) as serve_mcp_http,
        ):
            exit_code = main(
                [
                    'mcp',
                    'serve',
                    '--http',
                    '--host',
                    '0.0.0.0',
                    '--auth-token',
                    'token',
                    '--root',
                    tmp,
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(serve_mcp_http.call_args.kwargs['auth_token'], 'token')

    def test_mcp_http_oauth_key_ring_file_loads(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch('teaagent.cli.serve_mcp_http', return_value=0),
        ):
            key_ring_path = Path(tmp) / 'keyring.json'
            key_ring_path.write_text(
                json.dumps(
                    {
                        'active_kid': 'v2',
                        'keys': {
                            'v1': 'legacy-signing-secret-0001',
                            'v2': 'active-signing-secret-0002',
                        },
                    }
                ),
                encoding='utf-8',
            )
            exit_code = main(
                [
                    'mcp',
                    'serve',
                    '--http',
                    '--root',
                    tmp,
                    '--oauth-issuer',
                    'https://issuer.test',
                    '--oauth-signing-key',
                    'fallback-signing-key-1234',
                    '--oauth-key-ring-file',
                    str(key_ring_path),
                ]
            )

        self.assertEqual(exit_code, 0)

    def test_mcp_http_oauth_active_kid_requires_file(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(stderr):
            exit_code = main(
                [
                    'mcp',
                    'serve',
                    '--http',
                    '--root',
                    tmp,
                    '--oauth-issuer',
                    'https://issuer.test',
                    '--oauth-signing-key',
                    'fallback-signing-key-1234',
                    '--oauth-active-kid',
                    'v2',
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertIn(
            '--oauth-active-kid requires --oauth-key-ring-file', stderr.getvalue()
        )

    def test_mcp_http_oauth_key_ring_rejects_unknown_active_kid(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(stderr):
            key_ring_path = Path(tmp) / 'keyring.json'
            key_ring_path.write_text(
                json.dumps(
                    {
                        'active_kid': 'v1',
                        'keys': {
                            'v1': 'legacy-signing-secret-0001',
                        },
                    }
                ),
                encoding='utf-8',
            )
            exit_code = main(
                [
                    'mcp',
                    'serve',
                    '--http',
                    '--root',
                    tmp,
                    '--oauth-issuer',
                    'https://issuer.test',
                    '--oauth-signing-key',
                    'fallback-signing-key-1234',
                    '--oauth-key-ring-file',
                    str(key_ring_path),
                    '--oauth-active-kid',
                    'v2',
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("OAuth active kid 'v2' not found", stderr.getvalue())
        self.assertIn('available kids: v1', stderr.getvalue())

    def test_mcp_http_oauth_dpop_replay_ttl_accepted(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch('teaagent.cli.serve_mcp_http', return_value=0),
        ):
            exit_code = main(
                [
                    'mcp',
                    'serve',
                    '--http',
                    '--root',
                    tmp,
                    '--oauth-issuer',
                    'https://issuer.test',
                    '--oauth-signing-key',
                    'signing-secret-key-12345',
                    '--oauth-dpop-replay-ttl',
                    '120',
                ]
            )
        self.assertEqual(exit_code, 0)

    def test_completion_outputs_shell_snippet(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(['completion', 'bash'])

        self.assertEqual(exit_code, 0)
        self.assertIn('complete -W', output.getvalue())

    def test_doctor_all_outputs_aggregate_report(self) -> None:
        output = io.StringIO()

        with (
            patch('teaagent.cli.check_graphqlite_runtime', return_value=(True, 'ok')),
            patch('teaagent.cli.check_llm_configuration', return_value=(True, 'ok')),
            redirect_stdout(output),
        ):
            exit_code = main(['doctor', 'all', '--provider', 'gpt'])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['checks']['providers'][0]['provider'], 'gpt')

    def test_doctor_all_accepts_provider_from_config_string(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = os.path.join(tmp, 'config.json')
            with open(config, 'w', encoding='utf-8') as handle:
                json.dump({'provider': 'openrouter'}, handle)
            output = io.StringIO()

            with (
                patch(
                    'teaagent.cli.check_graphqlite_runtime', return_value=(True, 'ok')
                ),
                patch(
                    'teaagent.cli.check_llm_configuration', return_value=(True, 'ok')
                ),
                redirect_stdout(output),
            ):
                exit_code = main(['--config', config, 'doctor', 'all'])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload['ok'])
        self.assertGreaterEqual(len(payload['checks']['providers']), 2)

    def test_config_defaults_apply_to_optional_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = os.path.join(tmp, 'config.json')
            with open(config, 'w', encoding='utf-8') as handle:
                json.dump({'model': 'configured-model'}, handle)
            adapter = FakeAdapter(['hello'])
            output = io.StringIO()

            with (
                patch(
                    'teaagent.cli.create_llm_adapter', return_value=adapter
                ) as create,
                redirect_stdout(output),
            ):
                exit_code = main(['--config', config, 'model', 'smoke', 'gpt'])

        self.assertEqual(exit_code, 0)
        self.assertEqual(create.call_args.kwargs['model'], 'configured-model')

    def test_config_auto_discovery_and_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = os.path.join(tmp, '.teaagent')
            os.makedirs(config_dir)
            with open(
                os.path.join(config_dir, 'config.json'), 'w', encoding='utf-8'
            ) as handle:
                json.dump(
                    {
                        'model': 'base-model',
                        'profiles': {'ci': {'model': 'profile-model'}},
                    },
                    handle,
                )
            adapter = FakeAdapter(['hello'])
            output = io.StringIO()

            cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with (
                    patch(
                        'teaagent.cli.create_llm_adapter', return_value=adapter
                    ) as create,
                    redirect_stdout(output),
                ):
                    exit_code = main(['--profile', 'ci', 'model', 'smoke', 'gpt'])
            finally:
                os.chdir(cwd)

        self.assertEqual(exit_code, 0)
        self.assertEqual(create.call_args.kwargs['model'], 'profile-model')

    def test_audit_list_show_and_prune(self) -> None:
        from teaagent.audit import AuditLogger

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '.teaagent' / 'runs' / 'run-1.jsonl'
            logger = AuditLogger(path=path)
            logger.record('run_started', 'run-1', task='demo')

            list_output = io.StringIO()
            with redirect_stdout(list_output):
                list_code = main(['audit', 'list', '--root', tmp])
            listed = json.loads(list_output.getvalue())

            show_output = io.StringIO()
            with redirect_stdout(show_output):
                show_code = main(['audit', 'show', 'run-1', '--root', tmp])
            shown = json.loads(show_output.getvalue())

            prune_output = io.StringIO()
            with redirect_stdout(prune_output):
                prune_code = main(['audit', 'prune', '--root', tmp, '--all'])
            pruned = json.loads(prune_output.getvalue())

        self.assertEqual(list_code, 0)
        self.assertEqual(show_code, 0)
        self.assertEqual(prune_code, 0)
        self.assertEqual(listed[0]['run_id'], 'run-1')
        self.assertEqual(shown[0]['event_type'], 'run_started')
        self.assertEqual(pruned['count'], 1)


if __name__ == '__main__':
    unittest.main()
