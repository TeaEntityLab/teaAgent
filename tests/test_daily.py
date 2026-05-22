from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from teaagent.context_pack import build_context_pack
from teaagent.daily import (
    ContextProfile,
    build_harness_health_report,
    build_token_budget_report,
)
from teaagent.memory import MemoryCatalog


class DailyTokenBudgetTests(unittest.TestCase):
    def test_token_budget_reports_contributors_and_cost(self) -> None:
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
            self.assertEqual(payload['usage_level'], 'green')
            self.assertEqual(payload['contributors']['expected_output_reserve'], 1024)
            self.assertGreater(payload['contributors']['context_pack'], 0)
            self.assertGreater(payload['estimated_cost_cents'], 0)

    def test_unknown_model_context_window_degrades_to_unknown_zone(self) -> None:
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

            self.assertIsNone(report.max_context_tokens)
            self.assertEqual(report.usage_level, 'unknown')
            self.assertIn('model context window unknown', report.recommendations[0])

    def test_harness_health_warns_without_optional_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = build_harness_health_report(
                tmp, {'healthy': True, 'failures': [], 'warnings': []}
            )

            payload = report.to_dict()
            self.assertTrue(payload['healthy'])
            self.assertFalse(any(payload['optional_indexes'].values()))
            self.assertIn(
                'no optional context indexes are available', payload['warnings']
            )


if __name__ == '__main__':
    unittest.main()
