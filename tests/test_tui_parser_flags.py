"""U-P2-2: TUI parser flag alignment tests.

Ensures the ``tui`` subcommand exposes the same budget/resource flags as
``run``/``chat`` (``--max-iterations``, ``--max-estimated-cost-cents``,
``--memory-limit``) and that ``--provider`` defaults from configuration rather
than hardcoding ``gpt``.
"""

from __future__ import annotations

import argparse

from teaagent.cli._misc_parsers.tui_parser import _tui


def _build_tui_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='teaagent')
    subs = parser.add_subparsers(dest='command')
    _tui(subs, handler=lambda args: 0)
    return parser


def test_tui_parser_has_max_iterations() -> None:
    parser = _build_tui_parser()
    args = parser.parse_args(['tui', '--max-iterations', '42'])
    assert args.max_iterations == 42


def test_tui_parser_max_iterations_default() -> None:
    parser = _build_tui_parser()
    args = parser.parse_args(['tui'])
    assert args.max_iterations == 10


def test_tui_parser_has_max_estimated_cost_cents() -> None:
    parser = _build_tui_parser()
    args = parser.parse_args(['tui', '--max-estimated-cost-cents', '300'])
    assert args.max_estimated_cost_cents == 300


def test_tui_parser_max_estimated_cost_cents_default() -> None:
    parser = _build_tui_parser()
    args = parser.parse_args(['tui'])
    assert args.max_estimated_cost_cents == 500


def test_tui_parser_has_memory_limit() -> None:
    parser = _build_tui_parser()
    args = parser.parse_args(['tui', '--memory-limit', '20'])
    assert args.memory_limit == 20


def test_tui_parser_memory_limit_default() -> None:
    parser = _build_tui_parser()
    args = parser.parse_args(['tui'])
    assert args.memory_limit == 5


def test_tui_parser_provider_default_is_none_not_gpt() -> None:
    """--provider must default to None so the TUI resolves it from config."""
    parser = _build_tui_parser()
    args = parser.parse_args(['tui'])
    assert args.provider is None


def test_tui_parser_provider_can_be_overridden() -> None:
    parser = _build_tui_parser()
    args = parser.parse_args(['tui', '--provider', 'claude'])
    assert args.provider == 'claude'


def test_tui_parser_preserves_existing_flags() -> None:
    parser = _build_tui_parser()
    args = parser.parse_args(
        ['tui', '--database', '/tmp/db.sqlite', '--allow-destructive', '--chat']
    )
    assert args.database == '/tmp/db.sqlite'
    assert args.allow_destructive is True
    assert args.chat is True
