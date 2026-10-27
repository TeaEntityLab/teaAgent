# test-type: contract
"""The ``--git-sandbox`` help text must not imply opt-in.

Runtime enables the git sandbox automatically in git repositories (see
``teaagent/cli/_handlers/_agent/run.py``); the flag itself has no effect.
"""

from __future__ import annotations

import argparse

from teaagent.cli import build_parser


def _git_sandbox_actions(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    found: list[argparse.Action] = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for sub in action.choices.values():
                found.extend(_git_sandbox_actions(sub))
        elif '--git-sandbox' in action.option_strings:
            found.append(action)
    return found


def test_git_sandbox_help_does_not_claim_opt_in() -> None:
    actions = _git_sandbox_actions(build_parser())
    assert actions, 'expected at least one --git-sandbox option'

    for action in actions:
        help_text = action.help or ''
        lowered = help_text.lower()
        assert 'run agent task in a git sandbox' not in lowered
        assert 'no effect' in lowered
        assert 'automatically' in lowered
        assert 'git repository' in lowered
