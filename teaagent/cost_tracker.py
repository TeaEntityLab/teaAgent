"""Cost tracking from TeaAgent run audit logs.

Reads per-run JSONL audit logs under ``.teaagent/runs/`` and aggregates
cost data by label, day, and model.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class CostTracker:
    """Aggregate cost data from run audit logs.

    Scans the ``.teaagent/runs/`` directory for JSONL files, extracts
    cost-related audit events (``run_completed``, ``run_failed``), and
    provides summary reports.
    """

    def __init__(self, root: str | Path = '.') -> None:
        self._root = Path(root).resolve()
        self._runs_dir = self._root / '.teaagent' / 'runs'

    def _parse_runs(self) -> list[dict[str, Any]]:
        if not self._runs_dir.is_dir():
            return []
        runs: list[dict[str, Any]] = []
        for jsonl_path in sorted(self._runs_dir.glob('*.jsonl')):
            run_data = self._parse_single_run(jsonl_path)
            if run_data is not None:
                runs.append(run_data)
        return runs

    def _parse_single_run(self, path: Path) -> dict[str, Any] | None:
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except OSError:
            return None
        run_id = path.stem
        label = None
        cost_cents = 0.0
        model = None
        created_at = None
        status = 'unknown'
        input_tokens = 0
        output_tokens = 0

        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_type = event.get('event_type', '')
            payload = event.get('payload', {})

            if event_type == 'run_started':
                label = label or payload.get('label')
                model = model or payload.get('model')
                created_at = event.get('created_at', created_at)

            if event_type in ('run_completed', 'run_failed'):
                status = event_type.replace('run_', '')
                cost_cents = float(payload.get('cost_cents', cost_cents))
                input_tokens = int(payload.get('input_tokens', 0))
                output_tokens = int(payload.get('output_tokens', 0))

        if created_at is None:
            stat = path.stat()
            created_at = datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat()

        return {
            'run_id': run_id,
            'label': label or 'unlabeled',
            'model': model or 'unknown',
            'cost_cents': cost_cents,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'status': status,
            'created_at': created_at,
        }

    def report_by_label(self, label: str) -> dict[str, Any]:
        runs = [r for r in self._parse_runs() if r['label'] == label]
        return self._build_summary(runs)

    def report_by_day(self, days: int = 30) -> dict[str, Any]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        runs = self._parse_runs()
        by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for run in runs:
            try:
                dt = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
            except (ValueError, TypeError):
                continue
            if dt >= cutoff:
                day_key = dt.strftime('%Y-%m-%d')
                by_day[day_key].append(run)
        return {
            'days': days,
            'by_day': {
                day: self._build_summary(runs)
                for day, runs in sorted(by_day.items())
            },
        }

    def report_by_model(self) -> dict[str, Any]:
        runs = self._parse_runs()
        by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for run in runs:
            by_model[run['model']].append(run)
        return {
            'by_model': {
                model: self._build_summary(runs)
                for model, runs in sorted(by_model.items())
            },
        }

    def report_all(self, days: int = 30) -> dict[str, Any]:
        by_day = self.report_by_day(days=days)
        by_model = self.report_by_model()
        by_label_runs = self._parse_runs()
        by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for run in by_label_runs:
            by_label[run['label']].append(run)
        return {
            'by_label': {
                lbl: self._build_summary(runs)
                for lbl, runs in sorted(by_label.items())
            },
            'by_day': by_day['by_day'],
            'by_model': by_model['by_model'],
            'total': self._build_summary(by_label_runs),
        }

    def _build_summary(self, runs: list[dict[str, Any]]) -> dict[str, Any]:
        if not runs:
            return {'runs': 0, 'cost_cents': 0.0, 'input_tokens': 0, 'output_tokens': 0}
        return {
            'runs': len(runs),
            'cost_cents': sum(r['cost_cents'] for r in runs),
            'input_tokens': sum(r['input_tokens'] for r in runs),
            'output_tokens': sum(r['output_tokens'] for r in runs),
            'run_ids': [r['run_id'] for r in runs],
        }

    @staticmethod
    def export_csv(data: dict[str, Any]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)

        total = data.get('total', {})
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Runs', total.get('runs', 0)])
        writer.writerow(['Total Cost (cents)', total.get('cost_cents', 0)])
        writer.writerow(['Total Input Tokens', total.get('input_tokens', 0)])
        writer.writerow(['Total Output Tokens', total.get('output_tokens', 0)])
        writer.writerow([])

        writer.writerow(['By Label', 'Runs', 'Cost (cents)', 'Input Tokens', 'Output Tokens'])
        for label, summary in data.get('by_label', {}).items():
            writer.writerow([
                label,
                summary.get('runs', 0),
                summary.get('cost_cents', 0),
                summary.get('input_tokens', 0),
                summary.get('output_tokens', 0),
            ])

        writer.writerow([])
        writer.writerow(['By Day', 'Runs', 'Cost (cents)', 'Input Tokens', 'Output Tokens'])
        for day, summary in data.get('by_day', {}).items():
            writer.writerow([
                day,
                summary.get('runs', 0),
                summary.get('cost_cents', 0),
                summary.get('input_tokens', 0),
                summary.get('output_tokens', 0),
            ])

        writer.writerow([])
        writer.writerow(['By Model', 'Runs', 'Cost (cents)', 'Input Tokens', 'Output Tokens'])
        for model, summary in data.get('by_model', {}).items():
            writer.writerow([
                model,
                summary.get('runs', 0),
                summary.get('cost_cents', 0),
                summary.get('input_tokens', 0),
                summary.get('output_tokens', 0),
            ])

        return output.getvalue()
