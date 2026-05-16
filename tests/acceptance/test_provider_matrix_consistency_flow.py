"""AC-NEW-18: Provider/docs consistency flow.

As a user, I want provider names, default models, and smoke/doctor examples to
stay consistent across CLI behavior and docs, so first-run setup does not drift.

Acceptance criteria:
- README provider count matches runtime provider registry size.
- README environment variable examples include every provider API key env var.
- USAGE provider table matches runtime provider keys, env vars, and defaults.
- `teaagent model providers` output matches runtime provider registry.
- Docs `doctor model` / `model smoke` examples only reference valid providers.
"""

from __future__ import annotations

import io
import json
import re
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main
from teaagent.llm import available_providers
from teaagent.llm._config import PROVIDER_CONFIGS


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _extract_usage_provider_rows(usage_md: str) -> dict[str, tuple[str, str]]:
    rows: dict[str, tuple[str, str]] = {}
    for line in usage_md.splitlines():
        if not line.strip().startswith('|'):
            continue
        if line.strip().startswith('|---'):
            continue
        columns = [col.strip() for col in line.strip().strip('|').split('|')]
        if len(columns) < 4:
            continue
        provider = columns[0]
        if provider not in PROVIDER_CONFIGS:
            continue
        env_match = re.search(r'`([^`]+)`', columns[1])
        if not env_match:
            continue
        default_model = columns[2].rstrip('*').strip()
        rows[provider] = (env_match.group(1), default_model)
    return rows


def _extract_doc_providers(pattern: str, text: str) -> set[str]:
    return {match.group(1) for match in re.finditer(pattern, text)}


def test_provider_registry_matches_docs_and_cli_output() -> None:
    root = _repo_root()
    readme = (root / 'README.md').read_text(encoding='utf-8')
    usage = (root / 'docs' / 'USAGE.md').read_text(encoding='utf-8')
    cli_doc = (root / 'docs' / 'cli.md').read_text(encoding='utf-8')

    providers = available_providers()
    assert providers == sorted(PROVIDER_CONFIGS.keys())

    provider_count_match = re.search(r'\((\d+) providers\)', readme)
    assert provider_count_match, (
        'README must include provider count in architecture diagram'
    )
    assert int(provider_count_match.group(1)) == len(providers)

    env_exports = set(re.findall(r'export\s+([A-Z0-9_]+)=', readme))
    expected_env_vars = {cfg.api_key_env for cfg in PROVIDER_CONFIGS.values()}
    assert expected_env_vars.issubset(env_exports)

    usage_count_match = re.search(r'supports\s+(\d+)\s+LLM providers', usage)
    assert usage_count_match, 'USAGE must state provider count'
    assert int(usage_count_match.group(1)) == len(providers)

    usage_rows = _extract_usage_provider_rows(usage)
    assert set(usage_rows.keys()) == set(providers)
    for provider, cfg in PROVIDER_CONFIGS.items():
        env_var, default_model = usage_rows[provider]
        assert env_var == cfg.api_key_env
        assert default_model == cfg.default_model

    doctor_providers = _extract_doc_providers(
        r'teaagent doctor model ([a-z0-9-]+)', cli_doc
    )
    assert doctor_providers == set(providers)

    smoke_providers = _extract_doc_providers(
        r'teaagent model smoke ([a-z0-9-]+)', cli_doc
    )
    assert smoke_providers, 'cli.md should include at least one smoke command'
    assert smoke_providers.issubset(set(providers))

    output = io.StringIO()
    with redirect_stdout(output):
        exit_code = main(['model', 'providers'])
    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert payload == providers
