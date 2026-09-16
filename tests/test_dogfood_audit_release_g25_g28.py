# test-type: behavior
"""Pins dogfood findings G28 and G25 (R5).

G28: a bare ``teaagent audit verify`` (no ``run_id`` / ``--path``) must refuse
up front with the audit family's classified error when the legacy
``.teaagent/audit.jsonl`` is absent, instead of chasing a nonexistent default
log and only hinting after a failed verification attempt. When the legacy log
exists it must still be verified.

G25: ``release evidence`` (default ``release``/``full`` profile) must emit
progress lines on stderr around the multi-minute gate steps (``pre-commit run
-a`` and the acceptance tier) so operators are not left staring at a silent
process, while stdout stays a single parseable result document. The
``counts-only`` profile skips those steps and must emit no progress lines.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import teaagent.release_evidence as release_evidence
from teaagent.cli._handlers import _audit
from teaagent.cli._handlers._audit import audit_verify_command
from teaagent.cli._handlers._release import release_evidence_command


def _verify_args(root: Path) -> argparse.Namespace:
    return argparse.Namespace(
        root=str(root),
        path=None,
        run_id=None,
        ci=False,
        signature=None,
    )


def test_g28_bare_verify_without_default_log_errors_before_verifying(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Falsifier: verifier runs (or generic 'not found' with no runs hint)."""
    calls: list[Path] = []

    def _must_not_run(path: Path):  # pragma: no cover - asserted not called
        calls.append(path)
        raise AssertionError('verify_audit_chain must not run for a bare verify')

    monkeypatch.setattr(_audit, 'verify_audit_chain', _must_not_run)

    rc = audit_verify_command(_verify_args(tmp_path))
    out = capsys.readouterr().out

    assert rc == 1
    assert calls == []
    payload = json.loads(out)
    assert payload['status'] == 'error'
    assert '.teaagent/runs/' in payload['message']
    assert '--path' in payload['message']


def test_g28_bare_verify_with_legacy_log_still_verifies(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Falsifier: legacy .teaagent/audit.jsonl is no longer verified."""
    log_path = tmp_path / '.teaagent' / 'audit.jsonl'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text('{}\n', encoding='utf-8')

    verified: list[Path] = []

    def _spy(path: Path):
        verified.append(Path(path))
        return SimpleNamespace(valid=True, event_count=3, total_legacy_events=0)

    monkeypatch.setattr(_audit, 'verify_audit_chain', _spy)

    rc = audit_verify_command(_verify_args(tmp_path))
    capsys.readouterr()

    assert rc == 0
    assert verified == [log_path]


def _fake_run(argv, *, cwd, timeout_seconds=600):
    return {
        'cmd': ' '.join(argv),
        'exit_code': 0,
        'duration_seconds': 0.01,
        'stdout': '',
        'stderr': '',
    }


def _evidence_args(profile: str, root: Path, output: Path) -> argparse.Namespace:
    return argparse.Namespace(
        release_profile=profile,
        root=str(root),
        output=str(output),
    )


def test_g25_release_evidence_emits_progress_on_stderr(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Falsifier: gate steps run silently (no running:/done in on stderr)."""
    monkeypatch.setattr(release_evidence, '_run', _fake_run)

    rc = release_evidence_command(
        _evidence_args('release', tmp_path, tmp_path / 'evidence.json')
    )
    captured = capsys.readouterr()

    assert rc in (0, 1)
    # stdout stays a single parseable result document.
    doc = json.loads(captured.out)
    assert 'ok' in doc
    # progress went to stderr, not stdout, for both expensive steps.
    assert '[release evidence] running: pre-commit run -a' in captured.err
    assert '[release evidence] running: acceptance tier pytest' in captured.err
    assert captured.err.count('done in') >= 2
    assert '[release evidence]' not in captured.out


def test_g25_counts_only_profile_emits_no_progress(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Falsifier: progress lines leak into the counts-only profile."""
    monkeypatch.setattr(release_evidence, '_run', _fake_run)

    rc = release_evidence_command(
        _evidence_args('counts-only', tmp_path, tmp_path / 'evidence.json')
    )
    captured = capsys.readouterr()

    assert rc in (0, 1)
    doc = json.loads(captured.out)
    assert 'ok' in doc
    assert '[release evidence]' not in captured.err
