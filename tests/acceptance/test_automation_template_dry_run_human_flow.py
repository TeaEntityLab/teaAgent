"""Test module for automation template dry-run human-readable output.

This module tests that automation templates produce human-readable dry-run checklists
when using the --human flag. This helps users understand what an automation will do
before enabling it, with clear explanations of provenance, permissions, and configuration.

Key concepts tested:
- Template Dry-Run: Automation template --dry-run validates configuration
- Human Output: --human flag produces readable checklist format
- Provenance Digest: Template includes provenance digest for verification
- Allowed Toolsets: Dry-run shows which toolsets are allowed
- Readiness Check: Ticket ready status is computed and displayed

Acceptance Criteria:
- AC1: Template dry-run with --human returns human-readable output
- AC2: Human output includes template name
- AC3: Human output includes provenance digest (sha256:)
- AC4: Human output includes collector command if present
- AC5: Human output includes allowed toolsets (e.g., read-only)
- AC6: Human output includes dry-run readiness status

Technical Details:
- Automation templates are predefined configurations for common patterns
- --dry-run validates the template without creating an automation
- --human formats the output as a readable checklist instead of JSON
- Provenance digest (sha256) verifies template integrity
- Allowed toolsets are derived from permission_mode and write_source
- Readiness checks: acceptance_criteria, task clarity, collector integrity

References:
- Automation v2 design: /docs/architecture/automation_v2.md
- Template spec: /docs/specs/automation_templates.md
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main


def test_automation_template_dry_run_human_flow(tmp_path: Path) -> None:
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(
            [
                'agent',
                'automation',
                'template',
                'repo-watch',
                '--dry-run',
                '--human',
                '--root',
                str(tmp_path),
            ]
        )
    assert code == 0
    payload = json.loads(out.getvalue())
    assert payload['status'] == 'dry_run'
    assert payload['template'] == 'repo-watch'
    assert payload['ticket']['ready'] is True
    assert payload['ticket']['provenance_digest'].startswith('sha256:')
    assert 'read-only' in payload['ticket']['allowed_toolsets']
    human = payload['human']
    assert 'repo-watch' in human
    assert 'Provenance digest:' in human
    assert 'Collector command:' in human
    assert 'Dry-run: ready' in human
