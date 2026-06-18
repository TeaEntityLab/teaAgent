"""Release documentation evidence bundle (DOW-024 / DOCOPT-016).

Generates a dated markdown (+ JSON) bundle with git metadata, gate commands,
roadmap excerpt, documentation freshness, and open residual risks.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_MD = _REPO_ROOT / 'docs' / 'generated' / 'release-docs-evidence.md'
_DEFAULT_JSON = _REPO_ROOT / 'docs' / 'generated' / 'release-docs-evidence.json'
_RISK_REGISTER = (
    _REPO_ROOT / 'docs' / 'security' / 'risk-register-and-threat-model-2026-06-02.md'
)
_ROADMAP_STATUS = _REPO_ROOT / 'docs' / 'roadmap-status.md'

_RISK_ROW = re.compile(r'^\|\s*((?:SEC|DS|SC)-\d+)\s*\|')
_HORIZON_ROW = re.compile(r'^\|\s*(H\d+)\s*\|')
_MILESTONE_ROW = re.compile(r'^\|\s*(M\d+)\s*\|')


def _load_report_docs_aging():
    script = _REPO_ROOT / 'scripts' / 'report_docs_aging.py'
    spec = importlib.util.spec_from_file_location('report_docs_aging_bundle', script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run_command(argv: list[str], *, cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    return {
        'cmd': ' '.join(shlex.quote(part) for part in argv),
        'exit_code': proc.returncode,
        'stdout': proc.stdout,
        'stderr': proc.stderr,
    }


def _git_field(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(
        ['git', *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ''


def parse_open_risks(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        match = _RISK_ROW.match(line)
        if not match:
            continue
        parts = [part.strip() for part in line.strip().strip('|').split('|')]
        if len(parts) < 8:
            continue
        risk_id, category, description, status, priority = (
            parts[0],
            parts[1],
            parts[2],
            parts[6],
            parts[7],
        )
        status_upper = status.upper()
        if 'OPEN' not in status_upper:
            continue
        if any(token in status_upper for token in ('FIXED', 'DONE', 'CLOSE')):
            continue
        rows.append(
            {
                'id': risk_id,
                'category': category,
                'description': description,
                'status': status,
                'priority': priority,
            }
        )
    return rows


def parse_roadmap_excerpt(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {'horizons': [], 'milestones': []}
    horizons: list[dict[str, str]] = []
    milestones: list[dict[str, str]] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        horizon_match = _HORIZON_ROW.match(line)
        if horizon_match:
            parts = [part.strip() for part in line.strip().strip('|').split('|')]
            if len(parts) >= 8:
                horizons.append(
                    {
                        'id': parts[0],
                        'name': parts[1],
                        'status': parts[4],
                        'confidence': parts[5],
                        'next_gate': parts[6],
                    }
                )
            continue
        milestone_match = _MILESTONE_ROW.match(line)
        if milestone_match:
            parts = [part.strip() for part in line.strip().strip('|').split('|')]
            if len(parts) >= 8:
                milestones.append(
                    {
                        'id': parts[0],
                        'target': parts[1],
                        'status': parts[5],
                        'next_gate': parts[7],
                    }
                )
    return {
        'horizons': horizons[:6],
        'milestones': milestones[:4],
    }


def summarize_docs_freshness(*, repo_root: Path) -> dict[str, Any]:
    aging = _load_report_docs_aging()
    rows = [
        aging._scan_doc(entry, repo_root=repo_root, stale_days=aging.STALE_DAYS)
        for entry in aging.DOC_REVIEW_REGISTRY
    ]
    stale_rows = [row for row in rows if row.status != 'fresh']
    grouped: dict[str, int] = {}
    for row in stale_rows:
        grouped[row.owner] = grouped.get(row.owner, 0) + 1
    return {
        'scanned': len(rows),
        'needs_attention': len(stale_rows),
        'by_owner': grouped,
        'stale_threshold_days': aging.STALE_DAYS,
    }


def build_release_docs_evidence_bundle(
    *,
    repo_root: Path = _REPO_ROOT,
    run_gates: bool = True,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    commands: list[dict[str, Any]] = []

    if run_gates:
        commands.append(
            _run_command(
                [sys.executable, 'scripts/validate_docs_consistency.py'],
                cwd=repo_root,
            )
        )
        commands.append(
            _run_command(
                [sys.executable, 'scripts/report_docs_aging.py', '--check'],
                cwd=repo_root,
            )
        )

    git = {
        'branch': _git_field(repo_root, 'rev-parse', '--abbrev-ref', 'HEAD'),
        'commit': _git_field(repo_root, 'rev-parse', 'HEAD'),
        'dirty': bool(_git_field(repo_root, 'status', '--porcelain')),
    }
    docs_freshness = summarize_docs_freshness(repo_root=repo_root)
    open_risks = parse_open_risks(_RISK_REGISTER)
    roadmap = parse_roadmap_excerpt(_ROADMAP_STATUS)

    return {
        'ok': all(cmd['exit_code'] == 0 for cmd in commands),
        'created_at': created_at,
        'repo_root': str(repo_root),
        'git': git,
        'commands': commands,
        'docs_freshness': docs_freshness,
        'roadmap_excerpt': roadmap,
        'open_risks': open_risks,
        'regenerate_commands': [
            'python3 scripts/build_release_docs_evidence_bundle.py',
            'python3 scripts/validate_docs_consistency.py',
            'python3 scripts/report_docs_aging.py',
        ],
    }


def format_release_docs_evidence_markdown(bundle: dict[str, Any]) -> str:
    git = bundle['git']
    docs = bundle['docs_freshness']
    lines = [
        '# Release Documentation Evidence Bundle (Generated)',
        '',
        f'**Generated:** {bundle["created_at"]}',
        f'**Git commit:** `{git["commit"]}` on `{git["branch"]}`',
        f'**Working tree dirty:** {"yes" if git["dirty"] else "no"}',
        '',
        'Regenerate: `python3 scripts/build_release_docs_evidence_bundle.py`',
        '',
        '## Reproduce Commands',
        '',
    ]
    for cmd in bundle['regenerate_commands']:
        lines.append(f'- `{cmd}`')
    if bundle.get('commands'):
        lines.extend(
            [
                '',
                '## Last Gate Run',
                '',
                f'- Overall gate status: **{"pass" if bundle["ok"] else "fail"}**',
            ]
        )
        for cmd in bundle['commands']:
            status = 'pass' if cmd['exit_code'] == 0 else 'fail'
            lines.append(f'- `{cmd["cmd"]}` — **{status}** (exit {cmd["exit_code"]})')
    lines.extend(
        [
            '',
            '## Documentation Freshness',
            '',
            f'- Current-truth docs scanned: **{docs["scanned"]}**',
            f'- Needs attention: **{docs["needs_attention"]}** (>{docs["stale_threshold_days"]} days)',
        ]
    )
    if docs['by_owner']:
        lines.append('- Stale by owner surface:')
        for owner in sorted(docs['by_owner']):
            lines.append(f'  - `{owner}`: {docs["by_owner"][owner]}')
    else:
        lines.append('- All scanned current-truth docs are fresh.')

    lines.extend(['', '## Roadmap Excerpt', ''])
    for horizon in bundle['roadmap_excerpt']['horizons']:
        lines.append(
            f'- `{horizon["id"]}` {horizon["name"]}: **{horizon["status"]}** '
            f'(confidence {horizon["confidence"]}, next gate {horizon["next_gate"]})'
        )
    for milestone in bundle['roadmap_excerpt']['milestones']:
        lines.append(
            f'- `{milestone["id"]}` ({milestone["target"]}): **{milestone["status"]}** '
            f'(next gate {milestone["next_gate"]})'
        )

    lines.extend(['', '## Open Residual Risks', ''])
    open_risks = bundle['open_risks']
    if not open_risks:
        lines.append('No OPEN rows found in the risk register.')
    else:
        lines.append('| ID | Category | Priority | Description |')
        lines.append('| --- | --- | --- | --- |')
        for row in open_risks:
            desc = row['description'].replace('|', '\\|')
            if len(desc) > 120:
                desc = desc[:117] + '...'
            lines.append(
                f'| {row["id"]} | {row["category"]} | {row["priority"]} | {desc} |'
            )
    lines.append('')
    return '\n'.join(lines)


def write_release_docs_evidence_bundle(
    *,
    repo_root: Path = _REPO_ROOT,
    markdown_path: Path = _DEFAULT_MD,
    json_path: Path = _DEFAULT_JSON,
    run_gates: bool = True,
) -> dict[str, Any]:
    bundle = build_release_docs_evidence_bundle(
        repo_root=repo_root,
        run_gates=run_gates,
    )
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        format_release_docs_evidence_markdown(bundle),
        encoding='utf-8',
    )
    json_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    return bundle


def _normalize_generated_markdown(text: str) -> str:
    return re.sub(
        r'\*\*Generated:\*\* .+',
        '**Generated:** <normalized>',
        text,
        count=1,
    )


def check_release_docs_evidence_bundle(
    *,
    repo_root: Path = _REPO_ROOT,
    markdown_path: Path = _DEFAULT_MD,
    json_path: Path = _DEFAULT_JSON,
) -> list[str]:
    errors: list[str] = []
    if not markdown_path.is_file():
        errors.append(f'missing generated bundle: {markdown_path}')
    if not json_path.is_file():
        errors.append(f'missing generated JSON bundle: {json_path}')
    if errors:
        return errors

    try:
        recorded = json.loads(json_path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError) as exc:
        return [f'invalid generated JSON bundle: {exc}']

    expected = build_release_docs_evidence_bundle(repo_root=repo_root, run_gates=False)
    # Gate output is historical evidence from generation time. Preserve it while
    # recomputing fields that describe the current repository.
    expected['commands'] = recorded.get('commands', [])
    expected['ok'] = recorded.get('ok', False)
    expected_md = _normalize_generated_markdown(
        format_release_docs_evidence_markdown(expected)
    )
    actual_md = _normalize_generated_markdown(markdown_path.read_text(encoding='utf-8'))
    if actual_md != expected_md:
        errors.append(
            'stale release docs evidence bundle: regenerate with '
            'python3 scripts/build_release_docs_evidence_bundle.py'
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Generate release documentation evidence bundle.'
    )
    parser.add_argument('--root', default='.', help='Repository root.')
    parser.add_argument(
        '--markdown-output',
        default=str(_DEFAULT_MD.relative_to(_REPO_ROOT)),
        help='Markdown output path.',
    )
    parser.add_argument(
        '--json-output',
        default=str(_DEFAULT_JSON.relative_to(_REPO_ROOT)),
        help='JSON output path.',
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Verify generated bundle matches current repo state.',
    )
    parser.add_argument(
        '--skip-gates',
        action='store_true',
        help='Do not run validate/aging gate commands while building.',
    )
    args = parser.parse_args()
    repo_root = Path(args.root).resolve()
    markdown_path = (repo_root / args.markdown_output).resolve()
    json_path = (repo_root / args.json_output).resolve()

    if args.check:
        errors = check_release_docs_evidence_bundle(
            repo_root=repo_root,
            markdown_path=markdown_path,
            json_path=json_path,
        )
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print('Release docs evidence bundle is current.')
        return 0

    bundle = write_release_docs_evidence_bundle(
        repo_root=repo_root,
        markdown_path=markdown_path,
        json_path=json_path,
        run_gates=not args.skip_gates,
    )
    print(f'Wrote {markdown_path}')
    print(f'Wrote {json_path}')
    return 0 if bundle['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
