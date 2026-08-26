from __future__ import annotations

import tempfile
from pathlib import Path

from teaagent.context_pack import build_context_pack
from teaagent.daily import (
    ContextProfile,
    build_harness_health_report,
    build_token_budget_report,
)
from teaagent.memory import MemoryCatalog


def test_token_budget_reports_contributors_and_cost() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'README.md').write_text('hello teaagent', encoding='utf-8')
        MemoryCatalog(root).add('summarize README.md for onboarding')
        memories = MemoryCatalog(root).search('summarize README.md', limit=5)
        pack = build_context_pack('summarize README.md', root=root)
        profile = ContextProfile(
            name='balanced',
            memory_limit=5,
            hydrate_lsp=True,
            search_graph=True,
            recent_run_replay=1,
            output_reserve_tokens=1024,
        )

        report = build_token_budget_report(
            task='summarize README.md',
            provider='gpt',
            model='gpt-4o-mini',
            context_pack=pack,
            memories=memories,
            tool_count=3,
            profile=profile,
        )

        payload = report.to_dict()
        assert payload['usage_level'] == 'green'
        assert payload['contributors']['expected_output_reserve'] == 1024
        assert payload['contributors']['context_pack'] > 0
        assert payload['estimated_cost_cents'] > 0


def test_unknown_model_context_window_degrades_to_unknown_zone() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pack = build_context_pack('inspect repo', root=root)
        profile = ContextProfile(
            name='lean',
            memory_limit=2,
            hydrate_lsp=False,
            search_graph=False,
            recent_run_replay=0,
            output_reserve_tokens=512,
        )

        report = build_token_budget_report(
            task='inspect repo',
            provider='ollama',
            model='custom-local-model',
            context_pack=pack,
            memories=[],
            tool_count=1,
            profile=profile,
        )

        assert report.max_context_tokens is None
        assert report.usage_level == 'unknown'
        assert 'model context window unknown' in report.recommendations[0]


def test_harness_health_warns_without_optional_indexes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        report = build_harness_health_report(
            tmp, {'healthy': True, 'failures': [], 'warnings': []}
        )

        payload = report.to_dict()
        assert payload['healthy']
        assert not any(payload['optional_indexes'].values())
        assert 'no optional context indexes are available' in payload['warnings']


def test_harness_health_warns_on_ambient_github_token(monkeypatch) -> None:
    monkeypatch.setenv('GITHUB_TOKEN', 'ambient-token')
    monkeypatch.delenv('GH_TOKEN', raising=False)
    with tempfile.TemporaryDirectory() as tmp:
        payload = build_harness_health_report(
            tmp, {'healthy': True, 'failures': [], 'warnings': []}
        ).to_dict()
    ambient = [w for w in payload['warnings'] if 'ambient credential' in w]
    assert len(ambient) == 1
    assert 'GITHUB_TOKEN' in ambient[0]
    assert 'EFX-002' in ambient[0]


def test_harness_health_silent_without_ambient_tokens(monkeypatch) -> None:
    monkeypatch.delenv('GITHUB_TOKEN', raising=False)
    monkeypatch.delenv('GH_TOKEN', raising=False)
    with tempfile.TemporaryDirectory() as tmp:
        payload = build_harness_health_report(
            tmp, {'healthy': True, 'failures': [], 'warnings': []}
        ).to_dict()
    assert not any('ambient credential' in w for w in payload['warnings'])
