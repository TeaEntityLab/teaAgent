#!/usr/bin/env python3
"""Exercise H4 shadow wiring in a scratch workspace (ADR-0031 criterion 1 prep).

Creates a temporary workspace with a denying approval policy and an RBAC
assignment that lacks permission, invokes the two H4 shadow entry points,
and writes the resulting `h4_governance_shadow` receipts to a scratch
audit JSONL. The output can be fed to `scripts/prepare_h4_evidence.py`
to demonstrate that the 30-day window analysis is exercisable before
2026-09-12, without touching production audit logs or flipping modes.

Usage:
  python3 scripts/exercise_h4_shadow_demo.py --output /tmp/h4_demo.jsonl
  python3 scripts/prepare_h4_evidence.py --audit-log /tmp/h4_demo.jsonl --since 2026-08-13 --until 2026-09-11
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

# Ensure repo root on path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / 'scripts'))
from teaagent.audit import AuditLogger  # noqa: E402
from teaagent.governance.h4_integration import (  # noqa: E402
    check_subagent_launch_rbac,
    evaluate_approval_policy_shadow,
)


def _write_denying_policy(root: Path) -> None:
    policies = root / '.teaagent' / 'policies'
    policies.mkdir(parents=True, exist_ok=True)
    # Minimal approval policy that denies a specific tool; the engine will
    # evaluate it and the shadow wrapper will record a denial receipt.
    policy = {
        'policy_id': 'h4-demo-deny-write',
        'description': 'Demo deny for H4 shadow exercise (not RBAC)',
        'policy_type': 'approval',
        'effect': 'deny',
        'rules': [
            {
                'field': 'tool_name',
                'operator': 'equals',
                'value': 'workspace_write_file',
            }
        ],
    }
    (policies / 'h4-demo-deny.json').write_text(
        json.dumps(policy, indent=2), encoding='utf-8'
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--output', default='/tmp/h4_demo.jsonl', help='Scratch audit JSONL to write'
    )
    parser.add_argument(
        '--workspace', default=None, help='Use existing workspace instead of temp'
    )
    args = parser.parse_args()

    output = Path(args.output)
    if args.workspace:
        root = Path(args.workspace).resolve()
        tmp = None
    else:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)

    try:
        # Prepare workspace with denying policy
        (root / '.teaagent').mkdir(parents=True, exist_ok=True)
        _write_denying_policy(root)
        # Also ensure RBAC store exists (empty = no roles, so any assignee lacks permission)
        (root / '.teaagent' / 'roles').mkdir(parents=True, exist_ok=True)
        (root / '.teaagent' / 'role-assignments').mkdir(parents=True, exist_ok=True)

        audit_path = root / '.teaagent' / 'audit.jsonl'
        audit = AuditLogger(path=audit_path)

        # Exercise approval surface — should record a shadow receipt with allowed=False
        # (if policy matches) or allowed=True (if not). Either way a receipt is recorded.
        evaluate_approval_policy_shadow(
            workspace_root=root,
            audit=audit,
            run_id='h4-demo-approval',
            tool_name='workspace_write_file',
            arguments={'path': '/tmp/demo.txt', 'content': 'hello'},
            destructive=False,
            call_id='call_demo_001',
        )

        # Exercise RBAC surface — with no roles, this will be denied and recorded
        # as allowed=False, enforced=False (shadow). This creates a denial candidate
        # for criterion-1.
        check_subagent_launch_rbac(
            workspace_root=root,
            audit=audit,
            parent_run_id='h4-demo-rbac',
            assignee='demo-assignee-no-role',
            def_name='demo-subagent',
            depth=1,
        )

        # Copy audit JSONL to requested output for offline analysis
        if audit_path.is_file():
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(audit_path.read_text(encoding='utf-8'), encoding='utf-8')
            events = [
                json.loads(line)
                for line in output.read_text().splitlines()
                if line.strip()
            ]
            h4_events = [
                e
                for e in events
                if e.get('event_type') == 'h4_governance_shadow'
                or 'h4_governance_shadow' in str(e)
            ]
            print(
                f'Wrote {len(events)} audit events ({len(h4_events)} h4_governance_shadow) to {output}'
            )
            # Quick local validation: prepare_h4_evidence should find at least one denial
            from teaagent.governance.h4_evidence import (
                build_h4_evidence_report,
                load_events_from_paths,
            )

            report = build_h4_evidence_report(
                load_events_from_paths([output]), since='2026-08-13', until='2026-09-11'
            )
            print(
                f'Demo evidence: {report.observed_events} observed, {len(report.candidates)} denial candidates, {report.skipped_malformed} malformed'
            )
            if report.candidates:
                print(
                    'Sample candidate:',
                    json.dumps(report.candidates[0].to_dict(), indent=2),
                )
            return 0
        else:
            print(f'No audit file at {audit_path}', file=sys.stderr)
            return 1
    finally:
        if tmp is not None:
            tmp.cleanup()


if __name__ == '__main__':
    raise SystemExit(main())
