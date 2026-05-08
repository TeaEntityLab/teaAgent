from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from teaagent.skill_review import SkillReviewResult, SkillReviewFinding, review_skill


class SkillReviewTests(unittest.TestCase):
    def test_missing_skill_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "empty-skill"
            skill_dir.mkdir()

            result = review_skill(skill_dir)

            self.assertFalse(result.passed)
            self.assertEqual(len(result.findings), 1)
            self.assertEqual(result.findings[0].severity, "error")
            self.assertIn("missing", result.findings[0].message)

    def test_missing_yaml_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "bad-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("No frontmatter here.\n", encoding="utf-8")

            result = review_skill(skill_dir)

            self.assertFalse(result.passed)
            messages = [f.message for f in result.findings]
            self.assertTrue(any("frontmatter" in m for m in messages))

    def test_missing_name_in_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "bad-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\ndescription: No name.\n---\n\n# Bad Skill\n",
                encoding="utf-8",
            )

            result = review_skill(skill_dir)

            self.assertFalse(result.passed)
            messages = [f.message for f in result.findings]
            self.assertTrue(any("name" in m for m in messages))

    def test_missing_description_in_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "bad-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: no-desc\n---\n\n# Bad Skill\n",
                encoding="utf-8",
            )

            result = review_skill(skill_dir)

            self.assertFalse(result.passed)
            messages = [f.message for f in result.findings]
            self.assertTrue(any("description" in m for m in messages))

    def test_too_many_lines_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "long-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: long\ndescription: long\n---\n" + "line\n" * 90,
                encoding="utf-8",
            )

            result = review_skill(skill_dir, max_skill_md_lines=80)

            self.assertTrue(result.passed)
            self.assertTrue(any("Progressive Disclosure" in f.message for f in result.findings))

    def test_external_network_reference_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "net-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: net\ndescription: uses curl\n---\n\nRun: `curl https://example.com`\n",
                encoding="utf-8",
            )

            result = review_skill(skill_dir)

            self.assertTrue(result.passed)
            self.assertTrue(any("network" in f.message for f in result.findings))

    def test_wget_triggers_network_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "net-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: net\ndescription: uses wget\n---\n\nDownload with `wget`.\n",
                encoding="utf-8",
            )

            result = review_skill(skill_dir)

            self.assertTrue(result.passed)
            self.assertTrue(any("network" in f.message for f in result.findings))

    def test_long_skill_without_reference_md_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "long-no-ref"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: long-no-ref\ndescription: long without reference\n---\n" + "line\n" * 50,
                encoding="utf-8",
            )

            result = review_skill(skill_dir)

            self.assertTrue(result.passed)
            self.assertTrue(any("REFERENCE" in f.message for f in result.findings))

    def test_short_skill_without_reference_md_is_fine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "short-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: short\ndescription: short without reference\n---\n" + "line\n" * 10,
                encoding="utf-8",
            )

            result = review_skill(skill_dir)

            self.assertTrue(result.passed)
            self.assertFalse(any("REFERENCE" in f.message for f in result.findings))

    def test_review_skill_file_not_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_file = Path(tmp) / "SKILL.md"
            skill_file.write_text(
                "---\nname: file\ndescription: file review\n---\n\n# File\n",
                encoding="utf-8",
            )

            result = review_skill(skill_file)

            self.assertTrue(result.passed)
            self.assertEqual(result.skill_path, skill_file)

    def test_network_and_length_warnings_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "combo-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: combo\ndescription: combo issues\n---\n"
                + "line\n" * 50
                + "Install with `curl https://example.com`\n",
                encoding="utf-8",
            )

            result = review_skill(skill_dir, max_skill_md_lines=80)

            messages = [f.message for f in result.findings]
            self.assertTrue(any("Progressive Disclosure" in m for m in messages))
            self.assertTrue(any("network" in m for m in messages))


if __name__ == "__main__":
    unittest.main()
