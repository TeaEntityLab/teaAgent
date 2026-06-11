"""SURF-011: surface capability registry stays internally consistent."""

from __future__ import annotations

from teaagent.integration.surface_parity import (
    IDE_COMMAND_CLI_EQUIVALENTS,
    IDE_COMMAND_CLI_PARITY,
    IDE_SURFACE_GAPS,
    SURF002_REQUIRED_COMMANDS,
    build_surface_explain,
)


def test_surf002_required_subset_of_ide_parity_map() -> None:
    assert SURF002_REQUIRED_COMMANDS.issubset(IDE_COMMAND_CLI_PARITY)


def test_ide_surface_gaps_document_known_missing_surfaces() -> None:
    assert 'dashboard_cockpit' in IDE_SURFACE_GAPS


def test_ide_equivalents_cover_surf002_required_commands() -> None:
    missing = SURF002_REQUIRED_COMMANDS - set(IDE_COMMAND_CLI_EQUIVALENTS)
    assert not missing


def test_build_surface_explain_lists_surfaces_explain_in_cli() -> None:
    payload = build_surface_explain()
    assert 'surfaces explain' in payload['surfaces']['cli']['supported']
