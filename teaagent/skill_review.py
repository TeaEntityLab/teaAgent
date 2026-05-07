from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


EXTERNAL_COMMAND_PATTERNS = (
    re.compile(r"\b(curl|wget|ssh|scp|nc)\b"),
    re.compile(r"https?://"),
)


@dataclass(frozen=True)
class SkillReviewFinding:
    severity: str
    message: str


@dataclass(frozen=True)
class SkillReviewResult:
    skill_path: Path
    findings: list[SkillReviewFinding]

    @property
    def passed(self) -> bool:
        return not any(finding.severity == "error" for finding in self.findings)


def review_skill(skill_path: Path, *, max_skill_md_lines: int = 80) -> SkillReviewResult:
    skill_file = skill_path / "SKILL.md" if skill_path.is_dir() else skill_path
    findings: list[SkillReviewFinding] = []
    if not skill_file.exists():
        return SkillReviewResult(
            skill_path=skill_file,
            findings=[SkillReviewFinding("error", "SKILL.md is missing")],
        )

    text = skill_file.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        findings.append(SkillReviewFinding("error", "SKILL.md must start with YAML frontmatter"))
    if "name:" not in text:
        findings.append(SkillReviewFinding("error", "SKILL.md frontmatter must include name"))
    if "description:" not in text:
        findings.append(SkillReviewFinding("error", "SKILL.md frontmatter must include description"))
    if len(lines) > max_skill_md_lines:
        findings.append(
            SkillReviewFinding(
                "warning",
                f"SKILL.md has {len(lines)} lines; prefer Progressive Disclosure",
            )
        )
    for pattern in EXTERNAL_COMMAND_PATTERNS:
        if pattern.search(text):
            findings.append(
                SkillReviewFinding(
                    "warning",
                    "SKILL.md references external network access; review supply-chain risk",
                )
            )
            break
    if "REFERENCE.md" not in text and len(lines) > 40:
        findings.append(
            SkillReviewFinding(
                "warning",
                "Long skill should reference REFERENCE.md for Progressive Disclosure",
            )
        )
    return SkillReviewResult(skill_path=skill_file, findings=findings)
