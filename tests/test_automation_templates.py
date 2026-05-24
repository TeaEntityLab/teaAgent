from __future__ import annotations

import pytest

from teaagent.automation_templates import get_automation_template
from teaagent.automation_ticket import build_automation_dry_run_payload


def test_repo_watch_template_dry_run_ready(tmp_path) -> None:
    spec = get_automation_template('repo-watch').to_spec()
    payload = build_automation_dry_run_payload(
        spec, root=str(tmp_path), template='repo-watch'
    )
    assert payload['ticket']['ready'] is True
    assert payload['ticket']['max_cost_cents'] > 0
    assert payload['automation']['collector_command']


def test_unknown_template_raises() -> None:
    with pytest.raises(KeyError):
        get_automation_template('missing-template')
