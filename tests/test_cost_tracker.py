from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from teaagent.cost_tracker import CostTracker


def _write_run(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(e, sort_keys=True) for e in events]
    path.write_text('\n'.join(lines), encoding='utf-8')


class TestCostTracker:
    def test_parse_single_run_extracts_cost(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs_dir = root / '.teaagent' / 'runs'
            run_path = runs_dir / 'run-001.jsonl'

            _write_run(
                run_path,
                [
                    {
                        'event_id': 'ev1',
                        'event_type': 'run_started',
                        'run_id': 'run-001',
                        'created_at': '2026-06-01T10:00:00+00:00',
                        'payload': {'task': 'test task', 'label': 'feature:x'},
                    },
                    {
                        'event_id': 'ev2',
                        'event_type': 'run_completed',
                        'run_id': 'run-001',
                        'created_at': '2026-06-01T10:05:00+00:00',
                        'payload': {
                            'answer': 'done',
                            'cost_cents': 42.5,
                            'input_tokens': 100,
                            'output_tokens': 50,
                        },
                    },
                ],
            )

            tracker = CostTracker(root=tmp)
            report = tracker.report_by_label('feature:x')
            assert report['runs'] == 1
            assert report['cost_cents'] == 42.5
            assert report['input_tokens'] == 100
            assert report['output_tokens'] == 50
            assert report['run_ids'] == ['run-001']

    def test_report_by_label_filters_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs_dir = root / '.teaagent' / 'runs'

            _write_run(
                runs_dir / 'run-a.jsonl',
                [
                    {
                        'event_id': 'ev1',
                        'event_type': 'run_started',
                        'run_id': 'run-a',
                        'created_at': '2026-06-01T10:00:00+00:00',
                        'payload': {'label': 'label-a', 'model': 'gpt'},
                    },
                    {
                        'event_id': 'ev2',
                        'event_type': 'run_completed',
                        'run_id': 'run-a',
                        'created_at': '2026-06-01T10:05:00+00:00',
                        'payload': {'cost_cents': 10},
                    },
                ],
            )

            _write_run(
                runs_dir / 'run-b.jsonl',
                [
                    {
                        'event_id': 'ev1',
                        'event_type': 'run_started',
                        'run_id': 'run-b',
                        'created_at': '2026-06-01T11:00:00+00:00',
                        'payload': {'label': 'label-b', 'model': 'claude'},
                    },
                    {
                        'event_id': 'ev2',
                        'event_type': 'run_completed',
                        'run_id': 'run-b',
                        'created_at': '2026-06-01T11:05:00+00:00',
                        'payload': {'cost_cents': 20},
                    },
                ],
            )

            tracker = CostTracker(root=tmp)
            report_b = tracker.report_by_label('label-b')
            assert report_b['runs'] == 1
            assert report_b['cost_cents'] == 20

            report_unknown = tracker.report_by_label('nonexistent')
            assert report_unknown['runs'] == 0
            assert report_unknown['cost_cents'] == 0.0

    def test_report_by_model_aggregates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs_dir = root / '.teaagent' / 'runs'

            _write_run(
                runs_dir / 'run-1.jsonl',
                [
                    {
                        'event_id': 'ev1',
                        'event_type': 'run_started',
                        'run_id': 'run-1',
                        'created_at': '2026-06-01T10:00:00+00:00',
                        'payload': {'model': 'gpt'},
                    },
                    {
                        'event_id': 'ev2',
                        'event_type': 'run_completed',
                        'run_id': 'run-1',
                        'created_at': '2026-06-01T10:05:00+00:00',
                        'payload': {'cost_cents': 15, 'input_tokens': 200, 'output_tokens': 100},
                    },
                ],
            )

            _write_run(
                runs_dir / 'run-2.jsonl',
                [
                    {
                        'event_id': 'ev1',
                        'event_type': 'run_started',
                        'run_id': 'run-2',
                        'created_at': '2026-06-01T11:00:00+00:00',
                        'payload': {'model': 'gpt'},
                    },
                    {
                        'event_id': 'ev2',
                        'event_type': 'run_completed',
                        'run_id': 'run-2',
                        'created_at': '2026-06-01T11:05:00+00:00',
                        'payload': {'cost_cents': 25, 'input_tokens': 300, 'output_tokens': 150},
                    },
                ],
            )

            tracker = CostTracker(root=tmp)
            report = tracker.report_by_model()
            gpt_data = report['by_model']['gpt']
            assert gpt_data['runs'] == 2
            assert gpt_data['cost_cents'] == 40
            assert gpt_data['input_tokens'] == 500
            assert gpt_data['output_tokens'] == 250

    def test_report_all_includes_by_day(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs_dir = root / '.teaagent' / 'runs'

            _write_run(
                runs_dir / 'run-1.jsonl',
                [
                    {
                        'event_id': 'ev1',
                        'event_type': 'run_started',
                        'run_id': 'run-1',
                        'created_at': '2026-06-01T10:00:00+00:00',
                        'payload': {'label': 'feature:x'},
                    },
                    {
                        'event_id': 'ev2',
                        'event_type': 'run_completed',
                        'run_id': 'run-1',
                        'created_at': '2026-06-01T10:05:00+00:00',
                        'payload': {'cost_cents': 10},
                    },
                ],
            )

            tracker = CostTracker(root=tmp)
            report = tracker.report_all(days=365)
            assert 'by_label' in report
            assert 'by_day' in report
            assert 'by_model' in report
            assert 'total' in report
            assert report['total']['runs'] == 1
            assert report['total']['cost_cents'] == 10

    def test_export_csv_produces_valid_content(self) -> None:
        data = {
            'by_label': {
                'feature:a': {'runs': 2, 'cost_cents': 30, 'input_tokens': 400, 'output_tokens': 200},
            },
            'by_day': {
                '2026-06-01': {'runs': 2, 'cost_cents': 30, 'input_tokens': 400, 'output_tokens': 200},
            },
            'by_model': {
                'gpt': {'runs': 2, 'cost_cents': 30, 'input_tokens': 400, 'output_tokens': 200},
            },
            'total': {'runs': 2, 'cost_cents': 30, 'input_tokens': 400, 'output_tokens': 200},
        }

        csv_output = CostTracker.export_csv(data)
        assert 'Total Runs,2' in csv_output
        assert 'Total Cost (cents),30' in csv_output
        assert 'feature:a' in csv_output
        assert '2026-06-01' in csv_output
        assert 'gpt' in csv_output

    def test_empty_runs_dir_returns_zero_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tracker = CostTracker(root=tmp)
            report = tracker.report_all()
            assert report['total']['runs'] == 0
            assert report['total']['cost_cents'] == 0.0
