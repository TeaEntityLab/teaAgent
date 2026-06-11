from __future__ import annotations

import json
import signal
import tempfile
from pathlib import Path

from teaagent.scratchpad import Scratchpad


def test_write_and_read_cycle() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / 'repo'
        root.mkdir()
        sp = Scratchpad(root)

        assert not sp.exists()

        sp.write(
            goal='Implement rate limiting',
            progress='Completed: TokenRateLimiter class. Remaining: wire into server.',
            open_questions=['Should the rate limit be per-IP or per-token?'],
            next_step='Add rate_limiter parameter to VoteRelayServer.__init__',
            session_id='ses_abc123',
        )

        assert sp.exists()

        content = sp.read()
        assert content is not None

        assert content['last_goal'] == 'Implement rate limiting'
        assert 'TokenRateLimiter' in content['progress']
        assert 'rate_limiter' in content['next_step']
        assert content['open_questions'] == [
            'Should the rate limit be per-IP or per-token?'
        ]
        assert content['session_id'] == 'ses_abc123'
        assert 'timestamp' in content


def test_clear_removes_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sp = Scratchpad(Path(tmp))
        sp.write(goal='test', progress='done', open_questions=[], next_step='')
        assert sp.exists()
        sp.clear()
        assert not sp.exists()


def test_exists_returns_correct_values() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sp = Scratchpad(Path(tmp))
        assert not sp.exists()
        sp.write(goal='test', progress='', open_questions=[], next_step='')
        assert sp.exists()


def test_read_returns_none_when_missing() -> None:
    sp = Scratchpad(Path('/nonexistent/path/12345'))
    assert sp.read() is None
    assert not sp.exists()


def test_read_returns_none_on_corrupted_json() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        root.joinpath('.teaagent').mkdir()
        root.joinpath('.teaagent', 'scratchpad.json').write_text(
            'not valid json {{{',
            encoding='utf-8',
        )
        sp = Scratchpad(root)
        assert sp.read() is None
        assert sp.exists()


def test_json_format_correctness() -> None:
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

        assert data['last_goal'] == 'Test goal'
        assert data['progress'] == 'Some progress'
        assert data['open_questions'] == ['Q1', 'Q2']
        assert data['next_step'] == 'Next action'
        assert data['session_id'] == 's1'
        assert isinstance(data['timestamp'], str)


def test_resume_prompt_builds_context() -> None:
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
        assert prompt is not None

        assert 'Build a feature' in prompt
        assert 'Half done' in prompt
        assert 'How to test?' in prompt
        assert 'Add tests' in prompt
        assert '[Resumed from previous session]' in prompt


def test_resume_prompt_returns_none_when_empty() -> None:
    sp = Scratchpad(Path('/nonexistent/777'))
    assert sp.resume_prompt() is None


def test_resume_prompt_returns_none_when_no_meaningful_content() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sp = Scratchpad(Path(tmp))
        sp.write(goal='', progress='', open_questions=[], next_step='')
        assert sp.resume_prompt() is None


def test_write_creates_dot_teaagent_directory() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        sp = Scratchpad(root)
        sp.write(goal='g', progress='p', open_questions=[], next_step='')
        assert root.joinpath('.teaagent').is_dir()
        assert root.joinpath('.teaagent', 'scratchpad.json').is_file()


def test_multiple_write_overwrites() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sp = Scratchpad(Path(tmp))
        sp.write(goal='first', progress='p1', open_questions=[], next_step='n1')
        sp.write(goal='second', progress='p2', open_questions=['q'], next_step='n2')
        content = sp.read()
        assert content is not None
        assert content['last_goal'] == 'second'
        assert content['progress'] == 'p2'
        assert content['open_questions'] == ['q']


def test_atexit_registration() -> None:
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

        sp.write(
            goal='atexit test', progress='cleanup', open_questions=[], next_step=''
        )
        content = sp.read()
        assert content is not None
        assert content['last_goal'] == 'atexit test'


def test_signal_handler_registration() -> None:
    original = signal.getsignal(signal.SIGINT)

    def dummy_handler(signum: int, frame: object) -> None:
        pass

    signal.signal(signal.SIGINT, dummy_handler)
    assert signal.getsignal(signal.SIGINT) == dummy_handler
    signal.signal(signal.SIGINT, original)
    assert signal.getsignal(signal.SIGINT) == original
