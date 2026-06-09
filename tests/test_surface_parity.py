"""SURF-011: surface capability registry stays internally consistent."""

from __future__ import annotations

import unittest

from teaagent.integration.surface_parity import (
    IDE_COMMAND_CLI_EQUIVALENTS,
    IDE_COMMAND_CLI_PARITY,
    IDE_SURFACE_GAPS,
    SURF002_REQUIRED_COMMANDS,
    build_surface_explain,
)


class SurfaceParityTests(unittest.TestCase):
    def test_surf002_required_subset_of_ide_parity_map(self) -> None:
        self.assertTrue(SURF002_REQUIRED_COMMANDS.issubset(IDE_COMMAND_CLI_PARITY))

    def test_ide_surface_gaps_document_known_missing_surfaces(self) -> None:
        self.assertIn('dashboard_cockpit', IDE_SURFACE_GAPS)

    def test_ide_equivalents_cover_surf002_required_commands(self) -> None:
        missing = SURF002_REQUIRED_COMMANDS - set(IDE_COMMAND_CLI_EQUIVALENTS)
        self.assertFalse(missing)

    def test_build_surface_explain_lists_surfaces_explain_in_cli(self) -> None:
        payload = build_surface_explain()
        self.assertIn('surfaces explain', payload['surfaces']['cli']['supported'])


if __name__ == '__main__':
    unittest.main()
