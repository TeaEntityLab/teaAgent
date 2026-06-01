"""AC: plan command writes a reviewable artifact under .teaagent/plans."""

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
    assert code in (0, 2)
    artifact = Path(payload['plan_artifact'])
    assert artifact.is_file()
    assert artifact.parent == tmp_path / '.teaagent' / 'plans'
    text = artifact.read_text(encoding='utf-8')
    assert 'Fix failing calc tests without editing yet' in text
    assert '## Steps' in text
    assert '## Files likely touched' in text
    assert '## Rollback' in text
    # plan command defaults to PermissionMode.READ_ONLY, so context_pack.read_only should be True
    assert payload['context_pack']['read_only'] is True
