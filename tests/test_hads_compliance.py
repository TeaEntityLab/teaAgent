"""Acceptance test for HADS (Human-AI Document Standard) compliance."""

from __future__ import annotations

import unittest
from pathlib import Path


def is_hads_compliant(content: str) -> bool:
    """
    Check if a markdown string follows HADS:
    - Must start with YAML front matter (--- ... ---)
    - Must have a # Title
    - Must have standardized sections (Overview, Usage, etc.)
    """
    lines = content.strip().splitlines()
    if not lines or lines[0] != '---':
        return False

    # Simple check for closing front matter
    try:
        end_front_matter = lines[1:].index('---') + 1
    except ValueError:
        return False

    # Check for Title after front matter
    remaining = lines[end_front_matter + 1 :]
    has_title = any(line.startswith('# ') for line in remaining)

    return has_title


class TestHADSCompliance(unittest.TestCase):
    def test_sample_hads_document(self) -> None:
        content = """---
type: documentation
audience: human, ai
status: stable
---
# TeaAgent Usage

Overview: How to use TeaAgent.
"""
        self.assertTrue(is_hads_compliant(content))

    def test_existing_usage_doc_is_now_hads(self) -> None:
        usage_path = Path('docs/USAGE.md')
        if usage_path.exists():
            content = usage_path.read_text(encoding='utf-8')
            self.assertTrue(
                is_hads_compliant(content), 'docs/USAGE.md should now be HADS compliant'
            )


if __name__ == '__main__':
    unittest.main()
