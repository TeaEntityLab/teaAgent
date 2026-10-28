# test-type: behavior
"""``--git-sandbox`` is deprecated: passing it warns on stderr but is still accepted."""

from __future__ import annotations

import argparse
import io

from teaagent.cli._handlers._agent.run import warn_deprecated_git_sandbox


def test_warns_on_stderr_when_git_sandbox_passed() -> None:
    stream = io.StringIO()
    args = argparse.Namespace(git_sandbox=True)

    warn_deprecated_git_sandbox(args, stream)

    message = stream.getvalue()
    assert 'deprecated' in message
    assert '--git-sandbox' in message


def test_silent_when_git_sandbox_not_passed() -> None:
    stream = io.StringIO()
    args = argparse.Namespace(git_sandbox=False)

    warn_deprecated_git_sandbox(args, stream)

    assert stream.getvalue() == ''


def test_silent_when_attribute_absent() -> None:
    stream = io.StringIO()

    warn_deprecated_git_sandbox(argparse.Namespace(), stream)

    assert stream.getvalue() == ''
