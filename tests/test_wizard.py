from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from teaagent.wizard import (
    merge_env_exports,
    read_existing_exports,
    redact_wizard_payload,
    resolve_api_key,
    run_first_session_setup,
)


def test_redact_wizard_payload_hides_secret_keys() -> None:
    payload = {
        'ok': True,
        'configured': {'api_key_present': True, 'auth_token': 'secret-token'},
        'launch_command': 'teaagent mcp serve --auth-token Bearer sk-live',
    }
    redacted = redact_wizard_payload(payload)
    text = json.dumps(redacted)
    assert 'secret-token' not in text
    assert 'sk-live' not in text
    assert redacted['configured']['auth_token'] == '[redacted]'


def test_merge_env_exports_preserves_existing_keys() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        env_path = Path(tmp) / '.teaagent' / 'env'
        env_path.parent.mkdir(parents=True)
        env_path.write_text(
            '# existing\nexport OTHER_KEY=keep-me\n',
            encoding='utf-8',
        )
        merge_env_exports(
            env_path,
            {'OPENAI_API_KEY': 'sk-new'},
            '# merged',
        )
        exports = read_existing_exports(env_path)
        assert exports['OTHER_KEY'] == 'keep-me'
        assert exports['OPENAI_API_KEY'] == 'sk-new'
        content = env_path.read_text(encoding='utf-8')
        assert "export OPENAI_API_KEY='sk-new'" in content or 'sk-new' in content


def test_resolve_api_key_prefers_flag_then_env() -> None:
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'from-env'}, clear=True):
        key, source = resolve_api_key('gpt', api_key='from-flag', prompt=False)
        assert key == 'from-flag'
        assert source == 'flag'
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'from-env'}, clear=True):
        key2, source2 = resolve_api_key('gpt', prompt=False)
        assert key2 == 'from-env'
        assert source2 == 'env'


def test_redact_wizard_payload_bearer_and_export_lines() -> None:
    payload = {
        'launch_command': 'teaagent mcp serve --auth-token Bearer sk-live',
        'export_line': 'export OPENAI_API_KEY=sk-test123',
        'plain_text': 'hello world',
    }
    redacted = redact_wizard_payload(payload)
    text = json.dumps(redacted)
    assert 'sk-live' not in text
    assert 'Bearer [redacted]' in text
    assert redacted['plain_text'] == 'hello world'


def test_read_existing_exports_handles_non_existent_and_malformed(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / 'env'
    assert read_existing_exports(env_file) == {}
    env_file.write_text(
        'export KEY_WITHOUT_VALUE=\nexport \nexport ONLY_KEY\nnot_an_export\n',
        encoding='utf-8',
    )
    exports = read_existing_exports(env_file)
    assert exports['KEY_WITHOUT_VALUE'] == ''


def test_run_first_session_setup_non_interactive(tmp_path: Path) -> None:
    class Args:
        root = str(tmp_path)
        provider = 'gpt'
        api_key = 'sk-setup-test'
        permission_mode = 'read-only'
        max_iterations = 8
        max_tool_calls = 7
        context_profile = 'lean'
        heartbeat = 0.0
        daily_cost_cap_cents = 0
        write_env = True
        model = None

    def fake_check(provider: str) -> tuple[bool, str]:
        return provider == 'gpt', 'configured for test'

    result = run_first_session_setup(Args(), check_llm=fake_check)
    payload = result.to_dict()
    assert payload['ok'] is True
    assert payload['mode'] == 'setup'
    assert payload['safe_command']
    assert 'sk-setup-test' not in json.dumps(payload)
    assert (tmp_path / '.teaagent' / 'config.json').exists()
    assert payload['configured']['api_key_present'] is True
