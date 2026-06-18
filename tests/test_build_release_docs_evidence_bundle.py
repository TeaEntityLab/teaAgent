"""Tests for release documentation evidence bundle."""

from __future__ import annotations

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_module():
    script = (
        Path(__file__).resolve().parents[1]
        / 'scripts'
        / 'build_release_docs_evidence_bundle.py'
    )
    spec = spec_from_file_location('build_release_docs_evidence_bundle_test', script)
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_open_risks_filters_fixed_rows(tmp_path: Path) -> None:
    module = _load_module()
    register = tmp_path / 'risk.md'
    register.write_text(
        '\n'.join(
            [
                '| ID | Category | Description | L | I | Score | Status | Priority |',
                '|---|---|---|---|---|---|---|---|',
                '| SEC-05 | Budget | injectable cost | L | H | 3 | **OPEN** | P2 |',
                '| SEC-07 | Isolation | hardened docker | H | H | 9 | **FIXED 2026-06-05** | — |',
            ]
        ),
        encoding='utf-8',
    )
    rows = module.parse_open_risks(register)
    assert [row['id'] for row in rows] == ['SEC-05']


def test_format_release_docs_evidence_includes_sections() -> None:
    module = _load_module()
    bundle = {
        'ok': True,
        'created_at': '2026-06-06T12:00:00+00:00',
        'git': {'commit': 'abc123', 'branch': 'main', 'dirty': False},
        'regenerate_commands': [
            'python3 scripts/build_release_docs_evidence_bundle.py',
        ],
        'docs_freshness': {
            'scanned': 17,
            'needs_attention': 0,
            'by_owner': {},
            'stale_threshold_days': 90,
        },
        'roadmap_excerpt': {
            'horizons': [
                {
                    'id': 'H0',
                    'name': 'Claim hygiene',
                    'status': 'In Progress',
                    'confidence': 'Medium',
                    'next_gate': 'DOCOPT-012',
                }
            ],
            'milestones': [
                {
                    'id': 'M0',
                    'target': '1-2 weeks',
                    'status': 'Pending',
                    'next_gate': 'GOV-002 complete',
                }
            ],
        },
        'open_risks': [
            {
                'id': 'SEC-05',
                'category': 'Budget',
                'description': 'injectable cost',
                'status': '**OPEN**',
                'priority': 'P2',
            }
        ],
    }
    text = module.format_release_docs_evidence_markdown(bundle)
    assert 'Release Documentation Evidence Bundle' in text
    assert 'Reproduce Commands' in text
    assert 'Documentation Freshness' in text
    assert 'Open Residual Risks' in text
    assert 'SEC-05' in text


def test_build_release_docs_evidence_bundle_for_repo() -> None:
    root = Path(__file__).resolve().parents[1]
    module = _load_module()
    bundle = module.build_release_docs_evidence_bundle(
        repo_root=root,
        run_gates=False,
    )
    assert bundle['git']['commit']
    assert bundle['docs_freshness']['scanned'] > 0
    assert isinstance(bundle['open_risks'], list)


def test_check_preserves_recorded_gate_results(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    bundle = module.build_release_docs_evidence_bundle(
        repo_root=Path(__file__).resolve().parents[1],
        run_gates=False,
    )
    bundle['commands'] = [
        {
            'cmd': 'python3 scripts/validate_docs_consistency.py',
            'exit_code': 0,
            'stdout': 'passed',
            'stderr': '',
        }
    ]
    bundle['ok'] = True
    markdown_path = tmp_path / 'evidence.md'
    json_path = tmp_path / 'evidence.json'
    markdown_path.write_text(
        module.format_release_docs_evidence_markdown(bundle), encoding='utf-8'
    )
    json_path.write_text(json.dumps(bundle), encoding='utf-8')

    current = {**bundle, 'commands': [], 'ok': True}
    monkeypatch.setattr(
        module,
        'build_release_docs_evidence_bundle',
        lambda **_kwargs: current,
    )

    assert (
        module.check_release_docs_evidence_bundle(
            repo_root=tmp_path,
            markdown_path=markdown_path,
            json_path=json_path,
        )
        == []
    )
