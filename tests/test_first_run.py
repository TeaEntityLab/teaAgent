from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from teaagent.cli._handlers._misc import handle_first_run


class FirstRunTests(unittest.TestCase):
    def test_welcome_shown_when_no_welcomed_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            welcomed_file = root / '.teaagent' / 'welcomed'
            self.assertFalse(welcomed_file.exists())

            err = io.StringIO()
            with redirect_stderr(err):
                result = handle_first_run(root)

            self.assertTrue(result)
            self.assertIn('Welcome to TeaAgent!', err.getvalue())
            self.assertIn('Approval gates', err.getvalue())
            self.assertIn('Audit log', err.getvalue())
            self.assertIn('Undo', err.getvalue())
            self.assertIn('Budget cap', err.getvalue())
            self.assertTrue(welcomed_file.exists())

    def test_welcome_suppressed_when_welcomed_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tea_dir = root / '.teaagent'
            tea_dir.mkdir(parents=True, exist_ok=True)
            (tea_dir / 'welcomed').touch()

            err = io.StringIO()
            with redirect_stderr(err):
                result = handle_first_run(root)

            self.assertFalse(result)
            self.assertEqual(err.getvalue(), '')

    def test_quiet_flag_skips_message_but_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            welcomed_file = root / '.teaagent' / 'welcomed'

            err = io.StringIO()
            with redirect_stderr(err):
                result = handle_first_run(root, quiet=True)

            self.assertFalse(result)
            self.assertEqual(err.getvalue(), '')
            self.assertTrue(welcomed_file.exists())

    def test_idempotent_on_second_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            err1 = io.StringIO()
            with redirect_stderr(err1):
                result1 = handle_first_run(root)
            self.assertTrue(result1)
            self.assertIn('Welcome to TeaAgent!', err1.getvalue())

            err2 = io.StringIO()
            with redirect_stderr(err2):
                result2 = handle_first_run(root)
            self.assertFalse(result2)
            self.assertEqual(err2.getvalue(), '')


if __name__ == '__main__':
    unittest.main()
