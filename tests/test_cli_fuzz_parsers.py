"""Fuzz CLI argument parsing with hypothesis."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from teaagent.cli import build_parser


@settings(max_examples=30, deadline=None)
@given(st.sampled_from(['health', 'metrics', 'setup', 'doctor']))
def test_top_level_commands_parse(subcommand):
    parser = build_parser()
    args = parser.parse_args(
        [subcommand] if subcommand != 'doctor' else ['doctor', 'all']
    )
    assert args.command == subcommand or getattr(args, 'doctor_command', None) == 'all'


def test_health_parser_accepts_root():
    parser = build_parser()
    args = parser.parse_args(['health', '--root', '.'])
    assert args.command == 'health'


def test_metrics_parser():
    parser = build_parser()
    args = parser.parse_args(['metrics'])
    assert args.command == 'metrics'


def test_credentials_rotate_parser():
    parser = build_parser()
    args = parser.parse_args(['credentials', 'rotate', 'gpt', '--dry-run'])
    assert args.provider == 'gpt'
    assert args.dry_run is True


def test_audit_verify_ci_flag():
    parser = build_parser()
    args = parser.parse_args(['audit', 'verify', '--ci', '--root', '.'])
    assert args.ci is True
