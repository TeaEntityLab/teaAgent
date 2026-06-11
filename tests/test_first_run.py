from __future__ import annotations

import io
import tempfile
from contextlib import redirect_stderr
from pathlib import Path

from teaagent.cli._handlers._misc import handle_first_run


def test_welcome_shown_when_no_welcomed_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        welcomed_file = root / '.teaagent' / 'welcomed'
        assert not welcomed_file.exists()

        err = io.StringIO()
        with redirect_stderr(err):
            result = handle_first_run(root)

        assert result is True
        assert 'Welcome to TeaAgent!' in err.getvalue()
        assert 'Approval gates' in err.getvalue()
        assert 'Audit log' in err.getvalue()
        assert 'Undo' in err.getvalue()
        assert 'Budget cap' in err.getvalue()
        assert welcomed_file.exists()


def test_welcome_suppressed_when_welcomed_file_exists() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tea_dir = root / '.teaagent'
        tea_dir.mkdir(parents=True, exist_ok=True)
        (tea_dir / 'welcomed').touch()

        err = io.StringIO()
        with redirect_stderr(err):
            result = handle_first_run(root)

        assert result is False
        assert err.getvalue() == ''


def test_quiet_flag_skips_message_but_creates_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        welcomed_file = root / '.teaagent' / 'welcomed'

        err = io.StringIO()
        with redirect_stderr(err):
            result = handle_first_run(root, quiet=True)

        assert result is False
        assert err.getvalue() == ''
        assert welcomed_file.exists()


def test_idempotent_on_second_call() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        err1 = io.StringIO()
        with redirect_stderr(err1):
            result1 = handle_first_run(root)
        assert result1 is True
        assert 'Welcome to TeaAgent!' in err1.getvalue()

        err2 = io.StringIO()
        with redirect_stderr(err2):
            result2 = handle_first_run(root)
        assert result2 is False
        assert err2.getvalue() == ''
