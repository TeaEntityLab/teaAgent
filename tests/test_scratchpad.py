from __future__ import annotations

import json
import signal
import tempfile
import unittest
from pathlib import Path

from teaagent.scratchpad import Scratchpad


class ScratchpadTests(unittest.TestCase):
    def test_write_and_read_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'repo'
            root.mkdir()
            sp = Scratchpad(root)

            self.assertFalse(sp.exists())

            sp.write(
                goal='Implement rate limiting',
                progress='Completed: TokenRateLimiter class. Remaining: wire into server.',
                open_questions=['Should the rate limit be per-IP or per-token?'],
                next_step='Add rate_limiter parameter to VoteRelayServer.__init__',
                session_id='ses_abc123',
            )

            self.assertTrue(sp.exists())

            content = sp.read()
            self.assertIsNotNone(content)
            assert content is not None

            self.assertEqual(content['last_goal'], 'Implement rate limiting')
            self.assertIn('TokenRateLimiter', content['progress'])
            self.assertIn('rate_limiter', content['next_step'])
            self.assertEqual(
                content['open_questions'],
                ['Should the rate limit be per-IP or per-token?'],
            )
            self.assertEqual(content['session_id'], 'ses_abc123')
            self.assertIn('timestamp', content)

    def test_clear_removes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sp = Scratchpad(Path(tmp))
            sp.write(goal='test', progress='done', open_questions=[], next_step='')
            self.assertTrue(sp.exists())
            sp.clear()
            self.assertFalse(sp.exists())

    def test_exists_returns_correct_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sp = Scratchpad(Path(tmp))
            self.assertFalse(sp.exists())
            sp.write(goal='test', progress='', open_questions=[], next_step='')
            self.assertTrue(sp.exists())

    def test_read_returns_none_when_missing(self) -> None:
        sp = Scratchpad(Path('/nonexistent/path/12345'))
        self.assertIsNone(sp.read())
        self.assertFalse(sp.exists())

    def test_read_returns_none_on_corrupted_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath('.teaagent').mkdir()
            root.joinpath('.teaagent', 'scratchpad.json').write_text(
                'not valid json {{{', encoding='utf-8',
            )
            sp = Scratchpad(root)
            self.assertIsNone(sp.read())
            self.assertTrue(sp.exists())

    def test_json_format_correctness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp = Scratchpad(root)
            sp.write(
                goal='Test goal',
                progress='Some progress',
                open_questions=['Q1', 'Q2'],
                next_step='Next action',
                session_id='s1',
            )
            raw = root.joinpath('.teaagent', 'scratchpad.json').read_text(
                encoding='utf-8',
            )
            data = json.loads(raw)

            self.assertEqual(data['last_goal'], 'Test goal')
            self.assertEqual(data['progress'], 'Some progress')
            self.assertEqual(data['open_questions'], ['Q1', 'Q2'])
            self.assertEqual(data['next_step'], 'Next action')
            self.assertEqual(data['session_id'], 's1')
            self.assertIsInstance(data['timestamp'], str)

    def test_resume_prompt_builds_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sp = Scratchpad(Path(tmp))
            sp.write(
                goal='Build a feature',
                progress='Half done',
                open_questions=['How to test?'],
                next_step='Add tests',
                session_id='ses_xyz',
            )
            prompt = sp.resume_prompt()
            self.assertIsNotNone(prompt)
            assert prompt is not None

            self.assertIn('Build a feature', prompt)
            self.assertIn('Half done', prompt)
            self.assertIn('How to test?', prompt)
            self.assertIn('Add tests', prompt)
            self.assertIn('[Resumed from previous session]', prompt)

    def test_resume_prompt_returns_none_when_empty(self) -> None:
        sp = Scratchpad(Path('/nonexistent/777'))
        self.assertIsNone(sp.resume_prompt())

    def test_resume_prompt_returns_none_when_no_meaningful_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sp = Scratchpad(Path(tmp))
            sp.write(goal='', progress='', open_questions=[], next_step='')
            self.assertIsNone(sp.resume_prompt())

    def test_write_creates_dot_teaagent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sp = Scratchpad(root)
            sp.write(goal='g', progress='p', open_questions=[], next_step='')
            self.assertTrue(root.joinpath('.teaagent').is_dir())
            self.assertTrue(root.joinpath('.teaagent', 'scratchpad.json').is_file())

    def test_multiple_write_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sp = Scratchpad(Path(tmp))
            sp.write(goal='first', progress='p1', open_questions=[], next_step='n1')
            sp.write(goal='second', progress='p2', open_questions=['q'], next_step='n2')
            content = sp.read()
            assert content is not None
            self.assertEqual(content['last_goal'], 'second')
            self.assertEqual(content['progress'], 'p2')
            self.assertEqual(content['open_questions'], ['q'])

    def test_atexit_registration(self) -> None:
        import atexit

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            from teaagent.scratchpad import Scratchpad

            sp = Scratchpad(root)

            def handler() -> None:
                sp.write(
                    goal='atexit test',
                    progress='cleanup',
                    open_questions=[],
                    next_step='',
                )

            atexit.register(handler)
            atexit.unregister(handler)

            sp.write(goal='atexit test', progress='cleanup', open_questions=[], next_step='')
            content = sp.read()
            self.assertIsNotNone(content)
            assert content is not None
            self.assertEqual(content['last_goal'], 'atexit test')

    def test_signal_handler_registration(self) -> None:
        original = signal.getsignal(signal.SIGINT)

        def dummy_handler(signum: int, frame: object) -> None:
            pass

        signal.signal(signal.SIGINT, dummy_handler)
        self.assertEqual(signal.getsignal(signal.SIGINT), dummy_handler)
        signal.signal(signal.SIGINT, original)
        self.assertEqual(signal.getsignal(signal.SIGINT), original)
