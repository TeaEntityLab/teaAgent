"""Unit tests for the built-in rss-summary skill."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from teaagent.skill_loader import load_skills_with_report

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
SKILL_DIR = PROJECT_ROOT / "teaagent" / "skills" / "builtin" / "rss-summary"


class BuiltinRssSkillTests(unittest.TestCase):
    def test_builtin_rss_skill_exists(self) -> None:
        """SKILL.md, REFERENCE.md, and examples directory exist."""
        self.assertTrue(
            (SKILL_DIR / "SKILL.md").is_file(),
            "SKILL.md should exist in rss-summary skill directory",
        )
        self.assertTrue(
            (SKILL_DIR / "REFERENCE.md").is_file(),
            "REFERENCE.md should exist in rss-summary skill directory",
        )
        examples_dir = SKILL_DIR / "examples"
        self.assertTrue(
            examples_dir.is_dir(),
            "examples directory should exist in rss-summary skill directory",
        )
        self.assertTrue(
            (examples_dir / "example-input.txt").is_file(),
            "example-input.txt should exist",
        )
        self.assertTrue(
            (examples_dir / "example-output.md").is_file(),
            "example-output.md should exist",
        )

    def test_builtin_rss_skill_has_valid_frontmatter(self) -> None:
        """YAML frontmatter parses with required name and description fields."""
        skill_md = SKILL_DIR / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        # Extract YAML frontmatter
        lines = content.splitlines()
        self.assertTrue(lines, "SKILL.md should not be empty")
        self.assertEqual(
            lines[0], "---", "SKILL.md must start with YAML frontmatter delimiter"
        )
        # Find closing ---
        end = None
        for i in range(1, len(lines)):
            if lines[i] == "---":
                end = i
                break
        self.assertIsNotNone(
            end, "SKILL.md must have closing YAML frontmatter delimiter"
        )
        frontmatter_text = "\n".join(lines[1:end])
        data: dict[str, str] = {}
        for line in frontmatter_text.splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                data[key.strip()] = val.strip()
        self.assertTrue(data, "Frontmatter must parse as a YAML mapping")
        self.assertIn("name", data, "Frontmatter must contain 'name'")
        self.assertEqual(data["name"], "rss-summary")
        self.assertIn("description", data, "Frontmatter must contain 'description'")
        self.assertTrue(
            len(data["description"]) > 0,
            "Description must be non-empty",
        )

    def test_builtin_rss_skill_reference_has_limitations(self) -> None:
        """REFERENCE.md contains limitation/caveat language."""
        reference_md = SKILL_DIR / "REFERENCE.md"
        content = reference_md.read_text(encoding="utf-8")
        lower = content.lower()
        has_limitation = "limitation" in lower or "caveat" in lower
        has_known_failure = "known failure" in lower or "failure mode" in lower
        self.assertTrue(
            has_limitation or has_known_failure,
            "REFERENCE.md should document limitations or known failure modes",
        )

    def test_builtin_rss_skill_discovered_by_loader(self) -> None:
        """SkillLoader discovers the built-in rss-summary skill."""
        with tempfile.TemporaryDirectory() as tmp:
            report = load_skills_with_report(
                root=tmp,
                selected_names=frozenset(["rss-summary"]),
            )
            skill_names = [s.name for s in report.skills]
            self.assertIn(
                "rss-summary",
                skill_names,
                f"Built-in rss-summary skill should be discovered. Found: {skill_names}",
            )
            # Verify the builtin directory is in the searched dirs
            searched_strs = [str(d) for d in report.searched_dirs]
            self.assertTrue(
                any("teaagent/skills/builtin" in s for s in searched_strs),
                f"Builtin skills directory should be in searched paths. Got: {searched_strs}",
            )


if __name__ == "__main__":
    unittest.main()
