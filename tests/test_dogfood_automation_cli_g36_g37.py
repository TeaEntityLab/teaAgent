# test-type: behavior
"""Pins dogfood findings G36/G37 for the `agent automation` CLI (R5).

G36: ``agent automation add --schedule '<cron>'`` must return the automation
command family's classified ``{"status": "error", ...}`` shape (return 1)
instead of the generic ``Unexpected error:`` catch-all, and must not write the
automation store on the error path.

G37: ``run``/``pause``/``resume``/``delete``/``show`` must resolve a unique
automation ``name`` to its ``automation_id``; ambiguous names and unknown
names stay classified errors.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main


def _run(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(argv)
    return code, out.getvalue()


def _add(
    root: Path, name: str, task: str, *, schedule: str = 'every 30m'
) -> tuple[int, str]:
    return _run(
        [
            'agent',
            'automation',
            'add',
            name,
            task,
            '--schedule',
            schedule,
            '--provider',
            'fake',
            '--root',
            str(root),
        ]
    )


def _stored_automation_files(root: Path) -> list[str]:
    names: list[str] = []
    for sub in ('automations', 'automations-quarantine'):
        names.extend(p.name for p in (root / '.teaagent' / sub).glob('*.json'))
    return sorted(names)


def test_add_rejects_cron_schedule_without_writing_store(tmp_path: Path) -> None:
    code, stdout = _add(tmp_path, 'cronjob', 'summarize repo', schedule='*/5 * * * *')
    assert code == 1
    payload = json.loads(stdout)
    assert payload == {
        'status': 'error',
        'message': (
            "unsupported schedule '*/5 * * * *'; "
            "use 'every 30m', 'every 2h', or 'daily HH:MM'"
        ),
    }
    # Nothing persisted: the store dir must not even be created on this path.
    assert not (tmp_path / '.teaagent' / 'automations').exists()
    assert _stored_automation_files(tmp_path) == []


def test_show_resolves_unique_name_to_same_record_as_id(tmp_path: Path) -> None:
    add_code, add_out = _add(tmp_path, 'myauto', 'summarize repo')
    assert add_code == 0
    automation_id = json.loads(add_out)['automation']['automation_id']

    id_code, id_out = _run(
        ['agent', 'automation', 'show', automation_id, '--root', str(tmp_path)]
    )
    name_code, name_out = _run(
        ['agent', 'automation', 'show', 'myauto', '--root', str(tmp_path)]
    )
    assert id_code == 0
    assert name_code == 0
    assert json.loads(name_out) == json.loads(id_out)
    assert json.loads(name_out)['automation_id'] == automation_id


def test_show_ambiguous_name_is_classified_error(tmp_path: Path) -> None:
    assert _add(tmp_path, 'dup', 'task one')[0] == 0
    assert _add(tmp_path, 'dup', 'task two')[0] == 0
    code, stdout = _run(['agent', 'automation', 'show', 'dup', '--root', str(tmp_path)])
    assert code == 1
    payload = json.loads(stdout)
    assert payload['status'] == 'error'
    assert payload['message'].startswith("ambiguous automation name 'dup': ids ")


def test_pause_and_delete_by_name(tmp_path: Path) -> None:
    add_code, add_out = _add(tmp_path, 'nightly', 'nightly task')
    assert add_code == 0
    automation_id = json.loads(add_out)['automation']['automation_id']

    pause_code, pause_out = _run(
        ['agent', 'automation', 'pause', 'nightly', '--root', str(tmp_path)]
    )
    assert pause_code == 0
    paused = json.loads(pause_out)
    assert paused['status'] == 'paused'
    assert paused['automation']['enabled'] is False
    assert paused['automation']['automation_id'] == automation_id

    delete_code, delete_out = _run(
        ['agent', 'automation', 'delete', 'nightly', '--root', str(tmp_path)]
    )
    assert delete_code == 0
    deleted = json.loads(delete_out)
    assert deleted['status'] == 'deleted'
    assert deleted['automation_id'] == automation_id
    assert _stored_automation_files(tmp_path) == []


def test_unknown_name_uses_existing_not_found_shape(tmp_path: Path) -> None:
    code, stdout = _run(
        ['agent', 'automation', 'show', 'ghost', '--root', str(tmp_path)]
    )
    assert code == 1
    payload = json.loads(stdout)
    assert payload == {
        'status': 'error',
        'message': "automation 'ghost' not found",
    }
