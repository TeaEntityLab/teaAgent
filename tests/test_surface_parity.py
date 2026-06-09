"""SURF-011: surface capability registry stays internally consistent."""

from __future__ import annotations

import unittest

from teaagent.integration.surface_parity import (
    IDE_COMMAND_CLI_PARITY,
    IDE_SURFACE_GAPS,
    SURF002_REQUIRED_COMMANDS,
)


class SurfaceParityTests(unittest.TestCase):
    def test_surf002_required_subset_of_ide_parity_map(self) -> None:
        self.assertTrue(SURF002_REQUIRED_COMMANDS.issubset(IDE_COMMAND_CLI_PARITY))

    def test_ide_surface_gaps_document_known_missing_surfaces(self) -> None:
        self.assertIn('dashboard_cockpit', IDE_SURFACE_GAPS)


if __name__ == '__main__':
    unittest.main()
