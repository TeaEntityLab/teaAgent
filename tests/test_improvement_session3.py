"""Tests for session 3 improvement items: lazy imports, CLI errors, caches."""

from __future__ import annotations

import importlib

import teaagent


def test_lazy_import_audit_event() -> None:
    importlib.reload(teaagent)
    from teaagent import AuditEvent

    assert AuditEvent.__name__ == 'AuditEvent'


def test_lazy_import_version_eager() -> None:
    assert isinstance(teaagent.__version__, str)


def test_provider_key_error_hint() -> None:
    from teaagent.llm import ProviderKeyError

    err = ProviderKeyError('claude', 'ANTHROPIC_API_KEY')
    assert 'ANTHROPIC_API_KEY' in str(err)
    assert err.hint is not None
    assert 'setup' in err.hint.lower()


def test_cli_format_error_block_color_off() -> None:
    from teaagent.cli._formatting import format_error_block

    text = format_error_block('Title', 'message', hint='try this', category='CONFIG')
    assert 'Title' in text
    assert 'message' in text
    assert 'try this' in text


def test_config_cache_reset_fixture() -> None:
    from teaagent.config_loader import clear_config_cache

    clear_config_cache()
    # Fixture autouse should not break subsequent imports
    from teaagent.config_loader import ConfigResolver

    assert ConfigResolver is not None


def test_lazy_exports_dir() -> None:
    names = teaagent.__dir__()
    assert '__version__' in names
    assert 'AuditEvent' in names
