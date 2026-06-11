"""Test module for plan CLI command flow.

This module tests the plan command functionality, which generates reviewable
implementation plans without making any edits to the codebase. The plan command
is a critical safety feature that allows users to review proposed changes before
execution, supporting the "plan before edit" workflow.

Key concepts tested:
- Plan Artifact Generation: The plan command creates a markdown plan file
- Artifact Location: Plans are stored under .teaagent/plans/ directory
- Plan Structure: Plans include sections for Steps, Files likely touched, and Rollback
- Permission Mode: Plan command defaults to read-only mode for safety
- CLI Integration: Plan command integrates with the main CLI interface
- JSON Output: Plan command returns structured JSON with artifact path and context

Acceptance Criteria:
- AC1: Plan command creates a plan artifact file under .teaagent/plans/
- AC2: Plan artifact contains the user's task description
- AC3: Plan artifact includes required sections (Steps, Files likely touched, Rollback)
- AC4: Plan command defaults to PermissionMode.READ_ONLY
- AC5: Plan command returns JSON with plan_artifact path and context_pack metadata
- AC6: Context pack includes read_only=True when in read-only mode

Technical Details:
- Uses the main CLI entry point with 'plan' subcommand
- Requires provider configuration in .teaagent/config.toml
- Plan artifacts are markdown files with structured sections
- Output is JSON-formatted for programmatic consumption
- Plan command does not execute any tools or make edits
- Context pack metadata includes permission mode and other runtime settings

References:
- Plan command design: /docs/architecture/plan_command.md
- CLI spec: /docs/specs/cli_interface.md
- Plan artifact format: /docs/specs/plan_artifact.md
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main


def test_plan_cli_writes_artifact(tmp_path: Path) -> None:
    (tmp_path / '.teaagent').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.teaagent' / 'config.toml').write_text(
        'provider = "gpt"\n', encoding='utf-8'
    )

    out = io.StringIO()
    with redirect_stdout(out):
        code = main(
            [
                'plan',
                'gpt',
                'Fix failing calc tests without editing yet',
                '--root',
                str(tmp_path),
            ]
        )
    payload = json.loads(out.getvalue())
    # Verify plan command succeeds (0 or 2 for success scenarios)
    assert code in (0, 2), (
        f'Expected plan command to succeed with code 0 or 2, got {code}'
    )
    artifact = Path(payload['plan_artifact'])
    # Verify plan artifact file was created
    assert artifact.is_file(), f'Expected plan artifact to be a file at {artifact}'
    # Verify artifact is in correct directory
    assert artifact.parent == tmp_path / '.teaagent' / 'plans', (
        f'Expected artifact in .teaagent/plans/, got {artifact.parent}'
    )
    text = artifact.read_text(encoding='utf-8')
    # Verify artifact contains the task description
    assert 'Fix failing calc tests without editing yet' in text, (
        'Expected plan artifact to contain task description'
    )
    # Verify artifact has required sections
    assert '## Steps' in text, 'Expected plan artifact to have "## Steps" section'
    assert '## Files likely touched' in text, (
        'Expected plan artifact to have "## Files likely touched" section'
    )
    assert '## Rollback' in text, 'Expected plan artifact to have "## Rollback" section'
    # plan command defaults to PermissionMode.READ_ONLY, so context_pack.read_only should be True
    assert payload['context_pack']['read_only'] is True, (
        'Expected context_pack.read_only to be True (plan defaults to read-only)'
    )
